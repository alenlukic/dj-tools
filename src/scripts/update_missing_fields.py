import json
from os.path import join

from src.db import database
from src.db.entities.track import Track
from src.definitions.common import CONFIG


def update_missing_fields(update_template='update_template.json'):
    with open(join(CONFIG['DATA_DIR'], update_template), 'r') as u:
        session = database.create_session()
        errors = False
        update_values = json.load(u)

        try:
            for update_value in update_values:
                track_id = update_value.get('ID', -1)
                print('Processing %d' % track_id)
                try:
                    track = session.query(Track).filter_by(id=track_id).first()
                    if track is None:
                        print('Could not find track with id %d' % track_id)
                        continue

                    for field, value in update_value['Fields'].items():
                        setattr(track, field, value)
                except Exception as e:
                    print('Error processing %d: %s' % (track_id, str(e)))
                    errors = True
        finally:
            if not errors:
                session.commit()

            database.close_all_sessions()


if __name__ == '__main__':
    update_missing_fields()
