from src.db import database
import src.lib.data_management.service as data_service
from src.lib.error_management.service import handle

def migrate():
    # TODO: finish
    session = database.create_session()
    tracks = data_service.load_tracks(session)

    for track in tracks:
        try:
            file_name = track.file_path.split('/')[-1]
            track.file_path = file_name
            session.commit()
        except Exception as e:
            handle(e, 'Error trying to update file_path for %s' % track.file_path)
            continue


if __name__ == '__main__':
    migrate()
