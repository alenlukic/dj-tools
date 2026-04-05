"""API route definitions."""

import logging
from collections import Counter
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query

from src.api.schemas import (
    CacheStatsResponse,
    MatchDetailResponse,
    SearchSuggestion,
    TrackResponse,
    TrackTraitResponse,
    TransitionMatchResponse,
    WeightResponse,
    WeightUpdateRequest,
)
from src.api.queries import get_tracks
from src.api.serializers import (
    serialize_match_detail_track,
    serialize_matches,
    serialize_track_row,
    serialize_trait_info,
)
from src.data_management.config import TrackDBCols

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")

_match_finder = None

_BPM_BIN_WIDTH = 5


def _get_session():
    from src.db import database
    return database.create_session()


def _get_match_finder():
    global _match_finder
    if _match_finder is None:
        from src.harmonic_mixing.cosine_cache import CosineCache
        from src.harmonic_mixing.transition_match_finder import TransitionMatchFinder
        _match_finder = TransitionMatchFinder(cosine_cache=CosineCache())
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
        return [serialize_track_row(track) for track in rows]
    except HTTPException:
        raise
    except Exception:
        session.rollback()
        logger.exception("Track listing failed")
        raise HTTPException(status_code=500, detail="Track listing failed")
    finally:
        session.close()


@router.get("/track-traits", response_model=List[TrackTraitResponse])
def api_track_traits():
    from src.models.track_trait import TrackTrait
    from src.feature_extraction.config import TRAIT_VERSION

    session = _get_session()
    try:
        rows = (
            session.query(TrackTrait)
            .filter_by(trait_version=TRAIT_VERSION)
            .all()
        )
        return [
            {"track_id": row.track_id, "traits": serialize_trait_info(row)}
            for row in rows
        ]
    except HTTPException:
        raise
    except Exception:
        session.rollback()
        logger.exception("Track trait listing failed")
        raise HTTPException(status_code=500, detail="Track trait listing failed")
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

        cache = finder.cosine_cache
        if cache is not None and hasattr(cache, 'schedule_warmup'):
            cache.schedule_warmup(track_id)

        return serialize_matches(same_key, higher_key, lower_key)
    except HTTPException:
        raise
    except Exception:
        session.rollback()
        logger.exception("Match retrieval failed for track_id=%s", track_id)
        raise HTTPException(status_code=500, detail="Match retrieval failed")
    finally:
        session.close()


@router.get(
    "/tracks/{track_id}/match-detail/{candidate_id}",
    response_model=MatchDetailResponse,
)
def api_match_detail(track_id: int, candidate_id: int):
    from src.models.track import Track
    from src.harmonic_mixing.config import MATCH_WEIGHTS, MatchFactors
    from src.harmonic_mixing.weight_service import WeightService

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

        try:
            active_weights = WeightService.instance().get_effective_weights_for_scoring()
        except Exception:
            active_weights = MATCH_WEIGHTS

        factors = []
        for factor in MatchFactors:
            weight = active_weights.get(factor.name, 0)
            score = target_match.factors.get(factor, 0)
            factors.append({
                "name": factor.value,
                "score": round(score, 4),
                "weight": round(weight, 4),
            })

        return {
            "overall_score": round(target_match.get_score(), 2),
            "factors": factors,
            "on_deck": serialize_match_detail_track(source_track, None),
            "candidate": serialize_match_detail_track(candidate_track, None),
        }
    except HTTPException:
        raise
    except Exception:
        session.rollback()
        logger.exception("Match detail failed for track_id=%s, candidate_id=%s", track_id, candidate_id)
        raise HTTPException(status_code=500, detail="Match detail retrieval failed")
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Admin / cache stats
# ---------------------------------------------------------------------------


@router.get("/admin/cache-stats", response_model=CacheStatsResponse)
def api_cache_stats():
    finder = _get_match_finder()
    cache = finder.cosine_cache
    if cache is None:
        return CacheStatsResponse(
            used=0, capacity=0, usage_ratio=0.0,
            hits=0, misses=0, hit_rate=0.0,
            hit_rate_numerator=0, hit_rate_denominator=0,
            hit_rate_basis="process_lifetime",
            key_distribution=[], bpm_distribution=[],
            recent_entries=[], recent_exits=[],
        )

    stats = cache.get_stats()

    key_dist, bpm_dist = _build_cache_distributions(cache)

    return CacheStatsResponse(
        **{k: v for k, v in stats.items()
           if k not in ("recent_entries", "recent_exits")},
        key_distribution=key_dist,
        bpm_distribution=bpm_dist,
        recent_entries=[
            {"pair": list(e["pair"]), "timestamp": e["timestamp"]}
            for e in stats["recent_entries"]
        ],
        recent_exits=[
            {"pair": list(e["pair"]), "timestamp": e["timestamp"],
             "reason": e.get("reason")}
            for e in stats["recent_exits"]
        ],
    )


def _build_cache_distributions(cache):
    from src.models.track import Track

    track_ids = cache.get_cached_track_ids()
    if not track_ids:
        return [], []

    session = _get_session()
    try:
        rows = (
            session.query(Track)
            .filter(Track.id.in_(track_ids))
            .all()
        )

        key_counter: Counter = Counter()
        bpms: list = []
        for row in rows:
            if row.camelot_code:
                key_counter[row.camelot_code] += 1
            if row.bpm is not None:
                bpms.append(float(row.bpm))

        key_dist = [
            {"key": k, "count": c}
            for k, c in key_counter.most_common()
        ]

        bpm_dist = []
        if bpms:
            min_bpm = int(min(bpms) // _BPM_BIN_WIDTH) * _BPM_BIN_WIDTH
            max_bpm = int(max(bpms) // _BPM_BIN_WIDTH) * _BPM_BIN_WIDTH + _BPM_BIN_WIDTH
            bins: Counter = Counter()
            for b in bpms:
                bin_start = int(b // _BPM_BIN_WIDTH) * _BPM_BIN_WIDTH
                bins[bin_start] += 1
            for b in range(min_bpm, max_bpm + 1, _BPM_BIN_WIDTH):
                bpm_dist.append({
                    "bin_start": float(b),
                    "bin_end": float(b + _BPM_BIN_WIDTH),
                    "count": bins.get(b, 0),
                })

        return key_dist, bpm_dist
    except Exception:
        session.rollback()
        logger.exception("Cache distribution query failed")
        return [], []
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Weight controls
# ---------------------------------------------------------------------------


@router.get("/weights", response_model=WeightResponse)
def api_get_weights():
    from src.harmonic_mixing.weight_service import WeightService
    return WeightService.instance().get_weights()


@router.put("/weights", response_model=WeightResponse)
def api_update_weights(body: WeightUpdateRequest):
    from src.harmonic_mixing.weight_service import WeightService
    result = WeightService.instance().update_weights(body.weights)
    finder = _get_match_finder()
    finder._sync_effective_weights()
    return result
