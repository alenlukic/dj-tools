from sqlalchemy import Column, Integer, Numeric, Sequence, String
from src.db import metadata
from src.db import Base


class Track(Base):
    __tablename__ = 'track'
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, Sequence('track_seq', metadata=metadata), primary_key=True, index=True, unique=True)

    file_path = Column('file_path', String(256), primary_key=True, index=True, unique=True, nullable=False)

    title = Column('title', String(256), index=True, nullable=False)

    bpm = Column('bpm', Numeric(5, 2), index=True)

    key = Column('key', String(4), index=True)

    camelot_code = Column('camelot_code', String(4), index=True)

    energy = Column('energy', Integer, index=True)

    genre = Column('genre', String(64), index=True)

    label = Column('label', String(128), index=True)

    comment = Column('comment', String(1024))

    def get_id_title_identifier(self):
        return '%d %s' % (self.id, self.title)

    def __eq__(self, other):
        return self.id == other.id and self.__class__.__name__ == other.__class__.__name__

    def __hash__(self):
        return hash(self.__class__.__name__ + str(self.id))
