from sqlalchemy import Column, Integer, Sequence, String

from src.db import Base, metadata


class ArtistMapping(Base):
    """Maps raw artist strings to canonical forms.

    match_type values:
      exact    — exact string equality match
      contains — match if raw_artist is a substring of the input artist string
    """

    __tablename__ = "artist_mapping"
    __table_args__ = {"extend_existing": True}

    id = Column(
        Integer,
        Sequence("artist_mapping_seq", metadata=metadata),
        primary_key=True,
        index=True,
        unique=True,
    )
    raw_artist = Column(String(255), unique=True, nullable=False, index=True)
    canonical_artist = Column(String(255), nullable=False)
    match_type = Column(String(32), nullable=False)

    def __eq__(self, other):
        return (
            self.id == other.id and self.__class__.__name__ == other.__class__.__name__
        )

    def __hash__(self):
        return hash(self.__class__.__name__ + str(self.id))
