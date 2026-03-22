"""Batch script: compute compact audio descriptors for all unprocessed tracks.

Each worker saves descriptors directly to the DB as it goes, so progress is
visible in real time and a crash only loses the track currently being computed.
The script is safe to re-run — already-processed tracks are skipped.

Usage:
    # Process all tracks that have no descriptor yet
    python -m src.scripts.feature_extraction.compute_compact_descriptors

    # Process specific track IDs
    python -m src.scripts.feature_extraction.compute_compact_descriptors 42 101 200
"""

import datetime
import sys
import warnings

warnings.simplefilter("ignore")

from multiprocessing import Pipe, Process
from os import getpid
from os.path import join, splitext

import numpy as np

from src.db import database
from src.db.entities.track import Track
from src.db.entities.track_descriptor import TrackDescriptor
from src.definitions.common import NUM_CORES, PROCESSED_MUSIC_DIR
from src.definitions.file_operations import AUDIO_TYPES
from src.lib.error_management.service import handle
from src.lib.feature_extraction.compact_descriptor import CompactDescriptor


_PROGRESS_INTERVAL = 100


def _compute_descriptors(chunk, result_transmitter):
    """Worker: compute and immediately persist one descriptor per track."""
    worker_session = database.create_session()
    n_saved = 0
    n_skipped = 0
    n_failed = 0
    pid = getpid()
    recent_saved_ids = []

    for track in chunk:
        try:
            audio_path = join(PROCESSED_MUSIC_DIR, track.file_name)
            print("  [%d] track %d: %s" % (pid, track.id, track.file_name), flush=True)

            desc = CompactDescriptor(track)
            desc.compute(audio_path=audio_path)

            if desc.global_vector is None:
                n_skipped += 1
                continue

            row = TrackDescriptor(
                track_id=track.id,
                global_vector=desc.pack_global(),
                intro_vector=desc.pack_intro(),
                outro_vector=desc.pack_outro(),
                descriptor_version=desc.version,
                computed_at=datetime.datetime.utcnow(),
            )
            if worker_session.guarded_add(row):
                n_saved += 1
                recent_saved_ids.append(track.id)
                if n_saved % _PROGRESS_INTERVAL == 0:
                    print(
                        "  [%d] saved %d so far — last %d IDs: %s"
                        % (pid, n_saved, len(recent_saved_ids[-_PROGRESS_INTERVAL:]),
                           recent_saved_ids[-_PROGRESS_INTERVAL:]),
                        flush=True,
                    )
            else:
                n_failed += 1

        except Exception as exc:
            handle(exc)
            n_failed += 1

    worker_session.close()
    print(
        "<<< Worker %d done: %d saved, %d skipped, %d failed >>>"
        % (pid, n_saved, n_skipped, n_failed),
        flush=True,
    )
    result_transmitter.send((n_saved, n_skipped, n_failed))


def run(track_ids):
    try:
        if len(track_ids) > 0:
            tracks_to_process = [t for t in tracks if t.id in track_ids]
        else:
            existing_ids = {
                row.track_id for row in session.query(TrackDescriptor).all()
            }
            tracks_to_process = [
                t for t in tracks
                if t.id not in existing_ids
                and splitext(t.file_name)[1].lower() in AUDIO_TYPES
            ]

        num_tracks = len(tracks_to_process)
        print("Computing compact descriptors for %d track(s)\n" % num_tracks)
        if num_tracks == 0:
            return

        chunks = np.array_split(tracks_to_process, min(NUM_CORES, num_tracks))
        workers = []
        aggregators = []

        for chunk in chunks:
            receiver, transmitter = Pipe()
            aggregators.append(receiver)
            worker = Process(
                target=_compute_descriptors,
                args=(chunk, transmitter),
            )
            worker.daemon = True
            workers.append(worker)
            worker.start()

        worker_results = [agg.recv() for agg in aggregators]
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
        return
    finally:
        session.close()


if __name__ == "__main__":
    session = database.create_session()
    tracks = list(session.query(Track).all())

    args = sys.argv
    run(set(int(t) for t in args[1:]) if len(args) > 1 else set())
