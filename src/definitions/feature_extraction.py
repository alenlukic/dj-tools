from enum import Enum


class SerializationKeys(Enum):
    TRACK_ID = "Track ID"
    TRACK_TITLE = "Track Title"
    SAMPLES = "Samples"


class RelativeKey(Enum):
    SAME = "Same"
    STEP_DOWN = "Step Down"
    STEP_UP = "Step Up"


class Feature(Enum):
    SMMS = "Segmented Mean Mel Spectrogram"


SAMPLE_RATE = 44100

NUM_MELS = 128

WINDOW_SIZE = int(SAMPLE_RATE / 2)

OVERLAP_WINDOW = int(WINDOW_SIZE / 5)

NUM_ROW_CHUNKS = 512

# Compact descriptor constants
DESCRIPTOR_VERSION = "1"

# Descriptor layout: 12+12 chroma + 1+16 rhythm + 13+13 MFCC + 2+2+2+2 energy = 75 dims
DESCRIPTOR_CHROMA_DIMS = 24
DESCRIPTOR_RHYTHM_DIMS = 17
DESCRIPTOR_MFCC_DIMS = 26
DESCRIPTOR_ENERGY_DIMS = 8
DESCRIPTOR_DIMS = (
    DESCRIPTOR_CHROMA_DIMS
    + DESCRIPTOR_RHYTHM_DIMS
    + DESCRIPTOR_MFCC_DIMS
    + DESCRIPTOR_ENERGY_DIMS
)

# Duration (seconds) of intro/outro zones extracted as separate vectors
DESCRIPTOR_ZONE_SECONDS = 60

# Normalized BPM range used when packing rhythm component
DESCRIPTOR_BPM_MIN = 60.0
DESCRIPTOR_BPM_RANGE = 140.0

# Number of tempogram summary bins in the rhythm vector
DESCRIPTOR_TEMPOGRAM_BINS = 16
