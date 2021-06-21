from src.db import database
from src.db.entities.track import Track
from src.lib.data_management.data_manager import DataManager
from src.lib.error_management.reporting_handler import handle


def sync_tags():
    session = database.create_session()

    try:
        tracks = session.query(Track).all()
        DataManager.sync_track_tags(tracks)
        session.commit()
    except Exception as e:
        handle(e, 'Top-level exception occurred while syncing track tags')
        session.rollback()
    finally:
        session.close()


if __name__ == '__main__':
    sync_tags()
