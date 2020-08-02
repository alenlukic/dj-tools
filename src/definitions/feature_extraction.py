from enum import Enum

from src.definitions.common import CONFIG


class SerializationKeys(Enum):
    TRACK_ID = 'Track ID'
    TRACK_TITLE = 'Track Title'
    SAMPLES = 'Samples'


class RelativeKey(Enum):
    SAME = 'Same'
    STEP_DOWN = 'Step Down'
    STEP_UP = 'Step Up'


class Feature(Enum):
    SMMS = 'Segmented Mean Mel Spectrogram'


class MatchScore(Enum):
    SMMS_SCORE = 'SMMS Score'


FEATURE_DIR = CONFIG['FEATURE_DIR']

SAMPLE_RATE = 44100

N_MELS = 128

WINDOW_SIZE = int(SAMPLE_RATE / 2)

OVERLAP_WINDOW = int(WINDOW_SIZE / 5)

NUM_ROW_CHUNKS = 512
