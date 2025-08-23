from src.definitions.ingestion_pipeline import TagRecordType
from src.lib.ingestion_pipeline.track_ingestion_pipeline import FinalPipelineStage


if __name__ == "__main__":
    FinalPipelineStage(TagRecordType.FINAL.value).execute()
