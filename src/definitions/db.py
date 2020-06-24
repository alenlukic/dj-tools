from enum import Enum
from os.path import join

from src.definitions.common import CONFIG
from src.definitions.data_management import ID3Tag, TrackDBCols


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
    ID3Tag.TITLE,
    ID3Tag.BPM,
    ID3Tag.KEY,
    ID3Tag.ENERGY
]

PIPELINE = CONFIG['INGESTION_PIPELINE']
PIPELINE_ROOT = PIPELINE['ROOT']
RB_TAG_FILE = join(PIPELINE_ROOT, PIPELINE['REKORDBOX_TAG_FILE'])
UNPROCESSED_DIR = join(PIPELINE_ROOT, PIPELINE['UNPROCESSED'])
PROCESSING_DIR = join(PIPELINE_ROOT, PIPELINE['PROCESSING'])
FINALIZED_DIR = join(PIPELINE_ROOT, PIPELINE['FINALIZED'])
