from src.definitions.db import TagRecordType
from src.tools.db.tag_record_pipeline import TagRecordPipeline


if __name__ == '__main__':
    TagRecordPipeline(TagRecordType.POST_MIK).create_tag_records()
