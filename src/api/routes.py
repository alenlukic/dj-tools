"""API route definitions for the three endpoints."""

import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query

from src.api.schemas import SearchSuggestion, TrackResponse, TransitionMatchResponse
from src.api.queries import get_tracks
from src.api.serializers import (
    serialize_track_row,
    serialize_matches,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")

_match_finder = None


def _get_session():
    from src.db import database
    return database.create_session()


def _get_match_finder():
    global _match_finder
    if _match_finder is None:
        from src.harmonic_mixing.transition_match_finder import TransitionMatchFinder
        _match_finder = TransitionMatchFinder()
    return _match_finder


@router.get("/search", response_model=List[SearchSuggestion])
def api_search(q: str = Query(..., min_length=1)):
    from src.api.es import search as es_search
    try:
        hits = es_search(q.strip(), limit=10)
    except Exception:
        logger.exception("Elasticsearch search failed for q=%r", q)
        raise HTTPException(status_code=503, detail="Search unavailable")
    results = []
    for doc in hits:
        artist_names = doc.get("artist_names", [])
        if isinstance(artist_names, str):
            artist_names = [n.strip() for n in artist_names.split(",") if n.strip()]
        results.append({
            "id": doc["id"],
            "title": doc.get("title", ""),
            "artist_names": artist_names,
            "bpm": doc.get("bpm"),
            "key": doc.get("key"),
            "camelot_code": doc.get("camelot_code"),
        })
    return results


@router.get("/tracks", response_model=List[TrackResponse])
def api_tracks(
    camelot_code: Optional[str] = Query(None),
    bpm: Optional[float] = Query(None),
    bpm_min: Optional[float] = Query(None),
    bpm_max: Optional[float] = Query(None),
):
    codes = None
    if camelot_code:
        codes = [c.strip() for c in camelot_code.split(",") if c.strip()]

    session = _get_session()
    try:
        rows = get_tracks(
            session.session,
            camelot_codes=codes,
            bpm=bpm,
            bpm_min=bpm_min,
            bpm_max=bpm_max,
        )
        return [serialize_track_row(track, names) for track, names in rows]
    finally:
        session.close()


@router.get("/tracks/{track_id}/matches", response_model=List[TransitionMatchResponse])
def api_matches(track_id: int):
    from src.models.track import Track

    session = _get_session()
    try:
        track = session.query(Track).filter_by(id=track_id).first()
        if track is None:
            raise HTTPException(status_code=404, detail="Track not found")

        finder = _get_match_finder()
        result = finder.get_transition_matches(track)
        if result is None:
            raise HTTPException(status_code=404, detail="No matches found")

        (same_key, higher_key, lower_key), _ = result
        return serialize_matches(same_key, higher_key, lower_key)
    finally:
        session.close()
