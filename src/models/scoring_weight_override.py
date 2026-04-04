from sqlalchemy import Column, DateTime, Integer, String, Text, func

from src.db import Base


class ScoringWeightOverride(Base):
    """Single-row table persisting user-modified scoring weights as JSON.

    Keyed by ``scope`` so the design can later support per-user or
    per-session scopes; the current implementation uses ``scope='global'``.
    """

    __tablename__ = "scoring_weight_override"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, autoincrement=True)
    scope = Column(String(32), nullable=False, unique=True, default="global")
    weights_json = Column(Text, nullable=False)
    updated_at = Column(DateTime, nullable=False, server_default=func.now())
