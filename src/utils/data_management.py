from src.utils.common import is_empty


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
