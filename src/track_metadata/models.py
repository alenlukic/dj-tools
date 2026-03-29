from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from mutagen.id3 import TALB, TCON, TIT2, TKEY, TPE1, TPE4, TPUB

ID3_FIELDS = {"title", "artist", "album", "label", "genre", "remixer", "key"}


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
    def from_dict(cls, data: Mapping[str, Any]) -> SimpleMetadata:
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
