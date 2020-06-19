from enum import Enum


class TagRecordType(Enum):
    INITIAL = 'InitialTagRecord'
    POST_MIK = 'PostMIKTagRecord'
    POST_RB = 'PostRekordboxTagRecord'
    FINAL = 'FinalTagRecord'
