from ast import literal_eval
from collections import ChainMap
from os import path, stat
from time import ctime
from unicodedata import normalize

import mutagen
from mutagen.id3 import TIT2, TCON, TBPM, TKEY, TPUB, COMM

from src.definitions.data_management import *
from src.utils.data_management import *


class AudioFile:
    """ Encapsulates an audio file and its metadata. """

    def __init__(self, full_path):
        """
        Constructor. Reads ID3 tags and generates metadata.

        :param full_path: Qualified path to the file on disk.
        """

        self.full_path = full_path
        self.basename = path.basename(full_path)
        self.id3 = self.read_id3()
        self.tags = self.read_tags()
        self.metadata = None

    def generate_metadata(self):
        """ Generates audio metadata. """

        bpm = self.format_bpm()
        key = self.format_key()
        camelot_code = self.format_camelot_code(key)
        key = key.capitalize()
        title = dedupe_title(self.generate_title(camelot_code, key, bpm).strip())

        metadata = {
            TrackDBCols.FILE_PATH.value: self.full_path,
            TrackDBCols.TITLE.value: title,
            TrackDBCols.BPM.value: int(bpm),
            TrackDBCols.KEY.value: key,
            TrackDBCols.CAMELOT_CODE.value: camelot_code,
            TrackDBCols.ENERGY.value: self.parse_energy(),
            TrackDBCols.GENRE.value: transform_genre(self.get_tag(ID3Tag.GENRE, '')),
            TrackDBCols.LABEL.value: transform_label(self.get_tag(ID3Tag.LABEL, '')),
            TrackDBCols.DATE_ADDED.value: ctime(stat(self.full_path).st_birthtime)
        }
        metadata = {k: v for k, v in metadata.items() if not is_empty(v)}

        comment = {k: v for k, v in dict(ChainMap(
            {k: v for k, v in metadata.items()},
            {
                ArtistFields.ARTISTS.value: self.get_tag(ID3Tag.ARTIST),
                ArtistFields.REMIXERS.value: self.get_tag(ID3Tag.REMIXER)
            }
        )).items() if not is_empty(v)}
        metadata[TrackDBCols.COMMENT.value] = str(comment)

        return metadata

    # =====================
    # Title-related methods
    # =====================

    def generate_title(self, camelot_code, key, bpm):
        """
        Generates track title.

        :param camelot_code: Track's Camelot Code.
        :param key: Track's key.
        :param bpm: Track's BPM.
        """

        parsed_title, featured = self.parse_title()
        title_prefix = self.generate_title_prefix(camelot_code, key, bpm)
        artist_midfix = self.format_artist_string(featured) + ('' if featured is None else ' ft. ' + featured)

        return title_prefix + ' ' + artist_midfix + ' - ' + parsed_title

    def generate_title_prefix(self, camelot_code, key, bpm):
        """
        Generates title prefix metadata.

        :param camelot_code: Track's Camelot Code.
        :param key: Track's key.
        :param bpm: Track's BPM.
        """
        return ' - '.join(['[' + camelot_code, key, bpm + ']'])

    def format_artist_string(self, featured):
        """
        Generate formatted artist string (first segment of artist midfix in track title).

        :param featured: Featured artist on the track (if any).
        """
        artists = self.get_tag(ID3Tag.ARTIST)
        featured_set = set() if featured is None else {transform_artist(featured)}
        filtered_artists = [transform_artist(a) for a in split_artist_string(artists) if a not in featured_set]

        # If any artist names contain "&" then we want to use "and" to separate artist names in the title, for clarity.
        # TODO: handle artist aliases
        separator = ' and ' if any('&' in artist for artist in filtered_artists) else ' & '
        return separator.join(filtered_artists)

    def parse_title(self):
        """ Parses track title and returns formatted track title and featured artist name, if any. """

        title = self.get_tag(ID3Tag.TITLE, '')
        segments = [seg.strip() for seg in title.split(' ') if not is_empty(seg.strip())]

        i = 0
        n = len(segments)
        featured = None
        in_parens = False
        filtered_segments = []
        while i < n:
            segment = segments[i]

            if '(' in segment:
                in_parens = True

            if ')' in segment and '(' not in segment:
                in_parens = False

            # Replace all instances of 'feat.' with 'ft.' inside the parenthetical phrase indicating mix type.
            # Ex: "(Hydroid feat. Santiago Nino Mix)" becomes "(Hydroid ft. Santiago Nino Mix)."
            segment_lowercase = segment.lower()
            if segment_lowercase == 'feat.' or segment_lowercase == 'ft.':
                if in_parens:
                    filtered_segments.append('ft.')
                    i += 1
                else:
                    # If we haven't seen an open parentheses yet, assume featured artist's name
                    # is composed of all words occuring before the parentheses and after 'ft.'
                    featured = []
                    for j in range(i + 1, n):
                        next_part = segments[j]
                        if '(' in next_part:
                            break
                        featured.append(next_part)
                    featured = ' '.join(featured)

                    if j == n - 1:
                        break
                    i = j

            else:
                filtered_segments.append(segment)
                i += 1

            if ')' in segment:
                in_parens = False

        # Get rid of the "(Original Mix)" and "(Extended Mix)" redundant suffixes.
        formatted_title = ' '.join(filtered_segments).replace('(Original Mix)', '').replace('(Extended Mix)', '')

        return formatted_title, featured

    # =======================
    # Feature-related methods
    # =======================

    def parse_energy(self):
        """ Parse track energy (if any) from the comment tag. """

        comment_tags = [ID3Tag.COMMENT, ID3Tag.USER_COMMENT, ID3Tag.COMMENT_ENG]
        for tag in comment_tags:
            try:
                comment = self.get_tag(tag)

                if comment is None:
                    continue

                if comment.isnumeric():
                    return int(comment)

                if comment.startswith('Energy'):
                    segments = [s.strip() for s in comment.split()]
                    return int(segments[1])

                if comment.startswith('Metadata: ') or comment.startswith('{'):
                    track_metadata = (literal_eval(comment) if comment.startswith('{')
                                      else literal_eval(comment.split('Metadata: ')[1]))
                    return int(track_metadata.get('Energy', ''))

            except Exception:
                continue

        return None

    def format_bpm(self):
        """ Format BPM value as padded 3-digit representation. """
        bpm = self.get_tag(ID3Tag.BPM, '')
        return ''.join([str(0)] * max(3 - len(bpm), 0)) + bpm

    def format_key(self):
        """ Formats track key as canonical representation. """
        return CANONICAL_KEY_MAP.get(self.get_tag(ID3Tag.KEY, '').lower(), '')

    def format_camelot_code(self, formatted_key):
        """ Formats Camelot code based on track key. """
        return CAMELOT_MAP.get(formatted_key, '')

    # =======
    # Getters
    # =======

    def get_basename(self):
        """ Return file base name. """
        return self.basename

    def get_metadata(self):
        """ Return track's metadata dict. """
        if self.metadata is None:
            self.metadata = self.generate_metadata()
        return self.metadata

    def get_tag(self, tag, default=None):
        """
        Return specified tag's value.

        :param tag: Tag whose value to return.
        :param default: Default value to return if tag value not present.
        """

        try:
            tag_val = tag.value
        except Exception:
            tag_val = tag

        if self.tags.get(tag_val, '') == '':
            tag_val = self.get_synonym_with_value(tag_val)

        return self.tags.get(tag_val, default)

    def get_synonym_with_value(self, tag):
        """
        If given tag not present in tag set, try to find a synonymous tag's value.

        :param tag: Missing tag.
        """

        syns = [syn for syn in ID3_SYNONYMS.get(tag, []) if self.tags.get(syn, '') != '']
        if len(syns) == 0:
            return tag

        return syns[0]

    def get_tags(self):
        """ Gets ID3 tag dict. """
        return self.tags

    # ===================
    # ID3-related methods
    # ===================

    def read_id3(self):
        """ Read ID3 data from file. """

        id3 = mutagen.File(self.full_path)
        if id3 is None:
            raise Exception('Could not load ID3 data for %s' % self.full_path)

        return id3

    def read_tags(self):
        """ Read relevant tags from ID3 data. """
        id3_tags = self.id3.items()
        td = {k: v for k, v in id3_tags if getattr(v, 'text', None) is not None}.items()
        return ChainMap(
            {k: ''.join([str(t) for t in v.text]) if len(v.text) > 1 else v.text[0] for k, v in td},
            {k: getattr(id3_tags[k], 'text', [''])[0] if k in id3_tags else '' for k in ALL_ID3_TAGS}
        )

    def write_tag(self, tag, value, save=True):
        """
        Write value to specified ID3 tag.

        :param tag: Tag to write to.
        :param value: Tag value.
        :param save: Whether tag value should be saved to file immediately.
        """

        text = [normalize('NFKD', value).encode('ascii', 'ignore').decode('ascii') if type(value) == str else value]

        if tag in self.id3.keys():
            if tag in ID3_SYNONYMS[ID3Tag.COMMENT.value]:
                comm_tags_to_delete = [et for et in self.id3.keys() if et.startswith('COMM')]
                for ct in comm_tags_to_delete:
                    del self.id3[ct]
                self.id3[ID3Tag.COMMENT.value] = COMM(text=text)
            else:
                self.id3[tag].text = text

        elif tag in ALL_ID3_TAGS:
            if tag == ID3Tag.TITLE.value:
                self.id3[tag] = TIT2(text=text)
            elif tag == ID3Tag.GENRE.value:
                self.id3[tag] = TCON(text=text)
            elif tag == ID3Tag.BPM.value:
                self.id3[tag] = TBPM(text=text)
            elif tag == ID3Tag.KEY.value:
                self.id3[tag] = TKEY(text=text)
            elif tag == ID3Tag.LABEL.value:
                self.id3[tag] = TPUB(text=text)
            elif tag == ID3Tag.COMMENT.value or tag == ID3Tag.COMMENT_ENG.value:
                self.id3[ID3Tag.COMMENT.value] = COMM(text=text)

        if save:
            self.id3.save()

    def write_tags(self, tags_to_write=None):
        """
        Writes metadata to ID3 tags and saves to file.

        :param tags_to_write: (optional) Dictionary mapping tag to value which should be written.
        """

        track_metadata = tags_to_write or self.get_metadata()
        for k, v in track_metadata.items():
            mk = METADATA_KEY_TO_ID3.get(k)
            syn = self.get_synonym_with_value(mk)
            if syn is not None:
                self.write_tag(syn, v, False)

        self.id3.save()

    def save_tags(self):
        """ Save ID3 tag values to file. """
        self.id3.save()
