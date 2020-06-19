from src.definitions.db import TagRecordType
from src.tools.db.track_metadata_pipeline import TrackMetadataPipeline


if __name__ == '__main__':
    TrackMetadataPipeline(TagRecordType.FINAL.value).create_tag_records()
