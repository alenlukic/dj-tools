from src.db import database
from src.db.entities.track import Track


def update_wav_file_paths():
    """ Update file_path field for all .wav files to .aiff following the batch conversion. """

    session = database.create_session()
    tracks = list(filter(lambda t: t.file_path.endswith('.wav'), session.query(Track).all()))
    errors = False

    for track in tracks:
        file_path = track.file_path
        try:
            track.file_path = file_path.split('.wav')[0] + '.aiff'
        except Exception as e:
            print('Error processing %s: %s' % (file_path, str(e)))
            errors = True
            continue

    if not errors:
        session.commit()

    database.close_all_sessions()


if __name__ == '__main__':
    update_wav_file_paths()
