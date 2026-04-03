"""API route definitions."""

import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query

from src.api.schemas import (
    MatchDetailResponse,
    SearchSuggestion,
    TrackResponse,
    TransitionMatchResponse,
)
from src.api.queries import get_tracks
from src.api.serializers import (
    serialize_match_detail_track,
    serialize_matches,
    serialize_track_row,
)
from src.data_management.config import TrackDBCols

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


@router.get(
    "/tracks/{track_id}/match-detail/{candidate_id}",
    response_model=MatchDetailResponse,
)
def api_match_detail(track_id: int, candidate_id: int):
    from src.models.track import Track
    from src.models.track_trait import TrackTrait
    from src.feature_extraction.config import TRAIT_VERSION
    from src.harmonic_mixing.config import MATCH_WEIGHTS, MatchFactors

    session = _get_session()
    try:
        source_track = session.query(Track).filter_by(id=track_id).first()
        if source_track is None:
            raise HTTPException(status_code=404, detail="Source track not found")

        candidate_track = session.query(Track).filter_by(id=candidate_id).first()
        if candidate_track is None:
            raise HTTPException(status_code=404, detail="Candidate track not found")

        finder = _get_match_finder()
        result = finder.get_transition_matches(source_track)
        if result is None:
            raise HTTPException(status_code=404, detail="No matches found")

        (same_key, higher_key, lower_key), _ = result

        target_match = None
        for match in same_key + higher_key + lower_key:
            if match.metadata.get(TrackDBCols.ID) == candidate_id:
                target_match = match
                break

        if target_match is None:
            raise HTTPException(
                status_code=404, detail="Match not found for this track pair"
            )

        target_match.get_score()

        factors = []
        for factor in MatchFactors:
            weight = MATCH_WEIGHTS.get(factor.name, 0)
            score = target_match.factors.get(factor, 0)
            factors.append({
                "name": factor.value,
                "score": round(score, 4),
                "weight": round(weight, 4),
            })

        source_trait = (
            session.query(TrackTrait)
            .filter_by(track_id=track_id, trait_version=TRAIT_VERSION)
            .first()
        )
        candidate_trait = (
            session.query(TrackTrait)
            .filter_by(track_id=candidate_id, trait_version=TRAIT_VERSION)
            .first()
        )

        return {
            "overall_score": round(target_match.get_score(), 2),
            "factors": factors,
            "on_deck": serialize_match_detail_track(source_track, source_trait),
            "candidate": serialize_match_detail_track(candidate_track, candidate_trait),
        }
    finally:
        session.close()
