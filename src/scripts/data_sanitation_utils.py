import json
from os.path import join
from sqlalchemy.orm import session as sezzion, sessionmaker

from src.db.database import Database
from src.definitions.common import DATA_DIR
from src.tools.data_management.track import *


def find_null_values_in_tracks():
    """ Create a JSON file which shows null fields in the track table. """

    session = bound_session()
    track_table = metadata.tables['track']
    track_rows = session.execute(track_table.select()).fetchall()
    track_cols = [c.name for c in track_table.c]
    null_columns = {}

    for track_row in track_rows:
        row_null_columns = list(filter(lambda c: track_row[c] is None, track_cols))
        if len(row_null_columns) > 0:
            null_columns[track_row['file_path']] = {'Null fields': row_null_columns}

    with open(join(DATA_DIR, 'null_track_values.json'), 'w') as f:
        json.dump(null_columns, f, indent=2)


if __name__ == '__main__':
    database = Database()
    metadata = database.get_metadata()
    bound_session = sessionmaker(bind=database.get_engine())
    find_null_values_in_tracks()
    sezzion.close_all_sessions()
