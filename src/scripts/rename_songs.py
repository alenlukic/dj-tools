from os.path import join

from src.definitions.common import TMP_MUSIC_DIR
from src.tools.data_management.data_manager import DataManager


def rename_songs(dm):
    # dm.rename_songs(join(TMP_MUSIC_DIR, 'mp3'))
    # dm.rename_songs(join(TMP_MUSIC_DIR, 'lossless'))

    kwargs = {
        'target_dir': None,
        'upsert': True
    }
    dm.rename_songs(join(TMP_MUSIC_DIR, 'test'), **kwargs)


if __name__ == '__main__':
    rename_songs(DataManager())
