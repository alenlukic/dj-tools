from ast import literal_eval
from os.path import join

from src.db import database
from src.definitions.common import PROCESSED_MUSIC_DIR
from src.db.entities.track import Track as TrackEntity
from src.definitions.data_management import ID3Tag
from src.tools.data_management.track import Track
from src.utils.file_operations import get_audio_files


def update_energy_column():
    """ Update energy column in track table. """

    session = database.create_session()
    errors = False

    for base_path in get_audio_files():
        try:
            track_path = join(PROCESSED_MUSIC_DIR, base_path)
            track = session.query(TrackEntity).filter_by(file_path=track_path).first()
            if track.energy is not None:
                continue

            track_wrapper = Track(track_path)
            energy = track_wrapper.get_tag(ID3Tag.ENERGY)
            if energy is None:
                comment = literal_eval(track_wrapper.get_tag(ID3Tag.COMMENT) or '{}')
                energy = comment.get('Energy', '')

            if energy.isnumeric():
                track.energy = int(energy)

        except Exception as e:
            print('Error processing %s: %s' % (track_path, str(e)))
            errors = True
            continue

    if not errors:
        session.commit()
    database.close_all_sessions()


if __name__ == '__main__':
    update_energy_column()
