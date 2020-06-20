from src.definitions.db import TagRecordType
from src.tools.db.tag_record_pipeline import TagRecordPipeline


if __name__ == '__main__':
    TagRecordPipeline(TagRecordType.FINAL.value).sync_final_records()
