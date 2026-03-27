from __future__ import annotations

import json
import logging
from pathlib import Path

from src.track_metadata.audio_features import analyze_missing_audio_features
from src.track_metadata.models import SimpleMetadata
from src.track_metadata.sources.hydrator import MetadataHydrator, build_metadata_agent
from src.track_metadata.tags import read_existing_metadata, write_tags
from src.track_metadata.utils import (
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

# ---------------------------------------------------------------------------
# Entry-point functions
# ---------------------------------------------------------------------------


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


def enrich_metadata(
    agent: MetadataHydrator, file_path: Path, existing: SimpleMetadata
) -> SimpleMetadata:
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
        final_json = json.dumps(final_metadata, indent=2, ensure_ascii=False)
        logging.info("Final metadata:\n%s", final_json)

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
