from sqlalchemy import Column, Integer, Sequence, String
from src.db import metadata
from src.db import Base


class TrackAttribute(Base):
    __tablename__ = 'track_attribute'
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, Sequence('track_attribute_id_seq', metadata=metadata), primary_key=True, index=True, unique=True)

    track_id = Column('track_id', Integer, primary_key=True, index=True, nullable=False)

    attribute_id = Column('attribute_id', Integer, primary_key=True, index=True, nullable=False)

    def __eq__(self, other):
        return self.id == other.id and self.__class__.__name__ == other.__class__.__name__

    def __hash__(self):
        return hash(self.__class__.__name__ + str(self.id))
