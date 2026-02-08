from __future__ import annotations

import json
import logging
import os
import re
import shutil
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import Any

LOG_FORMAT = "%(asctime)s %(levelname)s:%(message)s"


def _env_path(var_name: str, default: str) -> Path:
    return Path(os.getenv(var_name, default)).expanduser()


DOWNLOAD_DIR = _env_path("TRACK_METADATA_DOWNLOAD_DIR", "downloads")
PROCESSING_DIR = _env_path("TRACK_METADATA_PROCESSING_DIR", "processing")
AUGMENTED_DIR = _env_path("TRACK_METADATA_AUGMENTED_DIR", "augmented")
LOG_DIR = _env_path("TRACK_METADATA_LOG_DIR", "logs")
RUN_START = os.getenv("TRACK_METADATA_RUN_START", datetime.now().strftime("%Y%m%dT%H%M%S"))
LOG_FILE_PATH = LOG_DIR / f"{RUN_START}.log"

SUPPORTED_AUDIO_EXTENSIONS = {".mp3", ".aiff", ".aif"}
SANITIZE_PATTERN = re.compile(r"[^\w.\- &'()\[\]]+")


def setup_logging(level: int = logging.INFO) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=level, format=LOG_FORMAT)


def log_dependency_warning(message: str) -> None:
    logging.warning(message)


def ensure_directories(
    download_dir: Path = DOWNLOAD_DIR,
    processing_dir: Path = PROCESSING_DIR,
    augmented_dir: Path = AUGMENTED_DIR,
) -> None:
    for path in (download_dir, processing_dir, augmented_dir, LOG_DIR):
        path.mkdir(parents=True, exist_ok=True)


def reset_processing_dir(processing_dir: Path = PROCESSING_DIR) -> None:
    if not processing_dir.exists():
        return
    for child in processing_dir.iterdir():
        if child.is_file() or child.is_symlink():
            child.unlink(missing_ok=True)
        else:
            shutil.rmtree(child, ignore_errors=True)


def discover_new_audio_files(
    download_dir: Path = DOWNLOAD_DIR,
    supported_extensions: Iterable[str] = SUPPORTED_AUDIO_EXTENSIONS,
    augmented_dir: Path = AUGMENTED_DIR,
) -> list[Path]:
    if not download_dir.exists():
        return []
    files: list[Path] = []
    for candidate in sorted(download_dir.iterdir()):
        if candidate.is_file() and candidate.suffix.lower() in supported_extensions:
            destination = augmented_dir / candidate.name
            if destination.exists():
                logging.info("Skipping %s; already present in augmented directory", candidate.name)
                continue
            files.append(candidate)
    return files


def stage_file(source: Path, processing_dir: Path = PROCESSING_DIR) -> Path:
    destination = processing_dir / source.name
    shutil.copy2(source, destination)
    logging.info("Staged %s", destination.name)
    return destination


def copy_to_converted(
    path: Path, augmented_dir: Path = AUGMENTED_DIR, original_name: str | None = None
) -> Path:
    destination = augmented_dir / (original_name or path.name)
    shutil.copy2(path, destination)
    logging.info("Copied %s to %s", path.name, destination)
    return destination


def sanitize_filename(base_name: str, pattern: re.Pattern[str] = SANITIZE_PATTERN) -> str:
    sanitized = pattern.sub(" ", base_name).strip()
    return re.sub(r"\s+", " ", sanitized)


def rename_file(
    path: Path,
    artist: str | None,
    title: str | None,
    pattern: re.Pattern[str] = SANITIZE_PATTERN,
) -> Path:
    safe_artist = artist or "Unknown Artist"
    safe_title = title or path.stem
    new_name = sanitize_filename(f"{safe_artist} - {safe_title}", pattern) + path.suffix.lower()

    destination = path.with_name(new_name)
    counter = 1
    while destination.exists() and destination != path:
        destination = path.with_name(
            sanitize_filename(f"{safe_artist} - {safe_title} ({counter})", pattern)
            + path.suffix.lower()
        )
        counter += 1

    if destination != path:
        path.rename(destination)
        logging.info("Renamed %s -> %s", path.name, destination.name)
    return destination


def log_agent_response(
    file_name: str,
    raw_text: str,
    messages: list[Any],
    log_file_path: Path = LOG_FILE_PATH,
) -> None:
    entry = {
        "timestamp": datetime.now().isoformat(),
        "file": file_name,
        "raw_response": raw_text,
        "messages": messages,
    }
    log_file_path.parent.mkdir(parents=True, exist_ok=True)
    with log_file_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


__all__ = [
    "AUGMENTED_DIR",
    "DOWNLOAD_DIR",
    "LOG_DIR",
    "LOG_FILE_PATH",
    "PROCESSING_DIR",
    "RUN_START",
    "SANITIZE_PATTERN",
    "SUPPORTED_AUDIO_EXTENSIONS",
    "copy_to_converted",
    "discover_new_audio_files",
    "ensure_directories",
    "log_agent_response",
    "log_dependency_warning",
    "rename_file",
    "reset_processing_dir",
    "sanitize_filename",
    "setup_logging",
    "stage_file",
]
