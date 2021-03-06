from src.db import database
from src.db.entities.track import Track
from src.lib.data_management.data_manager import DataManager
from src.utils.errors import handle_error


def sync_fields():
    session = database.create_session()
    dm = DataManager()

    try:
        tracks = session.query(Track).all()
        dm.sync_track_fields(tracks)
        session.commit()
    except Exception as e:
        handle_error(e, 'Top-level exception occurred while syncing track fields')
        session.rollback()
    finally:
        session.close()


if __name__ == '__main__':
    sync_fields()
