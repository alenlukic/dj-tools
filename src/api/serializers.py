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
    """Convert a TransitionMatch instance to a response dict."""
    return {
        "title": match.metadata.get(TrackDBCols.TITLE, ""),
        "overall_score": round(match.get_score(), 2),
        "bucket": bucket,
        "camelot_score": round(match.get_camelot_priority_score(), 4),
        "bpm_score": round(match.get_bpm_score(), 4),
        "energy_score": round(match.get_energy_score(), 4),
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
