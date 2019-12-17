from enum import Enum


# How harmonic a particular key transition is (higher = more harmonic)
class CamelotPriority(Enum):
    TWO_OCTAVE_JUMP = 0
    ONE_OCTAVE_JUMP = 1
    ADJACENT_JUMP = 2
    ONE_KEY_JUMP = 3
    MAJOR_MINOR_JUMP = 4
    SAME_KEY = 4


SAME_UPPER_BOUND = 0.0293
SAME_LOWER_BOUND = -0.0284
UP_KEY_LOWER_BOUND = 0.0293
UP_KEY_UPPER_BOUND = 0.0905
DOWN_KEY_LOWER_BOUND = -0.083
DOWN_KEY_UPPER_BOUND = -0.0284

TIMESTAMP_FORMAT = '%a %b %d %H:%M:%S %Y'
