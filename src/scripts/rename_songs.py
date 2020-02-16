from os.path import join

from src.definitions.common import PROCESSED_MUSIC_DIR, TMP_MUSIC_DIR
from src.tools.data_management.data_manager import DataManager


if __name__ == '__main__':
    dm = DataManager()
    dm.rename_songs(join(TMP_MUSIC_DIR, 'mp3'), PROCESSED_MUSIC_DIR, True)
    # dm.rename_songs(join(TMP_MUSIC_DIR, 'lossless'))
