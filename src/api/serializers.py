"""Converters from ORM rows and TransitionMatch objects to response dicts."""

from typing import List

from src.data_management.config import TrackDBCols


def serialize_track_row(track, artist_names_str):
    """Convert a (Track, artist_names_agg) query row to a response dict."""
    names = []
    if artist_names_str:
        names = [n.strip() for n in artist_names_str.split(",") if n.strip()]

    return {
        "id": track.id,
        "title": track.title,
        "artist_names": names,
        "bpm": float(track.bpm) if track.bpm is not None else None,
        "key": track.key,
        "camelot_code": track.camelot_code,
        "genre": track.genre,
        "label": track.label,
        "energy": track.energy,
    }


def serialize_search_row(track, artist_names_str, _similarity):
    """Convert a search result row to a suggestion dict."""
    names = []
    if artist_names_str:
        names = [n.strip() for n in artist_names_str.split(",") if n.strip()]

    return {
        "id": track.id,
        "title": track.title,
        "artist_names": names,
        "bpm": float(track.bpm) if track.bpm is not None else None,
        "key": track.key,
        "camelot_code": track.camelot_code,
    }


def serialize_transition_match(match, bucket: str) -> dict:
    """Convert a TransitionMatch instance to a response dict with full factor breakdown."""
    match.get_score()
    return {
        "candidate_id": match.metadata.get(TrackDBCols.ID),
        "title": match.metadata.get(TrackDBCols.TITLE, ""),
        "overall_score": round(match.get_score(), 2),
        "bucket": bucket,
        "camelot_score": round(match.get_camelot_priority_score(), 4),
        "bpm_score": round(match.get_bpm_score(), 4),
        "energy_score": round(match.get_energy_score(), 4),
        "similarity_score": round(match.get_similarity_score(), 4),
        "freshness_score": round(match.get_freshness_score(), 4),
        "genre_similarity_score": round(match.get_genre_similarity_score(), 4),
        "mood_continuity_score": round(match.get_mood_continuity_score(), 4),
        "vocal_clash_score": round(match.get_vocal_clash_score(), 4),
        "danceability_score": round(match.get_danceability_score(), 4),
        "timbre_score": round(match.get_timbre_score(), 4),
        "instrument_similarity_score": round(match.get_instrument_similarity_score(), 4),
    }


def serialize_matches(same_key, higher_key, lower_key) -> List[dict]:
    """Flatten all three match buckets into a single serialized list."""
    results = []
    for match in same_key:
        results.append(serialize_transition_match(match, "same_key"))
    for match in higher_key:
        results.append(serialize_transition_match(match, "higher_key"))
    for match in lower_key:
        results.append(serialize_transition_match(match, "lower_key"))
    return results


def serialize_trait_info(trait):
    """Extract readable trait fields for UI display, omitting binary/blob data."""
    if trait is None:
        return None
    result = {}
    for field in [
        "voice_instrumental", "danceability", "bright_dark",
        "acoustic_electronic", "tonal_atonal", "reverb",
        "onset_density", "spectral_flatness",
    ]:
        val = getattr(trait, field, None)
        if val is not None:
            result[field] = round(float(val), 4)
    for field in ["mood_theme", "genre", "instruments"]:
        val = getattr(trait, field, None)
        if val is not None:
            result[field] = val
    return result if result else None


def serialize_match_detail_track(track, trait):
    """Serialize a track + its trait data for the match detail endpoint."""
    return {
        "id": track.id,
        "title": track.title,
        "bpm": float(track.bpm) if track.bpm is not None else None,
        "key": track.key,
        "camelot_code": track.camelot_code,
        "energy": track.energy,
        "genre": track.genre,
        "label": track.label,
        "traits": serialize_trait_info(trait),
    }
