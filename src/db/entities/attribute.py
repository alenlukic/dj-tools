from sqlalchemy import Column, Integer, Sequence, String
from src.db import metadata
from src.db import Base


class Attribute(Base):
    __tablename__ = 'attribute'
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, Sequence('attribute_id_seq', metadata=metadata), primary_key=True, index=True, unique=True)

    name = Column('name', String(64), primary_key=True, index=True, unique=True, nullable=False)

    def __eq__(self, other):
        return self.id == other.id and self.__class__.__name__ == other.__class__.__name__

    def __hash__(self):
        return hash(self.__class__.__name__ + str(self.id))
