from src.ingestion_pipeline.config import TagRecordType
from src.ingestion_pipeline.track_ingestion_pipeline import FinalPipelineStage


if __name__ == "__main__":
    FinalPipelineStage(TagRecordType.FINAL.value).execute()
