"""SQLAlchemy queries for the API layer.

Uses reflected table objects for artist joins to avoid N+1 queries.
All track list/search queries aggregate artist names in SQL via string_agg.
"""

from typing import List, Optional

from sqlalchemy import func, literal_column
from sqlalchemy.orm import Session

from src.models.track import Track

_TRACK_GROUP_COLS = [
    Track.id,
    Track.file_name,
    Track.title,
    Track.bpm,
    Track.key,
    Track.camelot_code,
    Track.energy,
    Track.genre,
    Track.label,
    Track.comment,
]


def _get_reflected_tables(session: Session):
    """Retrieve the reflected artist and artist_track Table objects."""
    from src.db import database
    tables = database.get_tables()
    artist_table = tables["artist"]
    artist_track_table = tables["artist_track"]
    return artist_table, artist_track_table


def _base_track_query(session: Session):
    """Build a base query joining Track with aggregated artist names.

    Returns columns: Track.*, artist_names (comma-separated string).
    """
    artist_table, artist_track_table = _get_reflected_tables(session)

    artist_names_agg = func.string_agg(
        artist_table.c.name, literal_column("', '")
    ).label("artist_names")

    q = (
        session.query(Track, artist_names_agg)
        .outerjoin(artist_track_table, artist_track_table.c.track_id == Track.id)
        .outerjoin(artist_table, artist_table.c.id == artist_track_table.c.artist_id)
        .group_by(*_TRACK_GROUP_COLS)
    )
    return q


def get_tracks(
    session: Session,
    camelot_codes: Optional[List[str]] = None,
    bpm: Optional[float] = None,
    bpm_min: Optional[float] = None,
    bpm_max: Optional[float] = None,
):
    q = _base_track_query(session)

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
