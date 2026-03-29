from sqlalchemy import Column, DateTime, Float, Integer, Sequence, String, func
from sqlalchemy.dialects.postgresql import JSONB

from src.db import Base


class TrackTrait(Base):
    __tablename__ = "track_trait"
    __table_args__ = {"extend_existing": True}

    id = Column(
        Integer,
        Sequence("track_trait_id_seq"),
        primary_key=True,
        index=True,
        unique=True,
    )
    track_id = Column(Integer, index=True, unique=True, nullable=False)

    # Binary classifiers — float probability of positive class
    voice_instrumental = Column(Float, nullable=True)   # P(voice)
    danceability = Column(Float, nullable=True)          # P(danceable)
    bright_dark = Column(Float, nullable=True)           # P(bright)
    acoustic_electronic = Column(Float, nullable=True)  # P(electronic)
    tonal_atonal = Column(Float, nullable=True)          # P(tonal)
    reverb = Column(Float, nullable=True)                # P(wet)

    # librosa-derived scalars
    onset_density = Column(Float, nullable=True)         # onsets/sec
    spectral_flatness = Column(Float, nullable=True)     # mean [0, 1]

    # Multi-label classifiers — {label: probability} above threshold
    mood_theme = Column(JSONB, nullable=True)            # 56-class MTG Jamendo
    genre = Column(JSONB, nullable=True)                 # 519-class Discogs
    instruments = Column(JSONB, nullable=True)           # 40-class MTG Jamendo

    # Phase III placeholders (no inference implementation yet)
    audio_events = Column(JSONB, nullable=True)          # YAMNet 520 classes
    vocal_energy_ratio = Column(Float, nullable=True)    # Demucs stem ratio

    # Versioning
    trait_version = Column(String(32), nullable=False)
    computed_at = Column(DateTime, nullable=False, server_default=func.now())

    def __eq__(self, other):
        return (
            self.id == other.id and self.__class__.__name__ == other.__class__.__name__
        )

    def __hash__(self):
        return hash(self.__class__.__name__ + str(self.id))
