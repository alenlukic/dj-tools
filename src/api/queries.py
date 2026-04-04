"""SQLAlchemy queries for the API layer."""

from typing import List, Optional

from sqlalchemy.orm import Session

from src.models.track import Track


def get_tracks(
    session: Session,
    camelot_codes: Optional[List[str]] = None,
    bpm: Optional[float] = None,
    bpm_min: Optional[float] = None,
    bpm_max: Optional[float] = None,
):
    q = session.query(Track)

    if camelot_codes:
        q = q.filter(Track.camelot_code.in_(camelot_codes))
    if bpm is not None:
        q = q.filter(Track.bpm == bpm)
    if bpm_min is not None:
        q = q.filter(Track.bpm >= bpm_min)
    if bpm_max is not None:
        q = q.filter(Track.bpm <= bpm_max)

    q = q.order_by(Track.title.asc())
    return q.all()
