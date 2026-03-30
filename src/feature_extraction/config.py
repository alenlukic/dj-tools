from enum import Enum


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

SAMPLE_RATE = 44100

# Trait extraction constants
TRAIT_VERSION = "2"
TRAIT_SAMPLE_RATE = 16000
TRAIT_MODELS_DIR = "models/traits"
TRAIT_PREDICTION_THRESHOLD = 0.1

# EffNet-backed classification heads (18 MB embedding backbone)
TRAIT_CLASSIFIERS_EFFNET = [
    "mtg_jamendo_moodtheme-discogs-effnet-1",
    "voice_instrumental-discogs-effnet-1",
    "danceability-discogs-effnet-1",
    "timbre-discogs-effnet-1",
    "nsynth_acoustic_electronic-discogs-effnet-1",
    "tonal_atonal-discogs-effnet-1",
    "nsynth_reverb-discogs-effnet-1",
    "mtg_jamendo_instrument-discogs-effnet-1",
]

# MAEST standalone backbone for 519-class Discogs genre classification
TRAIT_CLASSIFIER_MAEST = "discogs-maest-30s-pw-519l"
