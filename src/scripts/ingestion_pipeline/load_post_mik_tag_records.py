from src.definitions.ingestion_pipeline import TagRecordType
from src.lib.ingestion_pipeline.track_ingestion_pipeline import PipelineStage


if __name__ == '__main__':
    PipelineStage(TagRecordType.POST_MIK.value).execute()
