from src.ingestion_pipeline.config import TagRecordType
from src.ingestion_pipeline.track_ingestion_pipeline import InitialPipelineStage


if __name__ == "__main__":
    InitialPipelineStage(TagRecordType.INITIAL.value).execute()
