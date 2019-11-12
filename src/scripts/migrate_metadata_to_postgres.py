from sqlalchemy import Integer, String
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import session as sezzion, sessionmaker
from sqlalchemy.sql import select

from src.db.column import DBColumn
from src.db.database import Database
from src.db.table import DBTable
from src.tools.data_management.data_manager import DataManager
from src.utils.common import is_empty


def create_track_table(metadata):
    """
    Creates the track table.

    :param metadata - sqlalchemy MetaData object.
    """

    columns = [
        DBColumn('id', Integer).as_index().as_primary_key().as_unique().create(metadata, 'track'),
        DBColumn('file_path', String).as_index().as_primary_key().create(),
        DBColumn('title', String).as_index().create(),
        DBColumn('bpm', Integer).as_index().as_nullable().create(),
        DBColumn('key', String).as_index().as_nullable().create(),
        DBColumn('camelot_code', String).as_index().as_nullable().create(),
        DBColumn('energy', Integer).as_index().as_nullable().create(),
        DBColumn('genre', String).as_index().as_nullable().create(),
        DBColumn('label', String).as_index().as_nullable().create(),
        DBColumn('date_added', String).as_index().as_nullable().create()
    ]
    DBTable('track', metadata, columns)


def create_artist_table(metadata):
    """
    Creates the artist table.

    :param metadata - sqlalchemy MetaData object.
    """

    columns = [
        DBColumn('id', Integer).as_index().as_primary_key().as_unique().create(metadata, 'artist'),
        DBColumn('name', String).as_index().as_primary_key().as_unique().create(),
        DBColumn('track_count', Integer).create()
    ]
    DBTable('artist', metadata, columns)


def create_artist_track_table(metadata):
    """
    Creates the artist_track table.

    :param metadata - sqlalchemy MetaData object.
    """

    columns = [
        DBColumn('id', Integer).as_index().as_primary_key().as_unique().create(metadata, 'artist_track'),
        DBColumn('artist_id', Integer).as_index().as_foreign_key('artist.id').as_primary_key().create(),
        DBColumn('track_id', Integer).as_index().as_foreign_key('track.id').as_primary_key().create()
    ]
    DBTable('artist_track', metadata, columns)


def create_tables():
    """ Creates track, artist, and artist_track tables, if they don't exist. """

    metadata = database.get_metadata()
    create_track_table(metadata)
    create_artist_table(metadata)
    create_artist_track_table(metadata)
    metadata.create_all()


def migrate_data():
    """ Migrates existing JSON data to the database. """

    bound_session = sessionmaker(bind=database.get_engine())
    metadata = database.get_metadata()
    track_table = metadata.tables['track']
    artist_table = metadata.tables['artist']
    artist_track_table = metadata.tables['artist_track']
    json_metadata = DataManager().load_collection_metadata()
    artist_counts = json_metadata.get('Artist Counts')

    for file_path, track_metadata in json_metadata.get('Track Metadata').items():
        try:
            # Start a new DB session
            session = bound_session()

            # Create row in track table
            track_data = {col: value for col, value in {
                'file_path': file_path,
                'title': track_metadata.get('Title'),
                'bpm': int(track_metadata.get('BPM', '-1')),
                'key': track_metadata.get('Key'),
                'camelot_code': track_metadata.get('Camelot Code'),
                'energy': int(track_metadata.get('Energy', '-1')),
                'genre': track_metadata.get('Genre'),
                'label': ' '.join([w.capitalize() for w in track_metadata.get('Label', '').split()]),
                'date_added': track_metadata.get('Date Added')
            }.items() if not (is_empty(value) or value == -1)}
            session.execute(track_table.insert(), track_data)

            # Create rows in artist table
            track_row = session.execute(select([track_table]).where(track_table.c.file_path == file_path)).fetchone()
            for artist in track_metadata.get('Artists', []) + track_metadata.get('Remixers', []):
                track_count = artist_counts.get(artist, 0)
                session.execute(
                    insert(artist_table).values(
                        name=artist,
                        track_count=track_count
                    ).on_conflict_do_nothing(index_elements=['name'])
                )

                # Create row in artist_track table
                artist_row = session.execute(select([artist_table]).where(artist_table.c.name == artist)).fetchone()
                session.execute(artist_track_table.insert(), {'track_id': track_row['id'], 'artist_id': artist_row['id']})

            session.commit()

        except Exception as e:
            print('Error: %s' % str(e))
            session.rollback()
            continue

    sezzion.close_all_sessions()


if __name__ == '__main__':
    database = Database()
    create_tables()
    migrate_data()
