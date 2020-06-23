from os.path import join

from src.db import database
from src.db.entities.track import Track
from src.definitions.common import TMP_MUSIC_DIR
from src.tools.data_management.data_manager import DataManager
from src.utils.errors import handle_error


def ingest_tracks(dm):
    """
    Migrates tracks in temp directories to permanent collection.

    :param dm: The data manager class which contains the track migration logic.
    """

    try:
        dm.ingest_tracks(join(TMP_MUSIC_DIR, 'mp3'))
        dm.ingest_tracks(join(TMP_MUSIC_DIR, 'lossless'))

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
    ingest_tracks(DataManager())
