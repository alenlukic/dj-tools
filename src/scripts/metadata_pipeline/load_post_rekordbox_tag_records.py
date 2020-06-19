from src.definitions.db import TagRecordType
from src.tools.db.track_metadata_pipeline import TrackMetadataPipeline


if __name__ == '__main__':
    TrackMetadataPipeline(TagRecordType.POST_RB).create_tag_records()
