from enum import Enum

from src.definitions.common import CONFIG


class SerializationKeys(Enum):
    TRACK_ID = 'Track ID'
    TRACK_TITLE = 'Track Title'
    SAMPLES = 'Samples'


FEATURE_DIR = CONFIG['FEATURE_DIR']

SAMPLE_RATE = 44100

N_MELS = 128

WINDOW_SIZE = int(SAMPLE_RATE / 2)

OVERLAP_WINDOW = int(WINDOW_SIZE / 5)

NUM_ROW_CHUNKS = 512
