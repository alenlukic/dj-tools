from sqlalchemy import Column, Integer, Sequence, String

from src.db import Base, metadata


class GenreMapping(Base):
    __tablename__ = "genre_mapping"
    __table_args__ = {"extend_existing": True}

    id = Column(
        Integer,
        Sequence("genre_mapping_seq", metadata=metadata),
        primary_key=True,
        index=True,
        unique=True,
    )
    raw_genre = Column(String(255), unique=True, nullable=False, index=True)
    canonical_genre = Column(String(255), nullable=False)

    def __eq__(self, other):
        return (
            self.id == other.id and self.__class__.__name__ == other.__class__.__name__
        )

    def __hash__(self):
        return hash(self.__class__.__name__ + str(self.id))
