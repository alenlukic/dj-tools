from enum import Enum
import re


class DBUpdateType(Enum):
    INSERT = 'Insert'
    UPDATE = 'Update'
    DELETE = 'Delete'
    FAILURE = 'Failure'
    NOOP = 'No-Op'


class ID3Tag(Enum):
    TITLE = 'TIT2'
    ARTIST = 'TPE1'
    REMIXER = 'TPE4'
    GENRE = 'TCON'
    BPM = 'TBPM'
    KEY = 'TKEY'
    LABEL = 'TPUB'
    USER_COMMENT = 'TXXX'
    ENERGY = 'TXXX:EnergyLevel'
    COMMENT = 'COMM'
    COMMENT_XXX = 'COMM::XXX'
    COMMENT_ENG = 'COMM::eng'
    BEATPORT = 'TENC'


class TrackDBCols(Enum):
    ID = 'id'
    FILE_PATH = 'file_path'
    TITLE = 'title'
    BPM = 'bpm'
    KEY = 'key'
    CAMELOT_CODE = 'camelot_code'
    ENERGY = 'energy'
    GENRE = 'genre'
    LABEL = 'label'
    DATE_ADDED = 'date_added'
    COMMENT = 'comment'


class ArtistFields(Enum):
    ARTISTS = 'artists'
    REMIXERS = 'remixers'


COMMENT_FIELDS = set([c.value for c in TrackDBCols if not (c == TrackDBCols.ID or c == TrackDBCols.COMMENT)])

ID3_COMMENT_FIELDS = set([c.value for c in [TrackDBCols.TITLE, TrackDBCols.BPM, TrackDBCols.KEY, TrackDBCols.GENRE,
                                            TrackDBCols.LABEL, TrackDBCols.COMMENT]])

METADATA_KEY_TO_ID3 = {
    TrackDBCols.TITLE.value: ID3Tag.TITLE.value,
    TrackDBCols.BPM.value: ID3Tag.BPM.value,
    TrackDBCols.KEY.value: ID3Tag.KEY.value,
    TrackDBCols.ENERGY.value: ID3Tag.ENERGY.value,
    TrackDBCols.GENRE.value: ID3Tag.GENRE.value,
    TrackDBCols.LABEL.value: ID3Tag.LABEL.value,
    TrackDBCols.COMMENT.value: ID3Tag.COMMENT.value,
    ArtistFields.ARTISTS.value: ID3Tag.ARTIST.value,
    ArtistFields.REMIXERS.value: ID3Tag.REMIXER.value
}

ID3_TAG_SYNONYMS = {
    ID3Tag.COMMENT.value: [ID3Tag.COMMENT.value, ID3Tag.COMMENT_XXX.value, ID3Tag.COMMENT_ENG.value],
    ID3Tag.COMMENT_XXX.value: [ID3Tag.COMMENT.value, ID3Tag.COMMENT_XXX.value, ID3Tag.COMMENT_ENG.value],
    ID3Tag.COMMENT_ENG.value: [ID3Tag.COMMENT.value, ID3Tag.COMMENT_XXX.value, ID3Tag.COMMENT_ENG.value],
}

ALL_TRACK_DB_COLS = set([c.value for c in TrackDBCols])

TRACK_MD_ID3_TAGS = set([t.value for t in ID3Tag])

REQUIRED_ID3_TAGS = {ID3Tag.TITLE.value, ID3Tag.ARTIST.value, ID3Tag.BPM.value, ID3Tag.KEY.value, ID3Tag.ENERGY.value}

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

GENRE_CANON = {
    'Psy-Trance': 'Psytrance'
}

LABEL_CANON = {
    'joof': 'JOOF',
    'shinemusic': 'Shine Music',
    'vii': 'VII',
    'rfr': 'RFR',
    'cdr': 'CDR',
    'knm': 'KNM',
    'umc': 'UMC',
    'uv': 'UV',
    'nx1': 'NX1',
    'srx': 'SRX',
    'kgg': 'KGG',
    'dpe': 'DPE',
    'kmx': 'KMX',
    'dbx': 'DBX',
    'x7m': 'X7M',
    'cr2': 'CR2',
    'dfc': 'DFC',
    'kd': 'KD',
    'tk': 'TK',
    'uk': 'UK',
    'l.i.e.s.': 'L.I.E.S.',
    'n.a.m.e': 'N.A.M.E',
    'd.o.c.': 'D.O.C.'
}

BAR_REGEX = re.compile(r'.*?\|')

MD_COMPOSITE_REGEX = re.compile(r'\[\d{2}[AB]\s-\s[A-Za-z#]{1,3}\s-\s\d{3}\]')

MD_SPLIT_REGEX = re.compile(r'\[(\d{2}[AB])\s-\s([A-Za-z#]{1,3})\s-\s(\d{3})\]')

PAREN_REGEX = re.compile(r'\(.*\)')

GD_TIMESTAMP_FORMAT = '%Y-%m-%dT%H:%M:%S.%fZ'
