from os.path import join

from src.db import database
from src.definitions.common import PROCESSED_MUSIC_DIR
from src.db.entities.track import Track
from src.definitions.data_management import ID3Tag
from src.tools.data_management.data_manager import DataManager
from src.utils.file_operations import get_audio_files


def update_comment_column():
    """ Create (if it doesn't exist) and update comment column in track table. """

    database.add_column('track', 'comment')
    dm = DataManager()
    session = database.create_session()
    errors = False

    for base_path in get_audio_files():
        try:
            track_path = join(PROCESSED_MUSIC_DIR, base_path)
            track_metadata = dm.generate_track_metadata(track_path)
            track_metadata.write_tags(track_path, [ID3Tag.COMMENT.value])

            track = session.query(Track).filter_by(file_path=track_path).first()
            track.comment = str(track_metadata.get_metadata())
        except Exception as e:
            print('Error processing %s: %s' % (track_path, str(e)))
            errors = True
            continue

    if not errors:
        session.commit()
    database.close_all_sessions()


if __name__ == '__main__':
    update_comment_column()