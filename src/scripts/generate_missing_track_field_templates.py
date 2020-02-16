import json
from os.path import join

from src.db import database
from src.db.entities.track import columns, Track
from src.definitions.common import CONFIG


def generate_discogs_search_queries(missing_fields):
    return ['Discogs %s' % mf['Title'] for mf in missing_fields]


def find_missing_track_columns():
    session = database.create_session()
    tracks = session.query(Track).all()
    columns_to_check = list(filter(lambda c: not (c == 'energy' or c == 'comment'), columns))

    track_missing_fields = []
    for track in tracks:
        track_id = track.id
        try:
            missing_fields = []
            for column in columns_to_check:
                if getattr(track, column) is None:
                    missing_fields.append(column)

            if len(missing_fields) > 0:
                track_missing_fields.append({
                    'ID': track_id,
                    'Title': track.title.split('] ')[-1],
                    'Fields': {f: '(missing)' for f in missing_fields}
                })

        except Exception as e:
            print('Error processing %d: %s' % (track_id, str(e)))
            continue

    data_path = CONFIG['DATA_DIR']
    with open(join(data_path, 'discog_queries.csv'), 'w') as w:
        discogs_queries = generate_discogs_search_queries(track_missing_fields)
        w.write('\n'.join(discogs_queries) + '\n')
    with open(join(data_path, 'update_template.json'), 'w') as w:
        json.dump(track_missing_fields, w, indent=2)

    database.close_all_sessions()


if __name__ == '__main__':
    find_missing_track_columns()
