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
from src.models.track import Track
from src.models.track_trait import TrackTrait
from src.config import NUM_CORES, PROCESSED_MUSIC_DIR
from src.utils.file_operations import AUDIO_TYPES
from src.errors import handle


_PROGRESS_INTERVAL = 10


def _compute_traits(chunk, result_transmitter):
    """Worker: load ONNX sessions once, compute and persist one trait row per track."""
    # Import here so ONNX sessions are not created in the parent process
    from src.feature_extraction.trait_extractor import TraitExtractor

    worker_session = database.create_session()
    pid = getpid()
    n_saved = 0
    n_skipped = 0
    n_failed = 0

    print("  [%d] Loading ONNX sessions..." % pid, flush=True)
    try:
        extractor = TraitExtractor()
    except Exception as exc:
        handle(exc)
        result_transmitter.send((0, 0, len(chunk)))
        return
    print("  [%d] Sessions ready, processing %d tracks." % (pid, len(chunk)), flush=True)

    for track in chunk:
        try:
            audio_path = join(PROCESSED_MUSIC_DIR, track.file_name)
            print("  [%d] track %d: %s" % (pid, track.id, track.file_name), flush=True)

            traits = extractor.compute(audio_path)

            row = TrackTrait(
                track_id=track.id,
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
                row.track_id for row in session.query(TrackTrait).all()
            }
            tracks_to_process = [
                t for t in tracks
                if t.id not in existing_ids
                and splitext(t.file_name)[1].lower() in AUDIO_TYPES
            ]

        num_tracks = len(tracks_to_process)
        print("Computing traits for %d track(s)\n" % num_tracks)
        if num_tracks == 0:
            return

        chunks = np.array_split(tracks_to_process, min(NUM_CORES, num_tracks))
        workers = []
        aggregators = []

        for chunk in chunks:
            receiver, transmitter = Pipe()
            aggregators.append(receiver)
            worker = Process(
                target=_compute_traits,
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
