from enum import Enum

from src.definitions.common import CONFIG
from src.definitions.data_management import ID3Tag


class TagRecordType(Enum):
    INITIAL = 'InitialTagRecord'
    POST_MIK = 'PostMIKTagRecord'
    POST_RB = 'PostRekordboxTagRecord'
    FINAL = 'FinalTagRecord'


TAG_RECORD_FACTORIES = {
    TagRecordType.INITIAL.value: 'TagRecordFactory',
    TagRecordType.POST_MIK.value: 'PostMIKRecordFactory',
    TagRecordType.POST_RB.value: 'PostRBRecordFactory',
    TagRecordType.FINAL.value: 'FinalRecordFactory'
}

TAG_COLUMNS = [
    ID3Tag.BPM,
    ID3Tag.KEY,
    ID3Tag.ENERGY
]

PIPELINE_ROOT = CONFIG['INGESTION_PIPELINE']['ROOT']
RB_TAG_FILE = PIPELINE_ROOT['REKORDBOX_TAG_FILE']
UNPROCESSED_DIR = PIPELINE_ROOT['UNPROCESSED']
PROCESSING_DIR = PIPELINE_ROOT['PROCESSING']
FINALIZED_DIR = PIPELINE_ROOT['FINALIZED']
