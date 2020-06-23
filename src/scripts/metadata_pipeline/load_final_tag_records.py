from src.definitions.db import TagRecordType
from src.tools.db.track_ingestion_pipeline import FinalPipelineStage


if __name__ == '__main__':
    FinalPipelineStage(TagRecordType.FINAL.value).execute()
