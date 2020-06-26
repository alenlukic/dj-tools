from src.definitions.ingestion_pipeline import TagRecordType
from src.tools.ingestion_pipeline.track_ingestion_pipeline import InitialPipelineStage


if __name__ == '__main__':
    InitialPipelineStage(TagRecordType.INITIAL.value).execute()
