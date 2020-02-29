from src.utils.common import is_empty


def split_artist_string(artists):
    """
    TODO.
    :param artists:
    :return:
    """
    if is_empty(artists):
        return []
    return [a.strip() for a in artists.split(',')]
