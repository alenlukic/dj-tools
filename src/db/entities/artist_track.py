from sqlalchemy import Column, Integer, Sequence

from src.db import metadata
from src.db import Base


class ArtistTrack(Base):
    """
    Represents row in artist_track table in the sqlalchemy ORM. Postgres schema:

                 Table "public.artist_track"
      Column   |  Type   | Collation | Nullable | Default
    -----------+---------+-----------+----------+---------
     id        | integer |           | not null |
     artist_id | integer |           | not null |
     track_id  | integer |           | not null |
    Indexes:
        "artist_track_pkey" PRIMARY KEY, btree (id, artist_id, track_id)
        "ix_artist_track_id" UNIQUE, btree (id)
        "ix_artist_track_artist_id" btree (artist_id)
        "ix_artist_track_track_id" btree (track_id)
    Foreign-key constraints:
        "artist_track_artist_id_fkey" FOREIGN KEY (artist_id) REFERENCES artist(id)
        "artist_track_track_id_fkey" FOREIGN KEY (track_id) REFERENCES track(id)
    """

    __tablename__ = 'artist_track'
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, Sequence('artist_track_seq', metadata=metadata), primary_key=True, index=True, unique=True)

    def __eq__(self, other):
        return self.id == other.id and self.__class__.__name__ == other.__class__.__name__

    def __hash__(self):
        return hash(self.__class__.__name__ + str(self.id))
