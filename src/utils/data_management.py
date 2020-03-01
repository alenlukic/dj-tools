from src.utils.common import is_empty

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

def split_artist_string(artists):
    """
    Splits a comma-separated artist string into a list of individual artists.

    :param artists: Artist string to split
    """
    return [] if is_empty(artists) else [a.strip() for a in artists.split(',')]


def transform_artist(artist):
    """
    Applies artist-specific transformation rules to standardize artist names across the board.

    :param artist: Artist string to transform
    """

    if 'Kamaya Painters' in artist:
        return 'Kamaya Painters'

    if artist in {'Tiësto', 'DJ Tiësto', 'DJ Tiesto'}:
        return 'Tiesto'

    return artist


def transform_label(label):
    """
    Applies label-specific transformation rules to standardize artist names across the board.

    :param artist: Artist string to transform
    :param label:
    :return:
    """
    return LABEL_CANON.get(label.lower(), label)
