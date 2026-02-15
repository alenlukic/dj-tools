from __future__ import annotations

import json
import logging
import os
import re
import importlib
from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import numpy as np
from mutagen.id3 import ID3, TALB, TBPM, TCON, TDRC, TIT2, TKEY, TPE1, TPE4, TPUB, ID3NoHeaderError

from utils import (
    AUGMENTED_DIR,
    DOWNLOAD_DIR,
    SUPPORTED_AUDIO_EXTENSIONS,
    copy_to_converted,
    discover_new_audio_files,
    ensure_directories,
    log_agent_response,
    rename_file,
    reset_processing_dir,
    setup_logging,
    stage_file,
)

ID3_FIELDS = {"title", "artist", "album", "label", "genre", "remixer", "key"}


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


def build_metadata_agent():
    try:
        from langchain_community.tools.tavily_search import TavilySearchResults
        from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
        from langchain_openai import ChatOpenAI
        from langgraph.prebuilt import create_react_agent

        from tools.music_metadata_search_tool import MusicMetadataSearchTool
    except ImportError as exc:
        raise RuntimeError(
            "Optional dependencies for metadata enrichment are not installed. "
            "Install this module's requirements to enable the agent workflow."
        ) from exc

    llm = ChatOpenAI(model="gpt-5", temperature=1, api_key=os.environ["OPENAI_API_KEY"])
    tavily_tool = TavilySearchResults(
        max_results=20,
        search_depth="advanced",
        include_answer=True,
        include_raw_content=True,
    )
    search_tool = MusicMetadataSearchTool(tavily_tool)

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are an assistant that enriches audio metadata. "
                "Use the MusicMetadataSearch tool to confirm or augment missing fields. "
                "Always return a compact JSON object with some or all of the keys: "
                "title, artist, album, label, genre, remixer, year, bpm, key.",
            ),
            MessagesPlaceholder(variable_name="messages"),
        ]
    )

    return create_react_agent(llm, [search_tool], prompt=prompt)


def parse_agent_metadata(raw_text: str) -> dict[str, str | int | float]:
    match = re.search(r"\{.*\}", raw_text, flags=re.DOTALL)
    if not match:
        return {}

    try:
        data = json.loads(match.group())
        if isinstance(data, dict):
            return {k: v for k, v in data.items() if isinstance(v, (str, int, float))}
    except json.JSONDecodeError:
        return {}

    return {}


def extract_message_text(payload: Mapping[str, Any]) -> str:
    messages = payload.get("messages", [])
    if not messages:
        return ""

    last_message = messages[-1]
    content = getattr(last_message, "content", last_message)
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        texts = []
        for chunk in content:
            if isinstance(chunk, dict) and chunk.get("type") == "text":
                texts.append(chunk.get("text", ""))

        return "\n".join(texts)

    return str(content)


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


def enrich_metadata(agent, file_path: Path, existing: SimpleMetadata) -> SimpleMetadata:
    existing_json = json.dumps(existing.to_dict(), ensure_ascii=False)
    user_message = (
        f"File name: {file_path.name}\n"
        f"Existing metadata: {existing_json}\n"
        "Respond with updated metadata JSON only."
    )

    messages = [("user", user_message)]
    response = agent.invoke({"messages": messages})
    raw_text = extract_message_text(response)

    log_agent_response(file_path.name, raw_text, messages)

    metadata_updates = parse_agent_metadata(raw_text)
    enriched = replace(existing)
    enriched.update(metadata_updates)

    _apply_label_fallback(enriched)

    return enriched


def process_file(agent, source: Path) -> None:
    logging.info("--- Processing '%s' ---", source.name)
    staged = stage_file(source)
    existing = read_existing_metadata(staged)
    existing_json = json.dumps(existing.to_dict(), indent=2, ensure_ascii=False)

    logging.info("Existing metadata:\n%s", existing_json)
    enriched = enrich_metadata(agent, staged, existing)
    agent_metadata = enriched.to_dict()
    agent_json = json.dumps(agent_metadata, indent=2, ensure_ascii=False)

    logging.info("Agent metadata:\n%s", agent_json)
    analyze_missing_audio_features(staged, enriched)
    final_metadata = enriched.to_dict()

    if final_metadata != agent_metadata:
        final_json = json.dumps(final_metadata, indent=2, ensure_ascii=False)
        logging.info("After audio analysis:\n%s", final_json)
    else:
        logging.info("Final metadata:\n%s", agent_json)

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

    if not os.getenv("OPENAI_API_KEY"):
        logging.error("OPENAI_API_KEY is not set. Ensure your environment is loaded and try again.")
        return

    logging.info("Building metadata enrichment agent")
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
