from src.definitions.db import TagRecordType
from src.tools.db.track_ingestion_pipeline import PostRBPipelineStage


if __name__ == '__main__':
    PostRBPipelineStage(TagRecordType.POST_RB.value).execute()
