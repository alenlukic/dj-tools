import os

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
TRAIT_VERSION = "4"
TRAIT_SAMPLE_RATE = 16000
TRAIT_MODELS_DIR = "models/traits"

# Storage threshold: the minimum probability to persist in the DB.
# Keeps near-zero noise out of JSONB without discarding usable signal.
# All display-layer filtering is applied downstream from these raw stored values.
TRAIT_STORAGE_THRESHOLD = 0.01

# --- Display-layer filtering (applied at read/consumption time, not storage) ---

MOOD_DISPLAY_THRESHOLD = 0.15
GENRE_DISPLAY_THRESHOLD = 0.10
INSTRUMENT_DISPLAY_THRESHOLD = 0.10
MOOD_TOP_K = 5
GENRE_TOP_K = 8

# Genre family allowlist for electronic-music collections.
# Only genres whose family prefix appears here are surfaced; all others
# are suppressed as acoustically-similar but genre-incorrect noise.
# Revise this set if the library evolves beyond all-electronic.
GENRE_ALLOWED_FAMILIES = frozenset({
    "Electronic",
    "Hip Hop",
    "Funk / Soul",
    "Pop",
    "Reggae",
    "Stage & Screen",
})

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

# Number of parallel worker processes for compute_track_traits.py.
# Each worker loads the full ONNX model set (~430 MB); keep this low on
# memory-constrained machines. Override with the TRAIT_WORKERS env var.
TRAIT_WORKERS = int(os.getenv("TRAIT_WORKERS", "2"))

# Number of parallel worker processes for compute_cosine_similarities.py.
# Each worker loads TransitionMatchFinder (all tracks + camelot map) but no
# heavy ONNX models, so memory is moderate (~50–100 MB per worker).
# Override with the COSINE_WORKERS env var.
COSINE_WORKERS = int(os.getenv("COSINE_WORKERS", "2"))
