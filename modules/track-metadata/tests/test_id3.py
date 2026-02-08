from __future__ import annotations

import shutil
from pathlib import Path

from mutagen.id3 import ID3

from metadata_agent import (
    SimpleMetadata,
    purge_invalid_augmented_files,
    read_existing_metadata,
    write_tags,
)

TEST_DATA_DIR = Path(__file__).resolve().parent.parent / "test_data"


def _copy_sample(tmp_path: Path, filename: str) -> Path:
    source = TEST_DATA_DIR / filename
    destination = tmp_path / filename
    shutil.copy2(source, destination)
    return destination


def test_read_existing_metadata_round_trip(tmp_path):
    audio_path = _copy_sample(tmp_path, "[01A - Abm - 086.00] Cell - Traffic (Live).mp3")
    expected = SimpleMetadata(
        title="Traffic (Live)",
        artist="Cell",
        album="Live Sessions",
        label="Ultimae Records",
        genre="Electronic",
        year=2024,
        bpm=86.0,
        key="Abm",
    )
    write_tags(audio_path, expected)

    loaded = read_existing_metadata(audio_path)

    assert loaded.to_dict() == expected.to_dict()


def test_write_tags_preserves_existing_album(tmp_path):
    audio_path = _copy_sample(
        tmp_path, "[01A - Abm - 110.00] Nova ft. AES Dana - Kalaallit Nunaat.aiff"
    )
    write_tags(
        audio_path,
        SimpleMetadata(
            title="Old Title",
            artist="Old Artist",
            album="Existing Album",
        ),
    )

    write_tags(audio_path, SimpleMetadata(title="New Title", artist="New Artist"))

    updated = read_existing_metadata(audio_path)
    assert updated.album == "Existing Album"
    assert updated.title == "New Title"
    assert updated.artist == "New Artist"


def test_write_and_read_remixer(tmp_path):
    audio_path = _copy_sample(tmp_path, "[01A - Abm - 086.00] Cell - Traffic (Live).mp3")
    metadata = SimpleMetadata(title="Traffic (Live)", artist="Cell", remixer="Example Remixer")

    write_tags(audio_path, metadata)
    loaded = read_existing_metadata(audio_path)

    assert loaded.remixer == "Example Remixer"
    assert loaded.title == metadata.title
    assert loaded.artist == metadata.artist


def test_write_tags_handles_numeric_fields(tmp_path):
    audio_path = _copy_sample(tmp_path, "[01A - Abm - 086.00] Cell - Traffic (Live).mp3")
    metadata = SimpleMetadata(
        title="Track Title",
        artist="Artist",
        label="Label",
        genre="Genre",
        year=2025,
        bpm=128.5,
        key="G#m",
    )

    write_tags(audio_path, metadata)
    tags = ID3(audio_path)

    assert str(tags["TDRC"].text[0]).startswith("2025")
    assert float(tags["TBPM"].text[0]) == metadata.bpm
    assert tags["TKEY"].text[0] == metadata.key


def test_read_existing_metadata_aiff(tmp_path):
    audio_path = _copy_sample(
        tmp_path, "[01A - Abm - 110.00] Nova ft. AES Dana - Kalaallit Nunaat.aiff"
    )
    write_tags(audio_path, SimpleMetadata(title="Title A", artist="Artist A"))

    loaded = read_existing_metadata(audio_path)

    assert loaded.title == "Title A"
    assert loaded.artist == "Artist A"


def test_write_tags_round_trip_aiff(tmp_path):
    audio_path = _copy_sample(
        tmp_path, "[01A - Abm - 110.00] Nova ft. AES Dana - Kalaallit Nunaat.aiff"
    )
    metadata = SimpleMetadata(
        title="Kalaallit Nunaat",
        artist="Nova ft. AES Dana",
        album="Single",
        label="Ultimae",
        genre="Ambient",
        year=2025,
        bpm=110.0,
        key="Abm",
    )

    write_tags(audio_path, metadata)
    loaded = read_existing_metadata(audio_path)

    assert loaded.to_dict() == metadata.to_dict()


def test_purge_invalid_augmented_files(tmp_path):
    augmented_dir = tmp_path / "augmented"
    augmented_dir.mkdir()

    valid_src = TEST_DATA_DIR / "[01A - Abm - 086.00] Cell - Traffic (Live).mp3"
    valid_copy = augmented_dir / "valid.mp3"
    shutil.copy2(valid_src, valid_copy)
    write_tags(valid_copy, SimpleMetadata(title="Valid Title", artist="Artist"))

    invalid_file = augmented_dir / "invalid.mp3"
    invalid_file.write_bytes(b"")  # no tags

    purge_invalid_augmented_files(augmented_dir)

    assert valid_copy.exists()
    assert not invalid_file.exists()
