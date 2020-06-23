from src.definitions.db import TagRecordType
from src.tools.db.track_ingestion_pipeline import InitialPipelineStage


if __name__ == '__main__':
    InitialPipelineStage(TagRecordType.INITIAL.value).execute()
