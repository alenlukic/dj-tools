from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    func,
)

from src.db import Base


class TrackCosineSimilarity(Base):
    __tablename__ = "track_cosine_similarity"
    __table_args__ = (
        CheckConstraint("id1 < id2", name="ck_track_cosine_similarity_id_order"),
        {"extend_existing": True},
    )

    id1 = Column(Integer, ForeignKey("track.id"), primary_key=True)
    id2 = Column(Integer, ForeignKey("track.id"), primary_key=True)
    cosine_similarity = Column(Float, nullable=False)
    descriptor_version = Column(String(32), nullable=False)
    computed_at = Column(DateTime, nullable=False, server_default=func.now())

    def __eq__(self, other):
        return (
            self.id1 == other.id1
            and self.id2 == other.id2
            and self.__class__.__name__ == other.__class__.__name__
        )

    def __hash__(self):
        return hash(self.__class__.__name__ + str(self.id1) + "_" + str(self.id2))
