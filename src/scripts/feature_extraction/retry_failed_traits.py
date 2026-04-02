"""One-off diagnostic script: retry the tracks that failed during the full trait backfill.

Queries tracks present in ``track`` but missing from ``track_trait`` (filtered
to audio extensions), then recomputes traits single-threaded with full
traceback logging to the RCA run directory.  Safe to re-run — already-computed
tracks are skipped by the NOT-IN query.

Usage:
    python -m src.scripts.feature_extraction.retry_failed_traits
"""

import datetime
import traceback
import warnings
from os.path import join, splitext
from pathlib import Path

warnings.simplefilter("ignore")

from src.db import database  # noqa: E402
from src.models.track import Track  # noqa: E402
from src.models.track_trait import TrackTrait  # noqa: E402
from src.config import PROCESSED_MUSIC_DIR  # noqa: E402
from src.utils.file_operations import AUDIO_TYPES  # noqa: E402
from src.feature_extraction.trait_extractor import TraitExtractor  # noqa: E402
from src.scripts.feature_extraction.compute_track_traits import _resolve_audio_path  # noqa: E402

LOG_FILE = (
    Path(__file__).resolve().parents[3]
    / ".local/cursor-meta/runs/2026-03-31_trait_failure_rca/failure_log.txt"
)

_PROGRESS_INTERVAL = 10


def run():
    session = database.create_session()
    try:
        existing_ids = {
            row.track_id for row in session.query(TrackTrait.track_id).all()
        }
        missing = [
            (t.id, t.file_name)
            for t in session.query(Track).all()
            if t.id not in existing_ids
            and splitext(t.file_name)[1].lower() in AUDIO_TYPES
        ]

        total = len(missing)
        print("Retrying %d tracks missing from track_trait" % total)
        if total == 0:
            return

        extractor = TraitExtractor()

        succeeded = 0
        failed = 0

        for idx, (track_id, file_name) in enumerate(missing, 1):
            try:
                audio_path = join(PROCESSED_MUSIC_DIR, file_name)
                try:
                    traits = extractor.compute(audio_path)
                except (FileNotFoundError, OSError):
                    fallback = _resolve_audio_path(PROCESSED_MUSIC_DIR, file_name)
                    if fallback is None:
                        print("  track %d: file not found: %s" % (track_id, file_name))
                        failed += 1
                        continue
                    traits = extractor.compute(fallback)

                row = TrackTrait(
                    track_id=track_id,
                    voice_instrumental=traits["voice_instrumental"],
                    danceability=traits["danceability"],
                    bright_dark=traits["bright_dark"],
                    acoustic_electronic=traits["acoustic_electronic"],
                    tonal_atonal=traits["tonal_atonal"],
                    reverb=traits["reverb"],
                    onset_density=traits["onset_density"],
                    spectral_flatness=traits["spectral_flatness"],
                    mood_theme=traits["mood_theme"],
                    genre=traits["genre"],
                    instruments=traits["instruments"],
                    trait_version=traits["trait_version"],
                    computed_at=datetime.datetime.utcnow(),
                )
                if session.guarded_add(row):
                    succeeded += 1
                else:
                    failed += 1

            except Exception:
                failed += 1
                now = datetime.datetime.utcnow().isoformat()
                with open(LOG_FILE, "a") as f:
                    f.write(
                        "====== TRACK %d | %s | %s ======\n%s\n"
                        % (track_id, now, file_name, traceback.format_exc())
                    )
                print("  track %d: exception logged to %s" % (track_id, LOG_FILE))

            if idx % _PROGRESS_INTERVAL == 0:
                print("  progress: %d / %d" % (idx, total))

        print("Done. %d succeeded, %d failed." % (succeeded, failed))

    finally:
        session.close()


if __name__ == "__main__":
    run()
