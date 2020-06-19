from src.tools.db.track_metadata_pipeline import TrackMetadataPipeline


if __name__ == '__main__':
    TrackMetadataPipeline('create_post_mik_tag_record').create_tag_records()
