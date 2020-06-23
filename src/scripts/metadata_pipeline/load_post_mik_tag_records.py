from src.definitions.db import TagRecordType
from src.tools.db.track_ingestion_pipeline import PipelineStage


if __name__ == '__main__':
    PipelineStage(TagRecordType.POST_MIK.value).execute()
