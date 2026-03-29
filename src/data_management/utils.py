import re
from ast import literal_eval
from unicodedata import normalize

from src.data_management.config import (
    BAR_REGEX,
    MD_COMPOSITE_REGEX,
    PAREN_REGEX,
    SPECIAL_FILENAME_CHARS,
)
from src.data_management.mapping_registry import MappingRegistry
from src.utils.common import is_empty


def get_canonical_form(segment, canon):
    return canon.get(
        segment,
        " ".join([ss.capitalize() for ss in segment.split()])
        if re.match(PAREN_REGEX, segment) is None
        else segment,
    )


def transform_segments(segments, canon):
    return [get_canonical_form(seg, canon) for seg in segments]


def transform_parens(segment, canon):
    phrase = segment[1:-1]
    return (
        segment.upper()
        if len(phrase) == 2
        else "(" + " ".join(transform_segments(phrase.split(), canon)) + ")"
    )


def dedupe_title(title):
    if title is None:
        return title

    md_matches = re.findall(MD_COMPOSITE_REGEX, title)
    if len(md_matches) > 0:
        md_match = md_matches[0]
        return md_match + title.split(md_match)[-1]

    return title


def split_artist_string(artists):
    return (
        []
        if is_empty(artists)
        else [a.strip() for a in artists.split(",") if not is_empty(a)]
    )


def transform_artist(artist):
    for raw, canonical in MappingRegistry.artist_contains():
        if raw in artist:
            return canonical
    return MappingRegistry.artist_exact().get(artist, artist)


def transform_genre(genre):
    bar_matches = re.findall(BAR_REGEX, genre)
    if len(bar_matches) > 0:
        bar_split = genre.split("|")
        parent_genre = bar_split[0].strip()

        if parent_genre == "House":
            return " ".join([g.strip() for g in bar_split[1].strip().split()])

        if parent_genre == "Trance" and bar_split[1].strip() == "psytrance":
            return "Psytrance"

        return parent_genre

    paren_matches = re.findall(PAREN_REGEX, genre)
    if len(paren_matches) > 0:
        return genre.split(paren_matches[0])[0]

    return get_canonical_form(genre, MappingRegistry.genre_exact())


def transform_label(label):
    for suffix in MappingRegistry.label_strip_suffix():
        if suffix in label:
            return label.split(suffix)[0].strip()

    label_lower = label.lower()
    for raw, canonical, exclude_pattern in MappingRegistry.label_substring():
        if raw in label_lower:
            if exclude_pattern and label_lower == exclude_pattern:
                continue
            return canonical

    paren_matches = re.findall(PAREN_REGEX, label_lower)
    label_word = MappingRegistry.label_word()

    if len(paren_matches) == 0:
        transformed_segments = transform_segments(
            [lp.strip() for lp in label_lower.split()], label_word
        )
    else:
        paren_match = paren_matches[0]
        paren_begin = label_lower.index(paren_match)
        paren_end = paren_begin + len(paren_match)

        pre_segments = transform_segments(
            [lp.strip() for lp in label_lower[0:paren_begin].split()], label_word
        )
        parens = [transform_parens(label_lower[paren_begin:paren_end], label_word)]
        post_segments = (
            []
            if paren_end == len(label_lower) - 1
            else [lp.strip() for lp in label_lower[paren_end:].split()]
        )
        post_segments = transform_segments(post_segments, label_word)
        transformed_segments = pre_segments + parens + post_segments

    return " ".join([seg.strip() for seg in transformed_segments])


def normalize_tag_text(text):
    return (
        normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
        if type(text) == str
        else text
    )


def load_comment(comment_string, default=None):
    try:
        return literal_eval(comment_string)
    except Exception:
        try:
            return literal_eval(default)
        except Exception:
            return {}


def extract_unformatted_title(formatted_title):
    if re.match(MD_COMPOSITE_REGEX, formatted_title) is None:
        return formatted_title

    md_title_split = MD_COMPOSITE_REGEX.split(formatted_title)
    title = md_title_split[-1].strip()
    title = " - ".join(title.split(" - ")[1:])

    return title


def format_track_title(unformatted_title):
    formatted_title = unformatted_title
    for c in SPECIAL_FILENAME_CHARS:
        formatted_title = formatted_title.replace(c, "_")

    return formatted_title
