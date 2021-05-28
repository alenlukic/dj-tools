from multiprocessing import Process
import numpy as np
import warnings

from src.db import database
from src.db.entities.feature_value import FeatureValue
from src.db.entities.track import Track
from src.definitions.common import NUM_CORES
from src.lib.feature_extraction.track_feature import SegmentedMeanMelSpectrogram
from src.utils.errors import handle_error


def compute_spectrograms(tracks, session):
    for track in tracks:
        print('Processing track ID %s' % str(track.id))

        try:
            smms = SegmentedMeanMelSpectrogram(track, session)
            smms.compute()
            smms.save()
        except Exception as e:
            handle_error(e)
            continue


def run():
    session = database.create_session()

    try:
        fv_track_ids = set([fv.track_id for fv in session.query(FeatureValue).all()])
        tracks = [t for t in session.query(Track).all()]
        tracks_to_process = [t for t in tracks if t.id not in fv_track_ids]

        print('Number of tracks to process: %d' % len(tracks_to_process))

        chunks = np.array_split(tracks_to_process, NUM_CORES)
        workers = []
        for chunk in chunks:
            worker = Process(target=compute_spectrograms, args=(chunk, session,))
            workers.append(worker)
            worker.start()
        for w in workers:
            w.join()

    except Exception as e:
        handle_error(e)
        return

    finally:
        session.close()


if __name__ == '__main__':
    warnings.simplefilter('ignore')
    run()
