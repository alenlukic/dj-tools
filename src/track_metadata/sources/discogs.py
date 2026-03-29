from __future__ import annotations

from typing import Any


def _coerce_year(value: Any) -> int | None:
    if value is None:
        return None

    try:
        return int(str(value)[:4])
    except (TypeError, ValueError):
        return None


def _first_non_empty(*values: Any) -> str | None:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _first_list_item(value: Any) -> str | None:
    if not isinstance(value, list):
        return None

    for item in value:
        if isinstance(item, str) and item.strip():
            return item.strip()
    return None


def _split_discogs_title(value: Any) -> tuple[str | None, str | None]:
    if not isinstance(value, str) or not value.strip():
        return None, None

    if " - " not in value:
        return None, value.strip()

    artist, title = value.split(" - ", 1)
    return artist.strip() or None, title.strip() or None
