from ast import literal_eval

from src.db import database
from src.db.entities.track import Track as TrackEntity
from src.definitions.data_management import METADATA_KEY_TO_ID3
from src.tools.data_management.formats.audio_file import AudioFile
from src.utils.common import is_empty
from src.utils.errors import handle_error


def standardize_tags():
    session = database.create_session()

    try:
        tracks = session.query(TrackEntity).all()
        progress = 0
        for track in tracks:
            if progress % 100 == 0:
                print('Processed %d tracks' % progress)

            # Get metadata values from DB
            file_path = track.file_path
            comment = {}
            try:
                comment = literal_eval(track.comment)
            except Exception as e:
                handle_error(e)

            updated_tag_values = {db_col: getattr(track, db_col, comment.get(db_col)) for db_col in METADATA_KEY_TO_ID3}
            updated_tag_values = {k: v for k, v in updated_tag_values.items() if not is_empty(v)}
            updated_tag_values['comment'] = str({k: v for k, v in updated_tag_values.items() if k != 'comment'})

            # Update tags
            try:
                track_model = AudioFile(file_path)
            except Exception:
                handle_error(e)
                continue

            for db_col, tag_value in updated_tag_values.items():
                if is_empty(tag_value):
                    continue
                track_model.write_tag(db_col, str(tag_value), False)

            track_model.save_id3()

            progress += 1

    except Exception as e:
        handle_error(e)

    finally:
        session.close()


if __name__ == '__main__':
    standardize_tags()
