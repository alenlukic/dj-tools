from collections import defaultdict, ChainMap
from enum import Enum
from eyed3 import id3 as metadata, load
from os.path import getctime
import re
from time import ctime


from src.utils.utils import is_empty


class ID3Tag(Enum):
    TITLE = 'TIT2'
    ARTIST = 'TPE1'
    REMIXER = 'TPE4'
    GENRE = 'TCON'
    BPM = 'TBPM'
    KEY = 'TKEY'
    LABEL = 'TPUB'
    COMMENT = 'COMM'
    BEATPORT = 'TENC'


class CustomTag(Enum):
    FEATURED = 'FEATURED'
    CAMELOT_CODE = 'CAMELOT_CODE'
    TRACK_NAME = 'TRACK_NAME'
    ENERGY = 'ENERGY'


ALL_ID3_TAGS = set([t.value for t in ID3Tag])

REQUIRED_ID3_TAGS = {ID3Tag.TITLE, ID3Tag.ARTIST, ID3Tag.BPM, ID3Tag.KEY}

CANONICAL_KEY_MAP = {
    k.lower(): v.lower() for k, v in {
        # A keys
        'A': 'A',
        'Amaj': 'A',
        'Am': 'Am',
        'Amin': 'Am',
        'Ab': 'Ab',
        'Abmaj': 'Ab',
        'A#': 'Bb',
        'A#maj': 'Bb',
        'Abm': 'Abm',
        'Abmin': 'Abm',
        'A#m': 'Bbm',
        'A#min': 'Bbm',
        # B keys
        'B': 'B',
        'Bmaj': 'B',
        'Bm': 'Bm',
        'Bmin': 'Bm',
        'Bb': 'Bb',
        'Bbmaj': 'Bb',
        'Bbm': 'Bbm',
        'Bbmin': 'Bbm',
        # C keys
        'C': 'C',
        'Cmaj': 'C',
        'Cm': 'Cm',
        'Cmin': 'Cm',
        'C#': 'Db',
        'C#maj': 'Db',
        'C#m': 'C#m',
        'C#min': 'C#m',
        # D keys
        'D': 'D',
        'Dmaj': 'D',
        'Dm': 'Dm',
        'Dmin': 'Dm',
        'Db': 'Db',
        'Dbmaj': 'Db',
        'D#': 'Eb',
        'D#maj': 'Eb',
        'Dbm': 'C#m',
        'Dbmin': 'C#m',
        'D#m': 'Ebm',
        'D#min': 'Ebm',
        # E keys
        'E': 'E',
        'Emaj': 'E',
        'Em': 'Em',
        'Emin': 'Em',
        'Eb': 'Eb',
        'Ebmaj': 'Eb',
        'Ebm': 'Ebm',
        'Ebmin': 'Ebm',
        # F keys
        'F': 'F',
        'Fmaj': 'F',
        'Fm': 'Fm',
        'Fmin': 'Fm',
        'F#': 'F#',
        'F#maj': 'F#',
        'F#m': 'F#m',
        'F#min': 'F#m',
        # G keys
        'G': 'G',
        'Gmaj': 'G',
        'Gm': 'Gm',
        'Gmin': 'Gm',
        'Gb': 'F#',
        'Gbmaj': 'F#',
        'G#': 'Ab',
        'G#maj': 'Ab',
        'Gbm': 'F#m',
        'Gbmin': 'F#m',
        'G#m': 'Abm',
        'G#min': 'Abm'
    }.items()
}

CAMELOT_MAP = {
    'abm': '01A',
    'b': '01B',
    'ebm': '02A',
    'f#': '02B',
    'bbm': '03A',
    'db': '03B',
    'fm': '04A',
    'ab': '04B',
    'cm': '05A',
    'eb': '05B',
    'gm': '06A',
    'bb': '06B',
    'dm': '07A',
    'f': '07B',
    'am': '08A',
    'c': '08B',
    'em': '09A',
    'g': '09B',
    'bm': '10A',
    'd': '10B',
    'f#m': '11A',
    'a': '11B',
    'c#m': '12A',
    'e': '12B'
}

MD_FORMAT_REGEX = re.compile(r'\[(\d{2}[AB])\s-\s([A-Za-z#]{1,3})\s-\s(\d{3})\]')


class Track:
    """ Class encapsulating a track and its metadata. """
    def __init__(self, track_path):
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

        energy = self.formatted[CustomTag.ENERGY.value]
        if energy is not None:
            return energy

        comment = self.get_tag(ID3Tag.COMMENT) or ''
        if 'Energy' in comment:
            segment = [s.strip() for s in comment.split()][-1]
            energy = None if not segment.isnumeric() else int(segment)

        self.formatted[CustomTag.ENERGY.value] = energy

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

        title = self.format_title()
        artists, featured = self.format_artists()
        bpm = self.format_bpm()
        key = self.format_key()
        camelot_code = self.format_camelot_code()

        metadata_prefix = ' - '.join(['[' + camelot_code, key.capitalize(), bpm + ']'])
        artist_midfix = artists + (' ft. ' + '' if featured is None else featured)
        track_name = metadata_prefix + ' ' + artist_midfix + ' - ' + title
        self.formatted[CustomTag.TRACK_NAME] = track_name

        return track_name

    def get_date_added(self):
        """ Returns when track was added to collection (Unix timestamp). """
        return ctime(getctime(self.track_path))

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
        """ Extracts mp3 metadata needed to automatically rename songs using the eyed3 lib. """

        md = load(self.track_path)
        if md is None:
            return None

        frame_types = {metadata.frames.TextFrame, metadata.frames.CommentFrame}
        track_frames = md.tag.frameiter()
        id3 = {frame.id.decode('utf-8'): frame.text for frame in filter(lambda t: type(t) in frame_types, track_frames)}
        keys = list(filter(lambda k: k in ALL_ID3_TAGS, id3.keys()))

        return defaultdict(str, {k: id3[k] for k in keys})


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
        return {k: v for k, v in {
            'Title': self.title,
            'Artists': self.artists,
            'Remixers': self.remixers,
            'Genre': self.genre,
            'Label': self.label,
            'BPM': self.bpm,
            'Key': self.key,
            'Camelot Code': self.camelot_code,
            'Energy': self.energy,
            'Date Added': self.date_added
        }.items() if not is_empty(v)}
