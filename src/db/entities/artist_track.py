from sqlalchemy import Column, Integer, Sequence

from src.db import metadata
from src.db import Base


class ArtistTrack(Base):
    """ Represents row in artist_track table in the sqlalchemy ORM. """

    __tablename__ = 'artist_track'
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, Sequence('artist_track_seq', metadata=metadata), primary_key=True, index=True, unique=True)
