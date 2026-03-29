"""Deprecated SMMS (Segmented Mean Mel Spectrogram) constants.

These constants are retained only for the legacy SMMS fallback path in
create_transition_match_rows.py. New code should use src.feature_extraction.config.
"""
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


NUM_MELS = 128
WINDOW_SIZE = int(44100 / 2)
OVERLAP_WINDOW = int(WINDOW_SIZE / 5)
NUM_ROW_CHUNKS = 512
