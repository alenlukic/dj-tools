from enum import Enum

from src.definitions.common import CONFIG

SAMPLE_RATE = 44100


class SerializationKeys(Enum):
    TRACK_ID = 'Track ID'
    TRACK_TITLE = 'Track Title'
    SAMPLES = 'Samples'


SERIALIZED_SAMPLE_DIR = CONFIG['SERIALIZED_SAMPLE_DIR']

