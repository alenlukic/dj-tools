from src.ingestion_pipeline.config import TagRecordType
from src.ingestion_pipeline.track_ingestion_pipeline import PipelineStage


if __name__ == "__main__":
    PipelineStage(TagRecordType.POST_MIK.value).execute()
