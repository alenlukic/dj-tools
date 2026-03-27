from src.db import database
from src.models.track import Track
from src.data_management.service import sync_track_fields
from src.errors import handle


def sync_fields():
    session = database.create_session()

    try:
        tracks = session.query(Track).all()
        sync_track_fields(tracks)
        session.commit()
    except Exception as e:
        handle(e, "Top-level exception occurred while syncing track fields")
        session.rollback()
    finally:
        session.close()


if __name__ == "__main__":
    sync_fields()
