from os.path import join
import sys

from src.definitions.common import PROCESSED_MUSIC_DIR, TMP_MUSIC_DIR
from src.tools.data_management.data_manager import DataManager


def ingest_tracks(dm, upsert=False):
    """
    Migrates tracks in temp directories to permanent collection.

    :param dm: The data manager class which contains the track migration logic.
    :param upsert: (optional) When True, will attempt to update existing DB rows rather than creating new ones.
    """

    kwargs = {
        'target_dir': PROCESSED_MUSIC_DIR,
        'upsert': upsert
    }
    dm.ingest_tracks(join(TMP_MUSIC_DIR, 'mp3'), **kwargs)
    dm.ingest_tracks(join(TMP_MUSIC_DIR, 'lossless'), **kwargs)


if __name__ == '__main__':
    upsert_tracks = False

    if len(sys.argv) == 2:
        upsert_arg = sys.argv[1].lower().strip()

        if upsert_arg == 'true':
            upsert_tracks = True

        elif upsert_arg != 'false':
            print('Valid values for upsert are only true, false or not provided (default: false')
            sys.exit(1)

    elif len(sys.argv) > 2:
        print('Too many arguments')
        sys.exit(1)

    ingest_tracks(DataManager(), upsert_tracks)
