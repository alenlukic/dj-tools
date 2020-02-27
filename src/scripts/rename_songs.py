from os.path import join

from src.definitions.common import TMP_MUSIC_DIR
from src.tools.data_management.data_manager import DataManager


def rename_songs(dm, upsert=False):
    """
    Migrates tracks in temp directories to permanent collection.

    :param dm: The data manager class which contains the track migration logic.
    :param upsert: (optional) When True, will attempt to update existing DB rows rather than creating new ones.
    """

    kwargs = {
        'target_dir': None,
        'upsert': upsert
    }
    dm.rename_songs(join(TMP_MUSIC_DIR, 'mp3'), **kwargs)
    dm.rename_songs(join(TMP_MUSIC_DIR, 'lossless'), **kwargs)


if __name__ == '__main__':
    rename_songs(DataManager())
