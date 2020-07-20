from src.db import database
from src.db.entities.track import Track
from src.lib.feature_extraction.track_feature import SegmentedMeanMelSpectrogram
from src.utils.errors import handle_error


def compute_spectrograms():
    session = database.create_session()
    tracks = session.query(Track).all()
    try:
        for track in tracks:
            try:
                smms = SegmentedMeanMelSpectrogram(track)
                smms.compute()
                smms.save()
            except Exception as e:
                handle_error(e)
                continue
    finally:
        session.close()


if __name__ == '__main__':
    compute_spectrograms()
