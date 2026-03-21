from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from models import SimpleMetadata
from sources.discogs import _first_non_empty


def _format_artist_credit(artist_credit: Any) -> str | None:
    if not isinstance(artist_credit, list):
        return None

    parts: list[str] = []
    for item in artist_credit:
        if isinstance(item, str):
            parts.append(item)
            continue

        if not isinstance(item, dict):
            continue

        name = item.get("name")
        if isinstance(name, str) and name.strip():
            parts.append(name.strip())

        joinphrase = item.get("joinphrase")
        if isinstance(joinphrase, str) and joinphrase:
            parts.append(joinphrase)

    text = "".join(parts).strip()
    return text or None


def _first_release_id(payload: Mapping[str, Any]) -> str | None:
    releases = payload.get("releases")
    if not isinstance(releases, list) or not releases:
        return None

    first = releases[0]
    if not isinstance(first, dict):
        return None

    release_id = first.get("id")
    if isinstance(release_id, str) and release_id:
        return release_id

    return None


def _extract_year_from_date(value: Any) -> int | None:
    if not value:
        return None

    text = str(value)
    match = re.search(r"(19|20)\d{2}", text)
    if not match:
        return None

    try:
        return int(match.group())
    except ValueError:
        return None


def _first_genre_name(value: Any) -> str | None:
    if not isinstance(value, list):
        return None

    for item in value:
        if isinstance(item, dict):
            name = item.get("name")
            if isinstance(name, str) and name.strip():
                return name.strip()
    return None


def _musicbrainz_payload_to_metadata(
    recording_payload: Mapping[str, Any],
    release_payload: Mapping[str, Any] | None,
) -> SimpleMetadata:
    recording_title = recording_payload.get("title")
    recording_artist = _format_artist_credit(recording_payload.get("artist-credit"))

    release_title = None
    release_year = None
    release_genre = None
    release_label = None

    if release_payload is not None:
        release_title = _first_non_empty(release_payload.get("title"))
        release_year = _extract_year_from_date(release_payload.get("date"))
        release_genre = _first_genre_name(release_payload.get("genres"))
        label_info = release_payload.get("label-info")
        if isinstance(label_info, list) and label_info:
            first_label_info = label_info[0]
            if isinstance(first_label_info, dict):
                label = first_label_info.get("label")
                if isinstance(label, dict):
                    label_name = label.get("name")
                    if isinstance(label_name, str) and label_name.strip():
                        release_label = label_name.strip()

    recording_year = _extract_year_from_date(recording_payload.get("first-release-date"))
    recording_genre = _first_genre_name(recording_payload.get("genres"))

    return SimpleMetadata(
        title=(
            recording_title.strip()
            if isinstance(recording_title, str) and recording_title.strip()
            else None
        ),
        artist=recording_artist,
        album=release_title,
        label=release_label,
        genre=release_genre or recording_genre,
        year=release_year or recording_year,
    )
