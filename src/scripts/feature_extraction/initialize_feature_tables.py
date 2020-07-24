from sqlalchemy import Integer, JSON

from src.db.column import DBColumn
from src.db.database import Database
from src.db.entities.feature_value import FeatureValue
from src.db.entities.track import Track
from src.db.entities.transition_match import TransitionMatch
from src.db.table import DBTable
from src.lib.assistant.assistant import Assistant


def create_tables():
    metadata = database.get_metadata()

    # feature_value table
    fv = 'feature_value'
    fv_columns = [
        DBColumn('id', Integer).as_index().as_primary_key().as_unique().create(metadata, fv),
        DBColumn('track_id', Integer).as_index().as_primary_key().as_foreign_key('track.id').as_unique().create(
            metadata, fv),
        DBColumn('features', JSON).create(metadata, fv)
    ]
    DBTable(fv, metadata, fv_columns)
    metadata.create_all()

    tm = 'transition_match'
    tm_columns = [
        DBColumn('id', Integer).as_index().as_primary_key().as_unique().create(metadata, tm),
        DBColumn('on_deck_id', Integer).as_index().as_primary_key().as_foreign_key(
            'feature_value.track_id').as_unique().create(metadata, tm),
        DBColumn('candidate_id', Integer).as_index().as_primary_key().as_foreign_key(
            'feature_value.track_id').as_unique().create(metadata, tm),
        DBColumn('match_factors', JSON).create(metadata, tm)
    ]
    DBTable(tm, metadata, tm_columns)
    metadata.create_all()


def populate_tables():
    assistant = Assistant()
    tracks = assistant.tracks()

    for track in tracks:
        same_key, higher_key, lower_key = assistant.get_transition_matches(track.title)
        for match in same_key:
            # TODO
            pass


if __name__ == '__main__':
    database = Database()
    # create_tables()
