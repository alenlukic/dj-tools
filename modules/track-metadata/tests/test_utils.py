from __future__ import annotations

import json

from utils import (
    copy_to_converted,
    discover_new_audio_files,
    ensure_directories,
    log_agent_response,
    rename_file,
    reset_processing_dir,
    sanitize_filename,
    stage_file,
)


def test_ensure_and_reset_processing_dir(tmp_path):
    download_dir = tmp_path / "downloads"
    processing_dir = tmp_path / "processing"
    augmented_dir = tmp_path / "augmented"
    ensure_directories(download_dir, processing_dir, augmented_dir)

    (processing_dir / "temp.txt").write_text("data")
    (processing_dir / "nested").mkdir()
    (processing_dir / "nested" / "item.txt").write_text("more")

    reset_processing_dir(processing_dir)

    assert list(processing_dir.iterdir()) == []


def test_stage_and_copy_to_converted(tmp_path):
    download_dir = tmp_path / "downloads"
    processing_dir = tmp_path / "processing"
    augmented_dir = tmp_path / "augmented"
    ensure_directories(download_dir, processing_dir, augmented_dir)

    source = download_dir / "sample.mp3"
    source.write_text("content")

    staged = stage_file(source, processing_dir)
    copied = copy_to_converted(staged, augmented_dir)

    assert staged.read_text() == "content"
    assert copied.read_text() == "content"
    assert copied.name == staged.name


def test_copy_to_converted_preserves_original_name(tmp_path):
    processing_dir = tmp_path / "processing"
    augmented_dir = tmp_path / "augmented"
    ensure_directories(tmp_path / "downloads", processing_dir, augmented_dir)

    renamed = processing_dir / "renamed.mp3"
    renamed.write_text("audio")

    copied = copy_to_converted(renamed, augmented_dir, original_name="original name.mp3")

    assert copied.exists()
    assert copied.name == "original name.mp3"


def test_sanitize_and_rename_file(tmp_path):
    processing_dir = tmp_path / "processing"
    augmented_dir = tmp_path / "augmented"
    ensure_directories(tmp_path / "downloads", processing_dir, augmented_dir)

    source = processing_dir / "file?.mp3"
    source.write_text("audio")

    cleaned = sanitize_filename("A?Title*")
    assert "?" not in cleaned
    assert "*" not in cleaned

    renamed = rename_file(source, "An Artist", "A / Title")

    assert renamed.exists()
    assert "?" not in renamed.name
    assert renamed.name.startswith("An Artist - A Title")


def test_log_agent_response(tmp_path):
    log_path = tmp_path / "logs" / "session.log"

    log_agent_response(
        file_name="track.mp3",
        raw_text='{"title": "Example"}',
        messages=[{"role": "user", "content": "Test"}],
        log_file_path=log_path,
    )

    assert log_path.exists()
    entry = json.loads(log_path.read_text().splitlines()[0])
    assert entry["file"] == "track.mp3"
    assert entry["raw_response"] == '{"title": "Example"}'


def test_discover_new_audio_files_skips_existing_augmented(tmp_path):
    download_dir = tmp_path / "downloads"
    processing_dir = tmp_path / "processing"
    augmented_dir = tmp_path / "augmented"
    ensure_directories(download_dir, processing_dir, augmented_dir)

    in_downloads = download_dir / "track1.mp3"
    in_downloads.write_text("a")
    also_in_downloads = download_dir / "track2.mp3"
    also_in_downloads.write_text("b")

    already_augmented = augmented_dir / in_downloads.name
    already_augmented.write_text("a-augmented")

    discovered = discover_new_audio_files(download_dir=download_dir, augmented_dir=augmented_dir)

    assert also_in_downloads in discovered
    assert in_downloads not in discovered
