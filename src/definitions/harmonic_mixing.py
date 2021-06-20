from enum import Enum

from src.definitions.common import CONFIG


class CollectionStat(Enum):
    OLDEST = 'Oldest Timestamp'
    NEWEST = 'Newest Timestamp'
    TIME_RANGE = 'Time Range'
    LABEL_COUNTS = 'Label Counts'
    ARTIST_COUNTS = 'Artist Counts'
    SMMS_MAX = 'SMMS Max'


class MatchFactors(Enum):
    ARTIST = 'Artist'
    BPM = 'BPM'
    CAMELOT = 'Camelot'
    ENERGY = 'Energy'
    FRESHNESS = 'Freshness'
    GENRE = 'Genre'
    LABEL = 'Label'
    SMMS_SCORE = 'SMMS Score'


# How harmonic a particular key transition is (higher = more harmonic)
class CamelotPriority(Enum):
    TWO_OCTAVE_JUMP = 0
    ONE_OCTAVE_JUMP = 1
    ADJACENT_JUMP = 2
    ONE_KEY_JUMP = 3
    MAJOR_MINOR_JUMP = 4
    SAME_KEY = 4


MATCH_WEIGHTS = {f.name: CONFIG['TRANSITION_MATCH_WEIGHTS'][f.name] for f in MatchFactors}

SAME_UPPER_BOUND = 0.0293
SAME_LOWER_BOUND = -0.0284
UP_KEY_LOWER_BOUND = 0.0293
UP_KEY_UPPER_BOUND = 0.0905
DOWN_KEY_LOWER_BOUND = -0.083
DOWN_KEY_UPPER_BOUND = -0.0284

TIMESTAMP_FORMAT = '%a %b %d %H:%M:%S %Y'
