import json
from os.path import join

from src.db import database
from src.db.entities.track import columns, Track
from src.definitions.common import CONFIG


def find_missing_track_columns():
    session = database.create_session()
    tracks = session.query(Track).all()
    track_missing_fields = []

    for track in tracks:
        track_id = str(track.id or '')
        track_path = track.file_path or ''
        try:
            missing_fields = []
            for column in columns:
                if getattr(track, column) is None:
                    missing_fields.append(column)

            if len(missing_fields) > 0:
                track_missing_fields.append({
                    'id': track_id,
                    'path': track_path,
                    'missing fields': missing_fields
                })

        except Exception as e:
            print('Error processing %s: %s' % (track_id, str(e)))
            continue

    data_path = CONFIG['DATA_DIR']
    with open(join(data_path, 'missing_fields.json'), 'w') as w:
        json.dump(track_missing_fields, w, indent=2)

    database.close_all_sessions()


if __name__ == '__main__':
    find_missing_track_columns()
