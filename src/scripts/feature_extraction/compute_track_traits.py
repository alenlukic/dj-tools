"""Batch script: compute semantic traits for all unprocessed tracks.

Each worker loads ONNX sessions once (expensive) then processes its chunk of
tracks, saving results to DB as it goes. Progress is visible in real time; a
crash only loses the track currently being computed. Safe to re-run — tracks
with an existing TrackTrait row are skipped.

Usage:
    # Process all tracks that have no trait row yet
    python -m src.scripts.feature_extraction.compute_track_traits

    # Process specific track IDs
    python -m src.scripts.feature_extraction.compute_track_traits 42 101 200

Environment:
    TRAIT_WORKERS  Number of parallel worker processes (default: 2). Each worker
                   loads the full ONNX model set (~430 MB); keep this low on
                   memory-constrained machines.
"""

import datetime
import gc
import os
import sys
import warnings

warnings.simplefilter("ignore")

from multiprocessing import Pipe, Process  # noqa: E402
from os.path import join, splitext  # noqa: E402

from src.db import database  # noqa: E402
from src.models.track import Track  # noqa: E402
from src.models.track_trait import TrackTrait  # noqa: E402
from src.config import PROCESSED_MUSIC_DIR  # noqa: E402
from src.feature_extraction.config import TRAIT_WORKERS  # noqa: E402
from src.utils.file_operations import AUDIO_TYPES  # noqa: E402
from src.errors import handle  # noqa: E402


_PROGRESS_INTERVAL = 10


def _chunkify(lst, n):
    """Split lst into n roughly equal non-empty chunks."""
    if not lst:
        return []
    n = min(n, len(lst))
    size, rem = divmod(len(lst), n)
    chunks, i = [], 0
    for k in range(n):
        extra = 1 if k < rem else 0
        chunks.append(lst[i : i + size + extra])
        i += size + extra
    return [c for c in chunks if c]


def _resolve_audio_path(music_dir, file_name):
    """Return the absolute audio path for a track.

    Falls back to a prefix substring match when the filename contains
    non-ASCII characters or ``?`` placeholders that may not survive
    filesystem round-trips.  The trigger fires at the first ``?`` or
    first non-ASCII character, whichever appears first.
    Returns the resolved path string, or None if no match is found.
    Only called after an OSError on the direct path — avoids os.path.exists()
    so that normal filesystem access patterns are preserved.
    """
    trigger_pos = next(
        (i for i, c in enumerate(file_name) if ord(c) > 127 or c == "?"),
        None,
    )
    if trigger_pos is None:
        return None

    prefix = file_name[:trigger_pos]
    search_dir = os.path.dirname(join(music_dir, prefix))
    basename_prefix = os.path.basename(prefix)

    if not os.path.isdir(search_dir):
        return None

    if not basename_prefix:
        return None

    for candidate in sorted(os.listdir(search_dir)):
        if candidate.startswith(basename_prefix):
            candidate_path = join(search_dir, candidate)
            if os.path.isfile(candidate_path):
                return candidate_path

    return None


def _compute_traits(chunk, result_transmitter):
    """Worker: load ONNX sessions once, compute and persist one trait row per track.

    chunk is a list of (track_id, file_name) tuples — full ORM objects are not
    passed across the process boundary to keep pickling overhead and memory low.
    """
    from src.feature_extraction.trait_extractor import TraitExtractor

    pid = os.getpid()
    n_saved = 0
    n_skipped = 0
    n_failed = 0

    print("  [%d] Loading ONNX sessions..." % pid, flush=True)
    try:
        extractor = TraitExtractor()
    except Exception as exc:
        handle(exc)
        result_transmitter.send((0, 0, len(chunk)))
        result_transmitter.close()
        return
    print(
        "  [%d] Sessions ready, processing %d tracks." % (pid, len(chunk)), flush=True
    )

    worker_session = database.create_session()
    try:
        for track_id, file_name in chunk:
            try:
                audio_path = join(PROCESSED_MUSIC_DIR, file_name)
                print("  [%d] track %d: %s" % (pid, track_id, file_name), flush=True)

                try:
                    traits = extractor.compute(audio_path)
                except (FileNotFoundError, OSError):
                    fallback = _resolve_audio_path(PROCESSED_MUSIC_DIR, file_name)
                    if fallback is None:
                        print(
                            "  [%d] track %d: file not found: %s"
                            % (pid, track_id, file_name),
                            flush=True,
                        )
                        n_failed += 1
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
                if worker_session.guarded_add(row):
                    n_saved += 1
                    if n_saved % _PROGRESS_INTERVAL == 0:
                        print(
                            "  [%d] saved %d traits so far" % (pid, n_saved),
                            flush=True,
                        )
                else:
                    n_failed += 1

                del traits, row
                if n_saved % _PROGRESS_INTERVAL == 0:
                    gc.collect()

            except Exception as exc:
                handle(exc)
                n_failed += 1
    finally:
        worker_session.close()

    print(
        "<<< Worker %d done: %d saved, %d skipped, %d failed >>>"
        % (pid, n_saved, n_skipped, n_failed),
        flush=True,
    )
    result_transmitter.send((n_saved, n_skipped, n_failed))
    result_transmitter.close()


def run(track_ids, session):
    try:
        all_tracks = session.query(Track).all()
        if len(track_ids) > 0:
            tracks_to_process = [
                (t.id, t.file_name) for t in all_tracks if t.id in track_ids
            ]
        else:
            existing_ids = {
                row.track_id for row in session.query(TrackTrait.track_id).all()
            }
            tracks_to_process = [
                (t.id, t.file_name)
                for t in all_tracks
                if t.id not in existing_ids
                and splitext(t.file_name)[1].lower() in AUDIO_TYPES
            ]
        del all_tracks

        num_tracks = len(tracks_to_process)
        print("Computing traits for %d track(s)" % num_tracks)
        if num_tracks == 0:
            return

        n_workers = min(TRAIT_WORKERS, num_tracks)
        print("Using %d worker(s) (TRAIT_WORKERS=%d)\n" % (n_workers, TRAIT_WORKERS))

        chunks = _chunkify(tracks_to_process, n_workers)
        del tracks_to_process

        workers = []
        aggregators = []

        for chunk in chunks:
            receiver, transmitter = Pipe(duplex=False)
            aggregators.append(receiver)
            worker = Process(
                target=_compute_traits,
                args=(chunk, transmitter),
            )
            worker.daemon = True
            workers.append(worker)
            worker.start()
            transmitter.close()  # parent holds only the read end

        worker_results = [agg.recv() for agg in aggregators]

        for worker in workers:
            worker.join()

        for agg in aggregators:
            agg.close()

        total_saved = sum(n for n, _, _ in worker_results)
        total_skipped = sum(n for _, n, _ in worker_results)
        total_failed = sum(n for _, _, n in worker_results)

        print(
            "\nDone. %d saved, %d skipped, %d failed."
            % (total_saved, total_skipped, total_failed)
        )

    except Exception as exc:
        handle(exc)
        session.rollback()
    finally:
        session.close()


if __name__ == "__main__":
    _session = database.create_session()
    _args = sys.argv
    run(set(int(t) for t in _args[1:]) if len(_args) > 1 else set(), _session)
