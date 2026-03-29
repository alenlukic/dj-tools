from sqlalchemy import Column, Integer, Sequence

from src.db import metadata
from src.db import Base


class InitialTagRecord(Base):
    __tablename__ = "initial_tags"
    __table_args__ = {"extend_existing": True}

    id = Column(
        Integer,
        Sequence("initial_tags_seq", metadata=metadata),
        primary_key=True,
        index=True,
        unique=True,
    )

    def __eq__(self, other):
        return (
            self.id == other.id and self.__class__.__name__ == other.__class__.__name__
        )

    def __hash__(self):
        return hash(self.__class__.__name__ + str(self.id))


class PostMIKTagRecord(Base):
    __tablename__ = "post_mik_tags"
    __table_args__ = {"extend_existing": True}

    id = Column(
        Integer,
        Sequence("post_mik_tags_seq", metadata=metadata),
        primary_key=True,
        index=True,
        unique=True,
    )

    def __eq__(self, other):
        return (
            self.id == other.id and self.__class__.__name__ == other.__class__.__name__
        )

    def __hash__(self):
        return hash(self.__class__.__name__ + str(self.id))


class PostRekordboxTagRecord(Base):
    __tablename__ = "post_rekordbox_tags"
    __table_args__ = {"extend_existing": True}

    id = Column(
        Integer,
        Sequence("post_rekordbox_tags_seq", metadata=metadata),
        primary_key=True,
        index=True,
        unique=True,
    )

    def __eq__(self, other):
        return (
            self.id == other.id and self.__class__.__name__ == other.__class__.__name__
        )

    def __hash__(self):
        return hash(self.__class__.__name__ + str(self.id))


class FinalTagRecord(Base):
    __tablename__ = "final_tags"
    __table_args__ = {"extend_existing": True}

    id = Column(
        Integer,
        Sequence("final_tags_seq", metadata=metadata),
        primary_key=True,
        index=True,
        unique=True,
    )

    def __eq__(self, other):
        return (
            self.id == other.id and self.__class__.__name__ == other.__class__.__name__
        )

    def __hash__(self):
        return hash(self.__class__.__name__ + str(self.id))
