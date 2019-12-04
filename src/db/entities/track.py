from sqlalchemy import Column, Integer, Sequence

from src.db import metadata
from src.db import Base


class Track(Base):
    """ Represents row in track table in the sqlalchemy ORM. """

    __tablename__ = 'track'
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, Sequence('track_seq', metadata=metadata), primary_key=True, index=True, unique=True)
