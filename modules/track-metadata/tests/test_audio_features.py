from __future__ import annotations

from pathlib import Path

import pytest

import metadata_agent
from metadata_agent import SimpleMetadata, analyze_missing_audio_features


@pytest.mark.parametrize(
    ("initial_bpm", "initial_key", "expected_bpm", "expected_key"),
    [
        (None, None, 128.12, "C#m"),
        (120.0, None, 120.0, "C#m"),
        (None, "Gm", 128.12, "Gm"),
        (120.0, "Gm", 120.0, "Gm"),
    ],
)
def test_analyze_missing_audio_features_is_safe_and_updates_only_missing(
    monkeypatch,
    initial_bpm: float | None,
    initial_key: str | None,
    expected_bpm: float | None,
    expected_key: str | None,
):
    monkeypatch.setattr(metadata_agent, "_estimate_bpm", lambda _path: 128.1234)
    monkeypatch.setattr(metadata_agent, "_estimate_key", lambda _path: "C#m")

    audio_path = Path("dummy.mp3")
    metadata = SimpleMetadata(title="t", artist="a", bpm=initial_bpm, key=initial_key)

    updated = analyze_missing_audio_features(audio_path, metadata)

    assert updated.bpm == expected_bpm
    assert updated.key == expected_key


