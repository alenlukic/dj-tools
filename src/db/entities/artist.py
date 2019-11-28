from sqlalchemy import Column, Integer, Sequence

from src.db import metadata
from src.db import Base


class Artist(Base):
    """ Represents row in artist table in the sqlalchemy ORM. """

    __tablename__ = 'artist'
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, Sequence('artist_seq', metadata=metadata), primary_key=True, index=True, unique=True)
