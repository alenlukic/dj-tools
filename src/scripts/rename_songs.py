from os.path import join

from src.definitions.common import TMP_MUSIC_DIR
from src.tools.data_management.data_manager import DataManager


if __name__ == '__main__':
    dm = DataManager()
    dm.rename_songs(join(TMP_MUSIC_DIR, 'mp3'))
    dm.rename_songs(join(TMP_MUSIC_DIR, 'lossless'))
