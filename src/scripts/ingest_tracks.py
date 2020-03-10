from os.path import join
import sys

from src.db import database
from src.db.entities.track import Track
from src.definitions.common import PROCESSED_MUSIC_DIR, TMP_MUSIC_DIR
from src.tools.data_management.data_manager import DataManager
from src.utils.errors import handle_error


def ingest_tracks(dm, upsert=False):
    """
    Migrates tracks in temp directories to permanent collection.

    :param dm: The data manager class which contains the track migration logic.
    :param upsert: (optional) When True, will attempt to update existing DB rows rather than creating new ones.
    """

    try:
        kwargs = {
            'target_dir': PROCESSED_MUSIC_DIR,
            'upsert': upsert
        }
        dm.ingest_tracks(join(TMP_MUSIC_DIR, 'mp3'), **kwargs)
        dm.ingest_tracks(join(TMP_MUSIC_DIR, 'lossless'), **kwargs)

        if not upsert:
            session = database.create_session()

            try:
                tracks = session.query(Track).all()
                dm.sync_track_fields(tracks)
                session.commit()

            except Exception as e:
                handle_error(e, 'Exception occurred trying to sync tracks post-ingest')
                session.rollback()

            finally:
                session.close()

    except Exception as e:
        handle_error(e, 'Exception occurred trying to ingest tracks')
        return


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
