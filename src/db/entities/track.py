from sqlalchemy import Column, Integer, Sequence

from src.db import metadata
from src.db import Base


class Track(Base):
    """
    Represents row in track table in the sqlalchemy ORM. Postgres schema:

                               Table "public.track"
        Column    |       Type        | Collation | Nullable | Default
    --------------+-------------------+-----------+----------+---------
     id           | integer           |           | not null |
     file_path    | character varying |           | not null |
     title        | character varying |           | not null |
     bpm          | integer           |           |          |
     key          | character varying |           |          |
     camelot_code | character varying |           |          |
     energy       | integer           |           |          |
     genre        | character varying |           |          |
     label        | character varying |           |          |
     date_added   | character varying |           |          |
     comment      | character varying |           |          |
    Indexes:
        "track_pkey" PRIMARY KEY, btree (id, file_path)
        "ix_track_id" UNIQUE, btree (id)
        "ix_track_bpm" btree (bpm)
        "ix_track_camelot_code" btree (camelot_code)
        "ix_track_date_added" btree (date_added)
        "ix_track_energy" btree (energy)
        "ix_track_file_path" btree (file_path)
        "ix_track_genre" btree (genre)
        "ix_track_key" btree (key)
        "ix_track_label" btree (label)
        "ix_track_title" btree (title)
    Referenced by:
        TABLE "artist_track" CONSTRAINT "artist_track_track_id_fkey" FOREIGN KEY (track_id) REFERENCES track(id)
    """

    __tablename__ = 'track'
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, Sequence('track_seq', metadata=metadata), primary_key=True, index=True, unique=True)

    def get_primary_key(self):
        """ TODO. """
        return '%d %s' % (self.id, self.title)
