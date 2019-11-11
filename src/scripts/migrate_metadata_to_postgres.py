from sqlalchemy import Integer, String

from src.db.column import DBColumn
from src.db.database import Database
from src.db.table import DBTable
from src.tools.data_management.data_manager import DataManager


def create_track_table(metadata):
    """
    Creates the track table.

    :param metadata - sqlalchemy MetaData object.
    """

    columns = [
        DBColumn('id', Integer).as_index().as_unique().with_autoincrement().create(),
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
        DBColumn('id', Integer).as_index().as_primary_key().as_unique().with_autoincrement().create(),
        DBColumn('name', String).as_index().as_primary_key().create(),
        DBColumn('track_count', Integer).create()
    ]
    DBTable('artist', metadata, columns)


def create_artist_track_table(metadata):
    """
    Creates the artist_track table.

    :param metadata - sqlalchemy MetaData object.
    """

    columns = [
        DBColumn('id', Integer).with_autoincrement().create(),
        DBColumn('artist_id', Integer).as_index().as_foreign_key('artist.id').as_primary_key().create(),
        DBColumn('track_id', Integer).as_index().as_foreign_key('track.id').as_primary_key().create()
    ]
    DBTable('artist_track', metadata, columns)


def create_tables(database):
    """
    Creates track, artist, and artist_track tables, if they don't exist.

    :param database - interface to Postgres database.
    """

    metadata = database.get_metadata()
    create_track_table(metadata)
    create_artist_table(metadata)
    create_artist_track_table(metadata)
    metadata.create_all()


def migrate_data(database):
    """
    Migrates existing JSON data to the database.

    :param database - interface to Postgres database.
    """

    data_manager = DataManager()
    json_metadata = data_manager.load_collection_metadata().get('Track Metadata')
    # TODO: iterate through json metadata and populate DB - make sure to capitalize first letter of each word in labels


if __name__ == '__main__':
    db = Database()
    create_tables(db)
