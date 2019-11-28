from ast import literal_eval
from collections import defaultdict, ChainMap
from os import stat
from time import ctime
from eyed3 import load
from eyed3.id3 import frames

from src.definitions.data_management import *
from src.utils.common import is_empty


class Track:
    """ Class encapsulating a track and its metadata. """

    class TrackMetadata:
        """ Wrapper class for track metadata. """

        def __init__(self, title, artists, remixers, genre, label, bpm, key, camelot_code, energy, date_added):
            """
            Initializes class with all metadata.

            :param title - track title.
            :param artists - track artists.
            :param remixers - track remixers.
            :param genre - track genre.
            :param label - track record label.
            :param bpm - track bpm.
            :param key - track key.
            :param camelot_code - track camelot code.
            :param energy  - track Mixed In Key energy level.
            :param date_added - date track was added ot the collection.
            """

            self.title = title
            self.artists = artists
            self.remixers = remixers
            self.genre = genre
            self.label = label
            self.bpm = bpm
            self.key = key
            self.camelot_code = camelot_code
            self.energy = energy
            self.date_added = date_added

        def get_metadata(self):
            """ Return non-empty metadata in dictionary form. """

            title_metadata = self._get_metadata_from_title()
            return {k: v for k, v in {
                'Title': self.title,
                'Artists': self.artists,
                'Remixers': self.remixers,
                'Genre': self.genre,
                'Label': self.label,
                'BPM': title_metadata.get('BPM') or self.bpm,
                'Key': title_metadata.get('Key') or self.key,
                'Camelot Code': title_metadata.get('Camelot Code') or self.camelot_code,
                'Energy': self.energy,
                'Date Added': self.date_added
            }.items() if not is_empty(v)}

        def get_database_row(self, file_path):
            """ Returns non-empty metadata in sqlalchemy-ready format. """

            track_metadata = self.get_metadata()
            return {col: value for col, value in {
                'file_path': file_path,
                'title': track_metadata.get('Title'),
                'bpm': int(track_metadata.get('BPM', '-1')),
                'key': track_metadata.get('Key'),
                'camelot_code': track_metadata.get('Camelot Code'),
                'energy': int(track_metadata.get('Energy', '-1')),
                'genre': track_metadata.get('Genre'),
                'label': ' '.join([w.capitalize() for w in track_metadata.get('Label', '').split()]),
                'date_added': track_metadata.get('Date Added')
            }.items() if not (is_empty(value) or value == -1)}

        def write_tags(self, track_path, tag_filter=None):
            """
            Write track's tags and metadata to ID3 fields, if they don't already exist.

            :param track_path - Full qualified path to the track file.
            :param tag_filter (optional) - Set of tags to write.
            """

            md = load(track_path)
            if md is None:
                return

            # Remove tags not supported by eyed3
            md = md.tag
            self._remove_unsupported_tags(md)

            # Update tags to fix any discrepancies
            frames = list(md.frameiter())
            track_metadata = self.get_metadata()
            for k, v in track_metadata.items():
                if k in KEYS_TO_OMIT_FROM_MD_UPDATES or self._exclude_tag(k, tag_filter):
                    continue

                frame = self._get_frame_with_metadata_key(k, frames)
                if frame is None:
                    continue

                frame.text = v

            # Write metadata
            comment = ID3Tag.COMMENT.value
            comment_frame = (None if self._exclude_tag(comment, tag_filter)
                             else self._get_frame_with_metadata_key(comment, frames))
            if comment_frame is None:
                return

            comment_frame.text = 'Metadata: ' + str(track_metadata)
            md.save()

        @staticmethod
        def _get_frame_with_metadata_key(metadata_key, frames):
            """
            Uses metadata key to retrieve corresponding ID3 frame, if available.

            :param metadata_key - the metadata key.
            :param frames - track's ID3 frames.
            """
            tag = READABLE_TO_ID3.get(metadata_key)
            if tag is None:
                return None

            target_frame = list(filter(lambda frame: frame.id.decode('utf-8') == tag, frames))
            if len(target_frame) == 1:
                return target_frame[0]

            return None

        def _get_metadata_from_title(self):
            """ Extracts Camelot Code, key, and BPM from track title."""

            title_md = re.findall(MD_FORMAT_REGEX, self.title)
            if len(title_md) == 1:
                camelot_code, key, bpm = title_md[0]

                return {
                    'Camelot Code': camelot_code,
                    'Key': key,
                    'BPM': bpm
                }

            return {}

        @staticmethod
        def _exclude_tag(tag, tag_filter):
            """
            Returns whether the given tag's updates should be omitted.

            :param tag - Name of the tag.
            :param tag_filter - Set of tags whose ID3 frames should be updated.
            """

            return not (tag_filter is None or tag in tag_filter)

        @staticmethod
        def _remove_unsupported_tags(md_tag):
            """
            Remove any tags not currently supported by eyed3.

            :param md_tag - Wrapper for a track's ID3 tags.
            """

            frame_set = md_tag.frame_set
            for k, tags in frame_set.items():
                for unsupported_tag in list(
                        filter(lambda frame: frame.id.decode('utf-8') in UNSUPPORTED_ID3_TAGS, tags)):
                    tags.remove(unsupported_tag)
                dict.__setitem__(frame_set, k, tags)

    def __init__(self, track_path):
        """
        Constructor. Initializes ID3 data and structures.

        :param track_path - Qualified path to the track.
        """

        self.track_path = track_path
        self.id3_data = self._extract_id3_data()
        self.formatted = dict(ChainMap(
            {id3_tag.value: None for id3_tag in ID3Tag},
            {custom_tag.value: None for custom_tag in CustomTag}
        ))

    def format_artists(self):
        """ Formats artist string. """

        artists = self.formatted[ID3Tag.ARTIST.value]
        if artists is not None:
            return artists

        featured = self.formatted[CustomTag.FEATURED.value]
        artists = self.get_tag(ID3Tag.ARTIST)

        featured_set = set() if featured is None else set(featured)
        filtered_artists = list(filter(lambda artist: artist not in featured_set, artists.split(', ')))
        # If any artist names contain "&" then we want to use "and" to separate artist names in the title, for clarity.
        separator = ' and ' if any('&' in artist for artist in filtered_artists) else ' & '

        formatted_artists = separator.join(filtered_artists)
        self.formatted[ID3Tag.ARTIST.value] = formatted_artists

        return formatted_artists

    def format_bpm(self):
        """ Formats BPM string. """

        bpm = self.formatted[ID3Tag.BPM.value]
        if bpm is not None:
            return bpm

        bpm = self.get_tag(ID3Tag.BPM)

        formatted_bpm = ''.join([str(0)] * max(3 - len(bpm), 0)) + bpm
        self.formatted[ID3Tag.BPM.value] = formatted_bpm

        return formatted_bpm

    def format_camelot_code(self):
        """ Formats camelot code. """

        camelot_code = self.formatted[CustomTag.CAMELOT_CODE.value]
        if camelot_code is not None:
            return camelot_code

        camelot_code = CAMELOT_MAP.get(self.format_key())
        self.formatted[CustomTag.CAMELOT_CODE.value] = camelot_code

        return camelot_code

    def format_energy(self):
        """ Formats energy level. """

        energy = self.formatted[ID3Tag.ENERGY.value]
        if energy is not None:
            return energy

        energy = self.get_tag(ID3Tag.ENERGY)
        if energy is not None:
            energy = int(energy)
            self.formatted[ID3Tag.ENERGY.value] = energy
            return energy

        comment = self.get_tag(ID3Tag.COMMENT) or ''
        if comment.startswith('Energy'):
            segments = [s.strip() for s in comment.split()]
            if len(segments) > 1 and segments[1].isnumeric():
                energy = int(segments[1])
        elif comment.startswith('Metadata: '):
            track_metadata = literal_eval(comment.split('Metadata: ')[1])
            energy = str(track_metadata.get('Energy', ''))
            energy = None if not energy.isnumeric() else int(energy)

        self.formatted[ID3Tag.ENERGY.value] = energy

        return energy

    def format_key(self):
        """ Formats key. """

        key = self.formatted[ID3Tag.KEY.value]
        if key is not None:
            return key

        key = self.get_tag(ID3Tag.KEY)

        formatted_key = CANONICAL_KEY_MAP.get(key.lower())
        self.formatted[ID3Tag.KEY.value] = formatted_key

        return formatted_key

    def format_title(self):
        """ Formats track title. """

        title, featured = self.formatted[ID3Tag.TITLE.value], self.formatted[CustomTag.FEATURED.value]
        if title is not None:
            return title, featured

        title = self.get_tag(ID3Tag.TITLE)
        if title is None:
            return None, None

        featured = None
        segments = title.split(' ')
        filtered_segments = []

        i = 0
        n = len(segments)
        open_paren_found = False
        while i < n:
            segment = segments[i]

            if '(' in segment:
                open_paren_found = True

            # Replace all instances of 'feat.' with 'ft.' inside the parenthetical phrase indicating mix type.
            # e.g. "(Hydroid feat. Santiago Nino Mix)" becomes "(Hydroid ft. Santiago Nino Mix)"
            if segment.lower() == 'feat.':
                if open_paren_found:
                    filtered_segments.append('ft.')
                    i += 1
                else:
                    # If we haven't seen an open parentheses yet, then the featured artist's name is composed of all
                    # words occuring before the parentheses. This heuristic works for MP3 files purchased on Beatport.
                    featured = []
                    for j in range(i + 1, n):
                        next_part = segments[j]
                        if '(' in next_part:
                            break
                        featured.append(next_part)
                    featured = ' '.join(featured)
                    i = j
            else:
                filtered_segments.append(segment.strip())
                i += 1

        # Get rid of "(Original Mix)" and "(Extended Mix)" as these are redundant phrases that unnecessarily lengthen
        # the file name.
        formatted_title = ' '.join(filtered_segments).replace('(Original Mix)', '').replace('(Extended Mix)', '')

        self.formatted[ID3Tag.TITLE.value] = formatted_title
        self.formatted[CustomTag.FEATURED.value] = featured

        return formatted_title, featured

    def format_track_name(self):
        """ Formats track name. """

        track_name = self.formatted[CustomTag.TRACK_NAME.value]
        if track_name is not None:
            return track_name

        title, featured = self.format_title()
        artists = self.format_artists()
        bpm = self.format_bpm()
        key = self.format_key()
        camelot_code = self.format_camelot_code()

        metadata_prefix = ' - '.join(['[' + camelot_code, key.capitalize(), bpm + ']'])
        artist_midfix = artists + ('' if featured is None else ' ft. ' + featured)
        track_name = metadata_prefix + ' ' + artist_midfix + ' - ' + title
        self.formatted[CustomTag.TRACK_NAME] = track_name

        return track_name

    def generate_metadata(self, title, artists, remixers, genre, label, bpm, key, camelot_code, energy, date_added):
        """
        Uses parameters to build and return metadata.

        :param title - track title.
        :param artists - track artists.
        :param remixers - track remixers.
        :param genre - track genre.
        :param label - track record label.
        :param bpm - track bpm.
        :param key - track key.
        :param camelot_code - track camelot code.
        :param energy  - track Mixed In Key energy level.
        :param date_added - date track was added ot the collection.
        """

        return self.TrackMetadata(title, artists, remixers, genre, label, bpm, key, camelot_code, energy, date_added)

    def generate_metadata_from_id3(self):
        """ Uses ID3 tags to generate track metadata. """
        title, featured = self.format_title()
        artists = self.get_tag(ID3Tag.ARTIST)
        artists = ([] if artists is None else artists.split(', ')) + ([] if featured is None else [featured])
        remixers = self.get_tag(ID3Tag.REMIXER)
        remixers = [] if remixers is None else remixers.split(', ')
        genre = self.get_tag(ID3Tag.GENRE)
        label = self.get_tag(ID3Tag.LABEL)
        label = None if label is None else label.lower().strip()
        bpm = self.get_tag(ID3Tag.BPM)
        key = self.format_key()
        key = None if key is None else key[0].upper() + ''.join(key[1:])
        camelot_code = self.format_camelot_code()
        energy = self.format_energy()
        date_added = self.get_date_added()

        return self.TrackMetadata(title, artists, remixers, genre, label, bpm, key, camelot_code, energy, date_added)

    def get_date_added(self):
        """ Returns when track was added to collection (Unix timestamp). """
        return ctime(stat(self.track_path).st_birthtime)

    def get_id3_data(self):
        """ Returns dictionary mapping ID3 tags to values. """
        return self.id3_data

    def get_tag(self, tag):
        """ Returns value of the given ID3 tag."""
        return self.id3_data.get(tag.value)

    def get_track_path(self):
        """ Returns path to the track's file."""
        return self.track_path

    def _extract_id3_data(self):
        """ Extracts mp3 metadata using the eyed3 lib. """

        md = load(self.track_path)
        if md is None:
            return {}

        md = md.tag
        frame_types = {frames.TextFrame, frames.CommentFrame, frames.UserTextFrame}
        track_frames = list(md.frameiter())
        id3 = {frame.id.decode('utf-8'): frame.text for frame in filter(lambda t: type(t) in frame_types, track_frames)}

        return defaultdict(str, {k: id3[k] for k in list(filter(lambda k: k in ALL_ID3_TAGS, id3.keys()))})
