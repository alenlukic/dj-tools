from sqlalchemy import Column, Integer, Sequence

from src.db import metadata
from src.db import Base


class Artist(Base):
    __tablename__ = 'artist'
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, Sequence('artist_seq', metadata=metadata), primary_key=True, index=True, unique=True)

    def __eq__(self, other):
        return self.id == other.id and self.__class__.__name__ == other.__class__.__name__

    def __hash__(self):
        return hash(self.__class__.__name__ + str(self.id))
