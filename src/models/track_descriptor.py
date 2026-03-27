from sqlalchemy import Column, DateTime, Integer, LargeBinary, Sequence, String, func

from src.db import Base


class TrackDescriptor(Base):
    __tablename__ = "track_descriptor"
    __table_args__ = {"extend_existing": True}

    id = Column(
        Integer,
        # metadata intentionally omitted: this sequence was auto-created by PostgreSQL
        # SERIAL and must not be re-emitted by metadata.create_all().
        Sequence("track_descriptor_id_seq"),
        primary_key=True,
        index=True,
        unique=True,
    )
    track_id = Column(Integer, index=True, unique=True, nullable=False)
    global_vector = Column(LargeBinary, nullable=False)
    intro_vector = Column(LargeBinary, nullable=True)
    outro_vector = Column(LargeBinary, nullable=True)
    descriptor_version = Column(String(32), nullable=False)
    computed_at = Column(DateTime, nullable=False, server_default=func.now())

    def __eq__(self, other):
        return (
            self.id == other.id and self.__class__.__name__ == other.__class__.__name__
        )

    def __hash__(self):
        return hash(self.__class__.__name__ + str(self.id))
