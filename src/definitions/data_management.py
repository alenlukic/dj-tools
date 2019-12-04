from enum import Enum
import re


class ID3Tag(Enum):
    TITLE = 'TIT2'
    ARTIST = 'TPE1'
    REMIXER = 'TPE4'
    GENRE = 'TCON'
    BPM = 'TBPM'
    KEY = 'TKEY'
    USER_COMMENT = 'TXXX'
    LABEL = 'TPUB'
    COMMENT = 'COMM'
    BEATPORT = 'TENC'


class CustomTag(Enum):
    FEATURED = 'FEATURED'
    CAMELOT_CODE = 'CAMELOT_CODE'
    TRACK_NAME = 'TRACK_NAME'
    ENERGY = 'ENERGY'


READABLE_TO_ID3 = {
    'Title': ID3Tag.TITLE.value,
    'Artists': ID3Tag.ARTIST.value,
    'Remixers': ID3Tag.REMIXER.value,
    'Genre': ID3Tag.GENRE.value,
    'BPM': ID3Tag.BPM.value,
    'Key': ID3Tag.KEY.value,
    'User Comment': ID3Tag.USER_COMMENT.value,
    'Label': ID3Tag.LABEL.value,
    'Comment': ID3Tag.COMMENT.value
}

ALL_ID3_TAGS = set([t.value for t in ID3Tag])

REQUIRED_ID3_TAGS = {ID3Tag.TITLE.value, ID3Tag.ARTIST.value, ID3Tag.BPM.value, ID3Tag.KEY.value}

UNSUPPORTED_ID3_TAGS = {'GRP1'}

KEYS_TO_OMIT_FROM_MD_UPDATES = {'Artists', 'Remixers'}

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
