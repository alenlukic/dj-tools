"""Backfill script: re-extract traits for rows with outdated trait_version.

Finds all track_trait rows whose trait_version is not the current version
(e.g. 'outdated' after the migration), recomputes traits via the full ONNX
pipeline, and updates existing rows in place.

Each worker loads ONNX sessions once (~430 MB) then processes its chunk,
committing per-row. A crash only loses the track currently being computed.
Safe to re-run — only processes rows where trait_version != current version.

Usage:
    python -m src.scripts.feature_extraction.backfill_genre_mood

Environment:
    TRAIT_WORKERS  Number of parallel worker processes (default: 2). Each
                   worker loads the full ONNX model set; keep this low on
                   memory-constrained machines.
"""

import datetime
import gc
import os
import traceback
import warnings

warnings.simplefilter("ignore")

from multiprocessing import Pipe, Process  # noqa: E402
from os.path import join, splitext  # noqa: E402

from src.db import database  # noqa: E402
from src.models.track import Track  # noqa: E402
from src.models.track_trait import TrackTrait  # noqa: E402
from src.config import PROCESSED_MUSIC_DIR  # noqa: E402
from src.feature_extraction.config import TRAIT_VERSION, TRAIT_WORKERS  # noqa: E402
from src.utils.file_operations import AUDIO_TYPES  # noqa: E402
from src.scripts.feature_extraction.compute_track_traits import (  # noqa: E402
    _chunkify,
    _resolve_audio_path,
)

_PROGRESS_INTERVAL = 10


def _backfill_chunk(chunk, result_transmitter):
    """Worker: load ONNX sessions once, recompute and update one trait row per track."""
    from src.feature_extraction.trait_extractor import TraitExtractor

    pid = os.getpid()
    n_ok = 0
    n_fail = 0

    print("  [%d] Loading ONNX sessions..." % pid, flush=True)
    try:
        extractor = TraitExtractor()
    except Exception:
        print("  [%d] Failed to load models:\n%s" % (pid, traceback.format_exc()), flush=True)
        result_transmitter.send((0, len(chunk)))
        result_transmitter.close()
        return
    print("  [%d] Sessions ready, backfilling %d tracks." % (pid, len(chunk)), flush=True)

    worker_session = database.create_session()
    try:
        for trait_id, track_id, file_name in chunk:
            try:
                audio_path = join(PROCESSED_MUSIC_DIR, file_name)
                try:
                    traits = extractor.compute(audio_path)
                except (FileNotFoundError, OSError):
                    fallback = _resolve_audio_path(PROCESSED_MUSIC_DIR, file_name)
                    if fallback is None:
                        print("  [%d] track %d: file not found: %s" % (pid, track_id, file_name), flush=True)
                        n_fail += 1
                        continue
                    traits = extractor.compute(fallback)

                row = worker_session.query(TrackTrait).filter_by(id=trait_id).first()
                if row is None:
                    n_fail += 1
                    continue

                row.voice_instrumental = traits["voice_instrumental"]
                row.danceability = traits["danceability"]
                row.bright_dark = traits["bright_dark"]
                row.acoustic_electronic = traits["acoustic_electronic"]
                row.tonal_atonal = traits["tonal_atonal"]
                row.reverb = traits["reverb"]
                row.onset_density = traits["onset_density"]
                row.spectral_flatness = traits["spectral_flatness"]
                row.mood_theme = traits["mood_theme"]
                row.genre = traits["genre"]
                row.instruments = traits["instruments"]
                row.trait_version = traits["trait_version"]
                row.computed_at = datetime.datetime.utcnow()
                worker_session.commit()
                n_ok += 1

                if n_ok % _PROGRESS_INTERVAL == 0:
                    print("  [%d] backfilled %d so far" % (pid, n_ok), flush=True)

                del traits
                if n_ok % _PROGRESS_INTERVAL == 0:
                    gc.collect()

            except Exception:
                worker_session.rollback()
                n_fail += 1
                print("  [%d] track %d: exception:\n%s" % (pid, track_id, traceback.format_exc()), flush=True)
    finally:
        worker_session.close()

    print("<<< Worker %d done: %d backfilled, %d failed >>>" % (pid, n_ok, n_fail), flush=True)
    result_transmitter.send((n_ok, n_fail))
    result_transmitter.close()


def run():
    session = database.create_session()
    try:
        outdated = (
            session.query(TrackTrait)
            .filter(TrackTrait.trait_version != TRAIT_VERSION)
            .all()
        )
        track_map = {
            t.id: t.file_name
            for t in session.query(Track).all()
        }

        work_items = []
        skipped = 0
        for row in outdated:
            file_name = track_map.get(row.track_id)
            if file_name is None:
                skipped += 1
                continue
            ext = splitext(file_name)[1].lower()
            if ext not in AUDIO_TYPES:
                skipped += 1
                continue
            work_items.append((row.id, row.track_id, file_name))

        total = len(work_items)
        print("Backfilling %d rows (%d skipped — missing track or non-audio)" % (total, skipped))
        if total == 0:
            return
    finally:
        session.close()

    n_workers = min(TRAIT_WORKERS, total)
    print("Using %d worker(s) (TRAIT_WORKERS=%d)\n" % (n_workers, TRAIT_WORKERS))

    chunks = _chunkify(work_items, n_workers)

    workers = []
    aggregators = []
    for chunk in chunks:
        receiver, transmitter = Pipe(duplex=False)
        aggregators.append(receiver)
        worker = Process(target=_backfill_chunk, args=(chunk, transmitter))
        worker.daemon = True
        workers.append(worker)
        worker.start()
        transmitter.close()

    worker_results = [agg.recv() for agg in aggregators]

    for worker in workers:
        worker.join()
    for agg in aggregators:
        agg.close()

    total_ok = sum(n for n, _ in worker_results)
    total_fail = sum(n for _, n in worker_results)

    print("\nDone. %d backfilled, %d failed." % (total_ok, total_fail))


if __name__ == "__main__":
    run()
