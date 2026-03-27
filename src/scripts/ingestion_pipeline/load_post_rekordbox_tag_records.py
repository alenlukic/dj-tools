from src.ingestion_pipeline.config import TagRecordType
from src.ingestion_pipeline.track_ingestion_pipeline import PostRBPipelineStage


if __name__ == "__main__":
    PostRBPipelineStage(TagRecordType.POST_RB.value).execute()
