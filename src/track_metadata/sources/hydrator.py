from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from typing import Any

import requests

from src.track_metadata.label import _apply_label_fallback
from src.track_metadata.matching import (
    _best_year,
    _extract_remixer,
    _merge_missing,
    _parse_filename_seed,
    _similarity,
)
from src.track_metadata.models import SimpleMetadata
from src.track_metadata.sources.discogs import (
    _coerce_year,
    _first_list_item,
    _first_non_empty,
    _split_discogs_title,
)
from src.track_metadata.sources.musicbrainz import (
    _first_release_id,
    _format_artist_credit,
    _musicbrainz_payload_to_metadata,
)
from src.track_metadata.utils import AUGMENTED_DIR

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
        resolved = _merge_missing(
            resolved, discogs_candidate, fields={"album", "label", "genre", "year"}
        )

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
            logging.info(
                "Ignoring low-confidence AcoustID match for %s (%.3f)",
                audio_path.name,
                best_score,
            )
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
            if value is None and field in {
                "title", "artist", "album", "label", "genre", "remixer", "year"
            }
        ]
        if not missing_fields:
            return None

        try:
            from pydantic import BaseModel
        except ImportError:
            return None

        from typing import Optional

        class MetadataResolution(BaseModel):
            title: Optional[str] = None  # noqa: UP045
            artist: Optional[str] = None  # noqa: UP045
            album: Optional[str] = None  # noqa: UP045
            label: Optional[str] = None  # noqa: UP045
            genre: Optional[str] = None  # noqa: UP045
            remixer: Optional[str] = None  # noqa: UP045
            year: Optional[int] = None  # noqa: UP045
            bpm: Optional[float] = None  # noqa: UP045
            key: Optional[str] = None  # noqa: UP045

        prompt = {
            "file_name": file_path.name,
            "current_metadata": current.to_dict(),
            "missing_fields": missing_fields,
            "candidate_sources": sources,
            "instructions": (
                "Resolve only the missing music metadata fields using the provided"
                " candidate sources. Prefer source consensus. Do not invent fields"
                " that are not clearly supported by the candidates."
                " Return null for uncertain fields."
            ),
        }

        try:
            response = self.openai_client.responses.parse(
                model=os.getenv("OPENAI_METADATA_MODEL", "gpt-5.4-mini"),
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
