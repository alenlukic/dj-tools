from multiprocessing import Process
import numpy as np
import sys
import warnings

from src.db import database
from src.db.entities.feature_value import FeatureValue
from src.db.entities.track import Track
from src.definitions.common import NUM_CORES
from src.lib.feature_extraction.track_feature import SegmentedMeanMelSpectrogram
from src.lib.error_management.reporting_handler import handle
from src.utils.file_operations import stage_tracks


def compute_spectrograms(chunk, sesh):
    stage_tracks(chunk)

    for track in chunk:
        print('Processing track ID %s' % str(track.id))

        try:
            smms = SegmentedMeanMelSpectrogram(track, sesh)
            smms.compute()
            smms.save()
        except Exception as e:
            handle(e)
            continue


def run(track_ids):
    sesh = database.create_session()

    try:
        if len(track_ids) > 0:
            tracks_to_process = [track for track in tracks if track.id in track_ids]
        else:
            fv_track_ids = set([fv.track_id for fv in sesh.query(FeatureValue).all()])
            tracks_to_process = [track for track in tracks if track.id not in fv_track_ids]

        print('Number of tracks to process: %d' % len(tracks_to_process))

        chunks = np.array_split(tracks_to_process, NUM_CORES)
        workers = []
        for chunk in chunks:
            worker = Process(target=compute_spectrograms, args=(chunk, sesh,))
            workers.append(worker)
            worker.start()
        for w in workers:
            w.join()

    except Exception as e:
        handle(e)
        return

    finally:
        sesh.close()


if __name__ == '__main__':
    warnings.simplefilter('ignore')

    session = database.create_session()
    tracks = set([t for t in session.query(Track).all()])
    session.close()

    args = sys.argv
    run(set([int(t) for t in args[1:]]) if len(args) > 1 else set())
