import re

from src.definitions.data_management import BAR_REGEX, MD_COMPOSITE_REGEX, PAREN_REGEX
from src.utils.common import is_empty


GENRE_CANON = {
    'Psy-Trance': 'Psytrance',
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


def get_canonical_form(segment, canon):
    return (canon.get(segment, ' '.join([ss.capitalize() for ss in segment.split()])
            if re.match(PAREN_REGEX, segment) is None else segment))


def transform_segments(segments, canon):
    return [get_canonical_form(seg, canon) for seg in segments]


def transform_parens(segment, canon):
    phrase = segment[1:-1]
    return segment.upper() if len(phrase) == 2 else '(' + ' '.join(transform_segments(phrase.split(), canon)) + ')'


def dedupe_title(title):
    """ TODO. """

    if title is None:
        return title

    md_matches = re.findall(MD_COMPOSITE_REGEX, title)
    if len(md_matches) > 0:
        md_match = md_matches[0]
        return md_match + title.split(md_match)[-1]

    return title

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


def transform_genre(genre):
    """
    Applies genre-specific transformation rules to standardize genre names across the board.

    :param genre: Genre string to transform
    """

    bar_matches = re.findall(BAR_REGEX, genre)
    if len(bar_matches) > 0:
        bar_split = genre.split('|')
        parent_genre = bar_split[0].strip()

        if parent_genre == 'House':
            return ' '.join([g.strip() for g in bar_split[1].strip().split()])

        if parent_genre == 'Trance' and bar_split[1].strip() == 'psytrance':
            return 'Psytrance'

        return parent_genre

    paren_matches = re.findall(PAREN_REGEX, genre)
    if len(paren_matches) > 0:
        return genre.split(paren_matches[0])[0]

    return get_canonical_form(genre, GENRE_CANON)


def transform_label(label):
    """
    Applies label-specific transformation rules to standardize label names across the board.

    :param label: Label string to transform
    """

    parent_label_parens = {'(Armada)', '(Armada Music)', '(Spinnin)'}
    for pl in parent_label_parens:
        if pl in label:
            return label.split(pl)[0].strip()

    label_lower = label.lower()
    if 'hommega' in label_lower:
        return 'HOMmega Productions'

    if 'pure trance' in label_lower and label_lower != 'pure trance progressive':
        return 'Pure Trance Recordings'

    paren_matches = re.findall(PAREN_REGEX, label_lower)
    if len(paren_matches) == 0:
        transformed_segments = transform_segments([lp.strip() for lp in label_lower.split()], LABEL_CANON)
    else:
        paren_match = paren_matches[0]
        paren_begin = label_lower.index(paren_match)
        paren_end = paren_begin + len(paren_match)

        pre_segments = transform_segments([lp.strip() for lp in label_lower[0:paren_begin].split()], LABEL_CANON)
        parens = [transform_parens(label_lower[paren_begin:paren_end], LABEL_CANON)]
        post_segments = ([] if paren_end == len(label_lower) - 1 else
                         [lp.strip() for lp in label_lower[paren_end:].split()])
        post_segments = transform_segments(post_segments, LABEL_CANON)

        transformed_segments = pre_segments + parens + post_segments

    return ' '.join([seg.strip() for seg in transformed_segments])
