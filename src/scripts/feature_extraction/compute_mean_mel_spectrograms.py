from multiprocessing import Pipe, Process
import numpy as np
from os import getpid
import sys
import warnings

from src.db import database
from src.db.entities.feature_value import FeatureValue
from src.db.entities.track import Track
from src.definitions.common import NUM_CORES
from src.lib.feature_extraction.track_feature import SegmentedMeanMelSpectrogram
from src.lib.error_management.reporting_handler import handle
from src.utils.file_operations import stage_tracks


def compute_spectrograms(chunk, transmitter):
    stage_tracks(chunk)

    smms_values = []
    for track in chunk:
        try:
            print('Computing spectrograms for track %s' % str(track.id))

            smms = SegmentedMeanMelSpectrogram(track)
            smms.compute()
            smms_values.append(smms)

        except Exception as e:
            handle(e)
            continue

    print('Process %d thread done' % getpid())

    transmitter.send(smms_values)

def run(track_ids):
    try:
        if len(track_ids) > 0:
            tracks_to_process = [track for track in tracks if track.id in track_ids]
        else:
            fv_track_ids = set([fv.track_id for fv in session.query(FeatureValue).all()])
            tracks_to_process = [track for track in tracks if track.id not in fv_track_ids]

        print('Computing SMMS feature for %d tracks\n' % len(tracks_to_process))

        chunks = np.array_split(tracks_to_process, NUM_CORES)
        workers = []
        smms_aggregator = []

        for chunk in chunks:
            receiver, transmitter = Pipe()
            smms_aggregator.append(receiver)

            worker = Process(target=compute_spectrograms, args=(chunk, transmitter,))
            worker.daemon = True
            workers.append(worker)
            worker.start()

        smms_results = [smms for result in [result.recv() for result in smms_aggregator] for smms in result]
        for smms in smms_results:
            track_id = smms.track.id
            print('Saving feature for track %s to DB' % str(track_id))

            try:
                feature_value = smms.get_feature()
                if feature_value is None:
                    continue

                fv_row = {
                    'track_id': track_id,
                    'features': {
                        smms.feature_name: smms.preprocess(feature_value)
                    }
                }
                session.guarded_add(FeatureValue(**fv_row))

            except Exception as e:
                handle(e)
                continue

    except Exception as e:
        handle(e)
        session.rollback()
        return

    finally:
        session.close()


if __name__ == '__main__':
    warnings.simplefilter('ignore')

    session = database.create_session()
    tracks = set([t for t in session.query(Track).all()])

    args = sys.argv
    run(set([int(t) for t in args[1:]]) if len(args) > 1 else set())
