from src.definitions.ingestion_pipeline import TagRecordType
from src.tools.ingestion_pipeline.track_ingestion_pipeline import PostRBPipelineStage


if __name__ == '__main__':
    PostRBPipelineStage(TagRecordType.POST_RB.value).execute()
