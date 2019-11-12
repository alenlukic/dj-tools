from enum import Enum


# How harmonic a particular key transition is (higher = more harmonic)
class CamelotPriority(Enum):
    TWO_OCTAVE_JUMP = 0
    ONE_OCTAVE_JUMP = 1
    ADJACENT_JUMP = 2
    ONE_KEY_JUMP = 3
    MAJOR_MINOR_JUMP = 4
    SAME_KEY = 4


SAME_UPPER_BOUND = 0.0275
SAME_LOWER_BOUND = -0.025
UP_KEY_LOWER_BOUND = 0.03
UP_KEY_UPPER_BOUND = 0.09
DOWN_KEY_LOWER_BOUND = -0.08
DOWN_KEY_UPPER_BOUND = -0.03
