from __future__ import annotations

from pathlib import Path

from mutagen.id3 import ID3, TBPM, TDRC, ID3NoHeaderError

from src.track_metadata.models import TEXT_TAG_FIELDS, SimpleMetadata, TextTagField


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


def _load_id3(path: Path, create_if_missing: bool = False) -> tuple[ID3 | None, None]:
    try:
        return ID3(str(path)), None
    except ID3NoHeaderError:
        return (ID3(), None) if create_if_missing else (None, None)


def _save_id3(path: Path, tags: ID3, container: None = None) -> None:
    _ = container
    tags.save(str(path), v2_version=4)


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
