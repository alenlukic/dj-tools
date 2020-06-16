from ast import literal_eval
from unicodedata import normalize

from src.definitions.data_management import *
from src.utils.common import is_empty


def get_canonical_form(segment, canon):
    """
    Get canonical entity form.

    :param segment: Text segment.
    :param canon: Mapping of aliases to canonical names.
    """
    return (canon.get(segment, ' '.join([ss.capitalize() for ss in segment.split()])
            if re.match(PAREN_REGEX, segment) is None else segment))


def transform_segments(segments, canon):
    """
    Get canonical entity forms for all segments.

    :param segments: Text segments.
    :param canon: Mapping of aliases to canonical names.
    """
    return [get_canonical_form(seg, canon) for seg in segments]


def transform_parens(segment, canon):
    """
    Get canonical entity forms for text embedded in parentheses.

    :param segment: Paranthetical segment.
    :param canon: Mapping of aliases to canonical names.
    """
    phrase = segment[1:-1]
    return segment.upper() if len(phrase) == 2 else '(' + ' '.join(transform_segments(phrase.split(), canon)) + ')'


def dedupe_title(title):
    """
    Remove repetitions from the given title.

    :param title: Title to dedupe.
    """

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
    return [] if is_empty(artists) else [a.strip() for a in artists.split(',') if not is_empty(a)]


def transform_artist(artist):
    """
    Applies artist-specific transformation rules to standardize artist names across the board.

    :param artist: Artist string to transform.
    """

    if 'Kamaya Painters' in artist:
        return 'Kamaya Painters'

    if artist in {'Tiësto', 'DJ Tiësto', 'DJ Tiesto'}:
        return 'Tiesto'

    return artist


def transform_genre(genre):
    """
    Applies genre-specific transformation rules to standardize genre names across the board.

    :param genre: Genre string to transform.
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

    :param label: Label string to transform.
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


def normalize_tag_text(text):
    """
    Normalizes ID3 tag text into ASCII to circumvent persistence issues.

    :param text: Original ID3 tag text.
    """
    return normalize('NFKD', text).encode('ascii', 'ignore').decode('ascii') if type(text) == str else text


def load_comment(comment_string, default=None):
    """

    :param comment_string:
    :param default:
    """
    try:
        return literal_eval(comment_string)
    except Exception:
        try:
            return literal_eval(default)
        except Exception:
            return {}

