
from __future__ import annotations

import hashlib
import importlib
import json
import logging
import os
import re
import time
from collections.abc import Mapping
from dataclasses import dataclass, replace
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import numpy as np
import requests
from mutagen.id3 import ID3, TALB, TBPM, TCON, TDRC, TIT2, TKEY, TPE1, TPE4, TPUB, ID3NoHeaderError

from utils import (
    AUGMENTED_DIR,
    DOWNLOAD_DIR,
    SUPPORTED_AUDIO_EXTENSIONS,
    copy_to_converted,
    discover_new_audio_files,
    ensure_directories,
    rename_file,
    reset_processing_dir,
    setup_logging,
    stage_file,
)

ID3_FIELDS = {"title", "artist", "album", "label", "genre", "remixer", "key"}

CACHE_PATH = AUGMENTED_DIR / ".metadata_cache.json"
MUSICBRAINZ_BASE_URL = "https://musicbrainz.org/ws/2"
DISCOGS_BASE_URL = "https://api.discogs.com"
HTTP_TIMEOUT_SECONDS = 15
MUSICBRAINZ_MIN_INTERVAL_SECONDS = 1.05
DISCOGS_MIN_INTERVAL_SECONDS = 1.05
DEFAULT_USER_AGENT = os.getenv(
    "MUSIC_METADATA_USER_AGENT",
    "metadata-hydrator/1.0 (https://example.com/contact)",
)

_last_musicbrainz_request_ts = 0.0
_last_discogs_request_ts = 0.0


def _import_attr(module: str, attr: str):
    return getattr(importlib.import_module(module), attr)


@dataclass
class SimpleMetadata:
    title: str | None = None
    artist: str | None = None
    album: str | None = None
    label: str | None = None
    genre: str | None = None
    remixer: str | None = None
    year: int | None = None
    bpm: float | None = None
    key: str | None = None

    def update(self, data: Mapping[str, str | int | float | None]) -> None:
        for field in ID3_FIELDS:
            value = str(data.get(field, "")).strip()

            if value:
                setattr(self, field, value)

        if data.get("year"):
            try:
                self.year = int(str(data["year"]).strip())
            except (TypeError, ValueError):
                pass

        if data.get("bpm") is not None:
            bpm_value = str(data["bpm"]).strip()

            if bpm_value:
                try:
                    self.bpm = float(bpm_value)
                except (TypeError, ValueError):
                    match = re.search(r"\d+(\.\d+)?", bpm_value)

                    if match:
                        try:
                            self.bpm = float(match.group())
                        except (TypeError, ValueError):
                            pass

    def to_dict(self) -> dict[str, str | int | float | None]:
        return {
            "title": self.title,
            "artist": self.artist,
            "album": self.album,
            "label": self.label,
            "genre": self.genre,
            "remixer": self.remixer,
            "year": self.year,
            "bpm": self.bpm,
            "key": self.key,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "SimpleMetadata":
        metadata = cls()
        metadata.update(
            {
                "title": data.get("title"),
                "artist": data.get("artist"),
                "album": data.get("album"),
                "label": data.get("label"),
                "genre": data.get("genre"),
                "remixer": data.get("remixer"),
                "year": data.get("year"),
                "bpm": data.get("bpm"),
                "key": data.get("key"),
            }
        )
        return metadata


@dataclass(frozen=True)
class TextTagField:
    attr: str
    key: str
    frame_factory: type
    clear_if_missing: bool = True


TEXT_TAG_FIELDS: tuple[TextTagField, ...] = (
    TextTagField("title", "TIT2", TIT2),
    TextTagField("artist", "TPE1", TPE1),
    TextTagField("album", "TALB", TALB, clear_if_missing=False),
    TextTagField("label", "TPUB", TPUB),
    TextTagField("genre", "TCON", TCON),
    TextTagField("remixer", "TPE4", TPE4),
    TextTagField("key", "TKEY", TKEY),
)


def _extract_text_tag(tags: ID3, key: str) -> str | None:
    frame = tags.get(key)
    if frame is None:
        return None

    text = frame.text[0] if getattr(frame, "text", None) else None
    if isinstance(text, str):
        stripped = text.strip()
        return stripped or None

    return None


def _text_tags_from_id3(tags: ID3) -> dict[str, str | None]:
    return {field.attr: _extract_text_tag(tags, field.key) for field in TEXT_TAG_FIELDS}


def _extract_year(tags: ID3) -> int | None:
    frame = tags.get("TDRC")
    if frame is None or not getattr(frame, "text", None):
        return None

    try:
        return int(str(frame.text[0])[:4])
    except (TypeError, ValueError):
        return None


def _extract_bpm(tags: ID3) -> float | None:
    frame = tags.get("TBPM")
    if frame is None or not getattr(frame, "text", None):
        return None

    try:
        return float(str(frame.text[0]))
    except (TypeError, ValueError):
        return None


def _write_text_tag(tags: ID3, field: TextTagField, value: str | None) -> None:
    if value:
        tags[field.key] = field.frame_factory(encoding=3, text=value)
        return

    if field.clear_if_missing and field.key in tags:
        del tags[field.key]


def _write_year_tag(tags: ID3, year: int | None) -> None:
    if year:
        tags["TDRC"] = TDRC(encoding=3, text=str(year))
        return

    if "TDRC" in tags:
        del tags["TDRC"]


def _write_bpm_tag(tags: ID3, bpm: float | None) -> None:
    if bpm is not None:
        bpm_value = f"{bpm:.2f}".rstrip("0").rstrip(".")
        tags["TBPM"] = TBPM(encoding=3, text=bpm_value or str(bpm))
        return

    if "TBPM" in tags:
        del tags["TBPM"]


def _normalize_label_value(label: str | None) -> str | None:
    if label is None:
        return None

    return label.strip() or None


def _apply_label_fallback(metadata: SimpleMetadata) -> None:
    label = _normalize_label_value(metadata.label)
    if label is None:
        metadata.label = "CDR"
        return

    simplified = re.sub(r"[\s\-]+", " ", label).lower()
    if (
        "white label" in simplified
        or simplified == "whitelabel"
        or "self release" in simplified
        or "self released" in simplified
        or simplified == "self"
    ):
        metadata.label = "CDR"
    else:
        metadata.label = label


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


def _merge_missing(target: SimpleMetadata, candidate: SimpleMetadata | None, *, fields: set[str] | None = None) -> SimpleMetadata:
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


def read_existing_metadata(path: Path) -> SimpleMetadata:
    metadata = SimpleMetadata()
    tags, _ = _load_id3(path)
    if tags is None:
        return metadata

    text_values = _text_tags_from_id3(tags)
    year = _extract_year(tags)
    bpm = _extract_bpm(tags)

    return SimpleMetadata(**text_values, year=year, bpm=bpm)


def write_tags(path: Path, metadata: SimpleMetadata) -> None:
    tags, container = _load_id3(path, create_if_missing=True)
    tag_values = metadata.to_dict()

    for field in TEXT_TAG_FIELDS:
        value = tag_values.get(field.attr)
        _write_text_tag(tags, field, value if isinstance(value, str) else None)

    _write_year_tag(tags, metadata.year)
    _write_bpm_tag(tags, metadata.bpm)

    _save_id3(path, tags, container)


class MetadataHydrator:
    def __init__(self) -> None:
        self.http = requests.Session()
        self.http.headers.update({"User-Agent": DEFAULT_USER_AGENT})
        self.cache = self._load_cache()
        self.openai_client = self._build_openai_client()

    def _build_openai_client(self) -> Any | None:
        if not os.getenv("OPENAI_API_KEY"):
            return None

        try:
            from openai import OpenAI
            from pydantic import BaseModel
        except ImportError:
            return None

        self._resolution_model = BaseModel  # marker to validate imports succeeded
        return OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    def hydrate(self, file_path: Path, existing: SimpleMetadata) -> SimpleMetadata:
        cache_key = self._file_cache_key(file_path)
        cached = self.cache.get(cache_key, {}).get("final")
        if isinstance(cached, dict):
            logging.info("Using cached metadata for %s", file_path.name)
            return SimpleMetadata.from_dict(cached)

        seed = _merge_missing(existing, _parse_filename_seed(file_path))
        sources: list[dict[str, Any]] = []

        acoustid_candidate = self._lookup_acoustid(file_path)
        if acoustid_candidate is not None:
            sources.append({"source": "acoustid", "metadata": acoustid_candidate.to_dict()})

        musicbrainz_candidate = self._lookup_musicbrainz(seed, file_path)
        if musicbrainz_candidate is not None:
            sources.append({"source": "musicbrainz", "metadata": musicbrainz_candidate.to_dict()})

        discogs_candidate = self._lookup_discogs(seed)
        if discogs_candidate is not None:
            sources.append({"source": "discogs", "metadata": discogs_candidate.to_dict()})

        resolved = replace(seed)
        resolved = _merge_missing(resolved, acoustid_candidate)
        resolved = _merge_missing(resolved, musicbrainz_candidate)
        resolved = _merge_missing(resolved, discogs_candidate, fields={"album", "label", "genre", "year"})

        llm_candidate = self._resolve_from_candidates(file_path, resolved, sources)
        if llm_candidate is not None:
            resolved = _merge_missing(resolved, llm_candidate)

        if resolved.remixer is None:
            resolved.remixer = _extract_remixer(resolved.title)

        if resolved.year is None:
            resolved.year = _best_year(
                existing.year,
                acoustid_candidate.year if acoustid_candidate else None,
                musicbrainz_candidate.year if musicbrainz_candidate else None,
                discogs_candidate.year if discogs_candidate else None,
            )

        _apply_label_fallback(resolved)
        self.cache.setdefault(cache_key, {})["final"] = resolved.to_dict()
        self._save_cache()
        return resolved

    def _load_cache(self) -> dict[str, dict[str, Any]]:
        if not CACHE_PATH.exists():
            return {}

        try:
            raw = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                return raw
        except (OSError, json.JSONDecodeError):
            logging.warning("Failed to read metadata cache at %s", CACHE_PATH)

        return {}

    def _save_cache(self) -> None:
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        CACHE_PATH.write_text(
            json.dumps(self.cache, indent=2, ensure_ascii=False, sort_keys=True),
            encoding="utf-8",
        )

    def _file_cache_key(self, file_path: Path) -> str:
        stat = file_path.stat()
        signature = f"{file_path.name}|{stat.st_size}|{stat.st_mtime_ns}"
        return hashlib.sha1(signature.encode("utf-8")).hexdigest()

    def _lookup_acoustid(self, audio_path: Path) -> SimpleMetadata | None:
        api_key = os.getenv("ACOUSTID_API_KEY")
        if not api_key:
            return None

        try:
            import acoustid
        except ImportError:
            logging.info("Skipping AcoustID lookup; pyacoustid is not installed.")
            return None

        try:
            matches = list(acoustid.match(api_key, str(audio_path)))
        except Exception as exc:
            logging.warning("AcoustID lookup failed for %s: %s", audio_path.name, exc)
            return None

        if not matches:
            return None

        best_score, recording_id, title, artist = max(matches, key=lambda item: float(item[0]))
        if float(best_score) < 0.80:
            logging.info("Ignoring low-confidence AcoustID match for %s (%.3f)", audio_path.name, best_score)
            return None

        metadata = SimpleMetadata(title=title or None, artist=artist or None)
        mb_metadata = self._lookup_musicbrainz_recording(recording_id)
        metadata = _merge_missing(metadata, mb_metadata)

        logging.info(
            "AcoustID matched %s -> %s / %s (score=%.3f)",
            audio_path.name,
            metadata.artist or artist,
            metadata.title or title,
            best_score,
        )
        return metadata

    def _lookup_musicbrainz(self, seed: SimpleMetadata, file_path: Path) -> SimpleMetadata | None:
        title = seed.title or _parse_filename_seed(file_path).title
        if not title:
            return None

        query_parts = []
        if seed.artist:
            query_parts.append(seed.artist)
        query_parts.append(title)
        query = " ".join(query_parts)

        try:
            payload = self._musicbrainz_get(
                "/recording",
                params={"query": query, "fmt": "json", "limit": 5, "dismax": "true"},
            )
        except Exception as exc:
            logging.warning("MusicBrainz search failed for %s: %s", file_path.name, exc)
            return None

        recordings = payload.get("recordings", [])
        if not isinstance(recordings, list) or not recordings:
            return None

        best = self._select_best_musicbrainz_recording(recordings, seed)
        if best is None:
            return None

        recording_id = best.get("id")
        if not isinstance(recording_id, str) or not recording_id:
            return None

        metadata = self._lookup_musicbrainz_recording(recording_id)
        if metadata is None:
            return None

        logging.info(
            "MusicBrainz matched %s -> %s / %s",
            file_path.name,
            metadata.artist or seed.artist,
            metadata.title or seed.title,
        )
        return metadata

    def _select_best_musicbrainz_recording(
        self,
        recordings: list[dict[str, Any]],
        seed: SimpleMetadata,
    ) -> dict[str, Any] | None:
        scored: list[tuple[float, dict[str, Any]]] = []
        for recording in recordings:
            title = recording.get("title")
            artist = _format_artist_credit(recording.get("artist-credit"))
            title_score = _similarity(seed.title, title)
            artist_score = _similarity(seed.artist, artist) if seed.artist else 0.8
            release_title = None
            releases = recording.get("releases")
            if isinstance(releases, list) and releases:
                first_release = releases[0]
                if isinstance(first_release, dict):
                    release_title = first_release.get("title")
            release_score = _similarity(seed.album, release_title) if seed.album else 0.5
            total = (title_score * 0.5) + (artist_score * 0.35) + (release_score * 0.15)
            scored.append((total, recording))

        scored.sort(key=lambda item: item[0], reverse=True)
        if not scored or scored[0][0] < 0.72:
            return None
        return scored[0][1]

    def _lookup_musicbrainz_recording(self, recording_id: str) -> SimpleMetadata | None:
        try:
            payload = self._musicbrainz_get(
                f"/recording/{recording_id}",
                params={"fmt": "json", "inc": "artists+releases+genres"},
            )
        except Exception as exc:
            logging.warning("MusicBrainz recording lookup failed for %s: %s", recording_id, exc)
            return None

        release_id = _first_release_id(payload)
        release_payload: dict[str, Any] | None = None
        if release_id:
            try:
                release_payload = self._musicbrainz_get(
                    f"/release/{release_id}",
                    params={"fmt": "json", "inc": "labels+genres"},
                )
            except Exception as exc:
                logging.warning("MusicBrainz release lookup failed for %s: %s", release_id, exc)

        return _musicbrainz_payload_to_metadata(payload, release_payload)

    def _musicbrainz_get(self, path: str, *, params: Mapping[str, Any]) -> dict[str, Any]:
        global _last_musicbrainz_request_ts
        self._respect_rate_limit("musicbrainz")
        response = self.http.get(
            f"{MUSICBRAINZ_BASE_URL}{path}",
            params=params,
            timeout=HTTP_TIMEOUT_SECONDS,
        )
        _last_musicbrainz_request_ts = time.monotonic()
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            raise ValueError("MusicBrainz returned a non-object payload")
        return data

    def _lookup_discogs(self, seed: SimpleMetadata) -> SimpleMetadata | None:
        token = os.getenv("DISCOGS_TOKEN")
        if not token or not seed.title:
            return None

        params: dict[str, Any] = {
            "type": "release",
            "per_page": 5,
            "track": seed.title,
        }
        if seed.artist:
            params["artist"] = seed.artist
        if seed.album:
            params["release_title"] = seed.album

        headers = {"Authorization": f"Discogs token={token}", "User-Agent": DEFAULT_USER_AGENT}

        try:
            self._respect_rate_limit("discogs")
            response = self.http.get(
                f"{DISCOGS_BASE_URL}/database/search",
                params=params,
                headers=headers,
                timeout=HTTP_TIMEOUT_SECONDS,
            )
            global _last_discogs_request_ts
            _last_discogs_request_ts = time.monotonic()
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            logging.warning("Discogs lookup failed for %s - %s: %s", seed.artist, seed.title, exc)
            return None

        results = data.get("results", [])
        if not isinstance(results, list) or not results:
            return None

        best_result: dict[str, Any] | None = None
        best_score = 0.0
        for result in results:
            title = result.get("title")
            artist_guess, release_guess = _split_discogs_title(title)
            title_score = _similarity(seed.title, release_guess or title)
            artist_score = _similarity(seed.artist, artist_guess) if seed.artist else 0.8
            total = (title_score * 0.55) + (artist_score * 0.45)
            if total > best_score:
                best_score = total
                best_result = result

        if best_result is None or best_score < 0.72:
            return None

        metadata = SimpleMetadata(
            album=_first_non_empty(best_result.get("title"), seed.album),
            year=_coerce_year(best_result.get("year")),
            genre=_first_list_item(best_result.get("genre")),
            label=_first_list_item(best_result.get("label")),
        )
        if metadata.album and " - " in metadata.album:
            _, release_title = _split_discogs_title(metadata.album)
            metadata.album = release_title or metadata.album

        logging.info(
            "Discogs matched %s / %s (score=%.3f)",
            seed.artist,
            seed.title,
            best_score,
        )
        return metadata

    def _resolve_from_candidates(
        self,
        file_path: Path,
        current: SimpleMetadata,
        sources: list[dict[str, Any]],
    ) -> SimpleMetadata | None:
        if self.openai_client is None or not sources:
            return None

        missing_fields = [
            field
            for field, value in current.to_dict().items()
            if value is None and field in {"title", "artist", "album", "label", "genre", "remixer", "year"}
        ]
        if not missing_fields:
            return None

        try:
            from pydantic import BaseModel
        except ImportError:
            return None

        from typing import Optional

        class MetadataResolution(BaseModel):
            title: Optional[str] = None
            artist: Optional[str] = None
            album: Optional[str] = None
            label: Optional[str] = None
            genre: Optional[str] = None
            remixer: Optional[str] = None
            year: Optional[int] = None
            bpm: Optional[float] = None
            key: Optional[str] = None

        prompt = {
            "file_name": file_path.name,
            "current_metadata": current.to_dict(),
            "missing_fields": missing_fields,
            "candidate_sources": sources,
            "instructions": (
                "Resolve only the missing music metadata fields using the provided candidate sources. "
                "Prefer source consensus. Do not invent fields that are not clearly supported by the candidates. "
                "Return null for uncertain fields."
            ),
        }

        try:
            response = self.openai_client.responses.parse(
                model=os.getenv("OPENAI_METADATA_MODEL", "gpt-4o-mini"),
                temperature=0,
                input=[
                    {
                        "role": "system",
                        "content": "You resolve music metadata from structured database results.",
                    },
                    {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
                ],
                text_format=MetadataResolution,
            )
            parsed = response.output_parsed
        except Exception as exc:
            logging.warning("LLM metadata resolution failed for %s: %s", file_path.name, exc)
            return None

        if parsed is None:
            return None

        return SimpleMetadata.from_dict(parsed.model_dump())

    def _respect_rate_limit(self, provider: str) -> None:
        if provider == "musicbrainz":
            global _last_musicbrainz_request_ts
            elapsed = time.monotonic() - _last_musicbrainz_request_ts
            delay = MUSICBRAINZ_MIN_INTERVAL_SECONDS - elapsed
        elif provider == "discogs":
            global _last_discogs_request_ts
            elapsed = time.monotonic() - _last_discogs_request_ts
            delay = DISCOGS_MIN_INTERVAL_SECONDS - elapsed
        else:
            return

        if delay > 0:
            time.sleep(delay)


def build_metadata_agent() -> MetadataHydrator:
    return MetadataHydrator()


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
        title=recording_title.strip() if isinstance(recording_title, str) and recording_title.strip() else None,
        artist=recording_artist,
        album=release_title,
        label=release_label,
        genre=release_genre or recording_genre,
        year=release_year or recording_year,
    )


def _first_genre_name(value: Any) -> str | None:
    if not isinstance(value, list):
        return None

    for item in value:
        if isinstance(item, dict):
            name = item.get("name")
            if isinstance(name, str) and name.strip():
                return name.strip()
    return None


def analyze_missing_audio_features(audio_path: Path, metadata: SimpleMetadata) -> SimpleMetadata:
    needs_bpm = metadata.bpm is None
    needs_key = metadata.key is None
    if not (needs_bpm or needs_key):
        return metadata

    if needs_bpm:
        bpm_estimate: float | None = None
        try:
            bpm_estimate = _estimate_bpm(audio_path)
        except Exception as exc:  # pragma: no cover - external library behaviour
            logging.warning("BPM analysis failed for %s: %s", audio_path.name, exc)
        if bpm_estimate is not None:
            metadata.bpm = round(bpm_estimate, 2)
            logging.info("Estimated BPM for %s: %.2f", audio_path.name, metadata.bpm)

    if needs_key:
        key_estimate: str | None = None
        try:
            key_estimate = _estimate_key(audio_path)
        except Exception as exc:  # pragma: no cover - external library behaviour
            logging.warning("Key analysis failed for %s: %s", audio_path.name, exc)
        if key_estimate is not None:
            metadata.key = key_estimate
            logging.info("Estimated key for %s: %s", audio_path.name, metadata.key)

    return metadata


def _estimate_bpm(audio_path: Path) -> float | None:
    try:
        DBNBeatTrackingProcessor = _import_attr(
            "madmom.features.beats", "DBNBeatTrackingProcessor"
        )
        RNNBeatProcessor = _import_attr("madmom.features.beats", "RNNBeatProcessor")
    except ImportError as exc:
        raise RuntimeError(
            "madmom is required for BPM estimation. "
            "Install this module's requirements to enable audio analysis."
        ) from exc

    beat_processor = RNNBeatProcessor()
    activation = beat_processor(str(audio_path))
    beats = DBNBeatTrackingProcessor(fps=100)(activation)
    if len(beats) < 2:
        return None

    intervals = np.diff(beats)  # type: ignore[arg-type]
    if intervals.size == 0:  # type: ignore[attr-defined]
        return None

    positive_intervals = intervals[intervals > 0]
    if positive_intervals.size == 0:  # type: ignore[attr-defined]
        return None

    median_interval = float(np.median(positive_intervals))  # type: ignore[arg-type]
    if median_interval <= 0:
        return None

    return 60.0 / median_interval


def _estimate_key(audio_path: Path) -> str | None:
    try:
        CNNKeyRecognitionProcessor = _import_attr(
            "madmom.features.key", "CNNKeyRecognitionProcessor"
        )
        key_prediction_to_label = _import_attr(
            "madmom.features.key", "key_prediction_to_label"
        )
    except ImportError as exc:
        raise RuntimeError(
            "madmom is required for key estimation. "
            "Install this module's requirements to enable audio analysis."
        ) from exc

    key_processor = CNNKeyRecognitionProcessor()
    prediction = key_processor(str(audio_path))
    if prediction is None:
        return None

    label = key_prediction_to_label(prediction)
    if isinstance(label, str):
        return label

    return None


def _load_id3(path: Path, create_if_missing: bool = False) -> tuple[ID3 | None, None]:
    try:
        return ID3(str(path)), None
    except ID3NoHeaderError:
        return (ID3(), None) if create_if_missing else (None, None)


def _save_id3(path: Path, tags: ID3, container: None = None) -> None:
    _ = container
    tags.save(str(path), v2_version=4)


def purge_invalid_augmented_files(augmented_dir: Path = AUGMENTED_DIR) -> None:
    """Remove augmented files that lack readable tags or a title."""
    if not augmented_dir.exists():
        return

    for candidate in augmented_dir.iterdir():
        if not (candidate.is_file() and candidate.suffix.lower() in SUPPORTED_AUDIO_EXTENSIONS):
            continue

        try:
            metadata = read_existing_metadata(candidate)
        except Exception:
            metadata = SimpleMetadata()

        if metadata.title:
            continue

        logging.info("Deleting %s from augmented; missing tags or title", candidate.name)
        candidate.unlink(missing_ok=True)


def enrich_metadata(agent: MetadataHydrator, file_path: Path, existing: SimpleMetadata) -> SimpleMetadata:
    enriched = agent.hydrate(file_path, existing)
    logging.info(
        "Hydrated metadata from structured sources:\n%s",
        json.dumps(enriched.to_dict(), indent=2, ensure_ascii=False),
    )
    return enriched


def process_file(agent: MetadataHydrator, source: Path) -> None:
    logging.info("--- Processing '%s' ---", source.name)
    staged = stage_file(source)
    existing = read_existing_metadata(staged)
    existing_json = json.dumps(existing.to_dict(), indent=2, ensure_ascii=False)

    logging.info("Existing metadata:\n%s", existing_json)
    enriched = enrich_metadata(agent, staged, existing)
    structured_metadata = enriched.to_dict()

    logging.info(
        "Structured-source metadata:\n%s",
        json.dumps(structured_metadata, indent=2, ensure_ascii=False),
    )
    analyze_missing_audio_features(staged, enriched)
    final_metadata = enriched.to_dict()

    if final_metadata != structured_metadata:
        final_json = json.dumps(final_metadata, indent=2, ensure_ascii=False)
        logging.info("After audio analysis:\n%s", final_json)
    else:
        logging.info("Final metadata:\n%s", json.dumps(final_metadata, indent=2, ensure_ascii=False))

    write_tags(staged, enriched)
    renamed = rename_file(staged, enriched.artist, enriched.title)
    final_copy = copy_to_converted(renamed, original_name=source.name)

    logging.info("Final file copied to '%s'", final_copy)


def main() -> None:
    setup_logging()
    ensure_directories()
    purge_invalid_augmented_files()
    reset_processing_dir()

    files = discover_new_audio_files()
    logging.info("Discovered %d file(s).", len(files))
    if not files:
        logging.info("No new audio files detected in %s", DOWNLOAD_DIR)
        return

    logging.info("Building metadata hydrator")
    agent = build_metadata_agent()

    for source in files:
        logging.info("Processing %s", source.name)
        try:
            process_file(agent, source)
        except Exception as exc:  # pragma: no cover - demo script
            logging.exception("Failed to process %s: %s", source, exc)
    logging.info("Processing complete.")


if __name__ == "__main__":
    main()
