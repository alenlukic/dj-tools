from sqlalchemy import Column, Integer, Sequence

from src.db import metadata
from src.db import Base


class Artist(Base):
    """
    Represents row in artist table in the sqlalchemy ORM. Postgres schema:

                          Table "public.artist"
       Column    |       Type        | Collation | Nullable | Default
    -------------+-------------------+-----------+----------+---------
     id          | integer           |           | not null |
     name        | character varying |           | not null |
     track_count | integer           |           | not null |
    Indexes:
        "artist_pkey" PRIMARY KEY, btree (id, name)
        "ix_artist_id" UNIQUE, btree (id)
        "ix_artist_name" UNIQUE, btree (name)
    Referenced by:
        TABLE "artist_track" CONSTRAINT "artist_track_artist_id_fkey" FOREIGN KEY (artist_id) REFERENCES artist(id)
    """

    __tablename__ = 'artist'
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, Sequence('artist_seq', metadata=metadata), primary_key=True, index=True, unique=True)
