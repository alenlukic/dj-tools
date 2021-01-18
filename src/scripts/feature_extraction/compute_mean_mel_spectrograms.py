from multiprocessing import Process
import numpy as np
from os.path import join

from src.db import database
from src.db.entities.feature_value import FeatureValue
from src.db.entities.track import Track
from src.definitions.common import NUM_CORES
from src.definitions.feature_extraction import FEATURE_DIR
from src.lib.feature_extraction.track_feature import SegmentedMeanMelSpectrogram
from src.utils.errors import handle_error
from src.utils.feature_extraction import load_json_from_file


def compute_spectrograms(tracks, session):
    for track in tracks:
        print('Processing %s' % str(track.id))
        try:
            smms = SegmentedMeanMelSpectrogram(track)
            smms.compute()
            smms.save()

            fv_row = {
                'track_id': track.id,
                'features': {
                    smms.feature_name: smms.preprocess(smms.feature_value)
                }
            }
            session.guarded_add(FeatureValue(**fv_row))
        except Exception as e:
            handle_error(e)
            continue


def run():
    session = database.create_session()
    try:
        tracks_to_process = list(filter(lambda t: load_json_from_file(
            join(FEATURE_DIR, str(t.id))) == {}, session.query(Track).all()))
        print('Tracks to process: %d' % len(tracks_to_process))
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
    run()
