from __future__ import annotations

import re
from dataclasses import replace
from difflib import SequenceMatcher
from pathlib import Path

from models import SimpleMetadata


def _normalize_for_match(value: str | None) -> str:
    if not value:
        return ""

    normalized = value.casefold()
    normalized = normalized.replace("&", " and ")
    normalized = re.sub(r"\b(feat|featuring|ft)\.?\b", "", normalized)
    normalized = re.sub(r"\(.*?\)|\[.*?\]", " ", normalized)
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def _similarity(left: str | None, right: str | None) -> float:
    a = _normalize_for_match(left)
    b = _normalize_for_match(right)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    return SequenceMatcher(None, a, b).ratio()


def _extract_remixer(title: str | None) -> str | None:
    if not title:
        return None

    match = re.search(r"\(([^()]+?)\s+remix\)", title, flags=re.IGNORECASE)
    if match:
        return match.group(1).strip() or None

    match = re.search(r"\[([^\[\]]+?)\s+remix\]", title, flags=re.IGNORECASE)
    if match:
        return match.group(1).strip() or None

    return None


def _parse_filename_seed(path: Path) -> SimpleMetadata:
    stem = path.stem
    stem = re.sub(r"[_]+", " ", stem)
    stem = re.sub(r"\s+", " ", stem).strip()

    if " - " not in stem:
        return SimpleMetadata(title=stem or None, remixer=_extract_remixer(stem))

    artist_part, title_part = stem.split(" - ", 1)
    return SimpleMetadata(
        artist=artist_part.strip() or None,
        title=title_part.strip() or None,
        remixer=_extract_remixer(title_part),
    )


def _merge_missing(
    target: SimpleMetadata,
    candidate: SimpleMetadata | None,
    *,
    fields: set[str] | None = None,
) -> SimpleMetadata:
    if candidate is None:
        return target

    merged = replace(target)
    candidate_data = candidate.to_dict()
    for field, value in candidate_data.items():
        if fields is not None and field not in fields:
            continue
        if value is None:
            continue
        if getattr(merged, field) is None:
            setattr(merged, field, value)
    return merged


def _best_year(*values: int | None) -> int | None:
    for value in values:
        if value:
            return value
    return None
