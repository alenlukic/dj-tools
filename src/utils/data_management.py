from src.utils.common import is_empty


def split_artist_string(artists):
    """
    Splits a comma-separated artist string into a list of individual artists.

    :param artists: Artist string to split
    """
    return [] if is_empty(artists) else [a.strip() for a in artists.split(',')]
