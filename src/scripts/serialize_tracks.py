from multiprocessing import Process
import numpy as np

from src.db import database
from src.db.entities.track import Track
from src.definitions.common import NUM_CORES
from src.lib.feature_extraction.sample_serializer import serialize
from src.utils.errors import handle_error


def run_serializer():
    session = database.create_session()

    try:
        tracks = session.query(Track).all()
        chunks = np.array_split(tracks, NUM_CORES)
        workers = []

        for chunk in chunks:
            worker = Process(target=serialize, args=(chunk,))
            workers.append(worker)
            worker.start()

        for w in workers:
            w.join()

    except Exception as e:
        handle_error(e)

    finally:
        session.close()


if __name__ == '__main__':
    run_serializer()
