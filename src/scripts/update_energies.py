from src.db import database
from src.db.entities.track import Track
from src.definitions.data_management import TrackDBCols
from src.tools.data_management.audio_file import AudioFile
from src.utils.errors import handle_error


def update_energies():
    session = database.create_session()
    errors = False
    try:
        tracks = session.query(Track).filter_by(energy=None)
        for track in tracks:
            af = AudioFile(track.file_path)
            md = af.get_metadata()
            track.energy = md.get(TrackDBCols.ENERGY.value)
    except Exception as e:
        errors = True
        handle_error(e)
    finally:
        if errors:
            session.rollback()
        else:
            session.commit()


if __name__ == '__main__':
    update_energies()
