from collections import ChainMap
from shutil import copyfile
from os.path import splitext

from src.db import database
from src.db.entities.track import Track
from src.definitions.common import PROCESSED_MUSIC_DIR
from src.definitions.data_management import TrackDBCols
from src.definitions.ingestion_pipeline import *
from src.lib.data_management.definitions.audio_file import AudioFile
from src.lib.data_management.service import ingest_tracks
import src.lib.ingestion_pipeline.tag_record_factory as tag_record_factories
from src.utils.common import is_empty
from src.lib.error_management.service import handle
from src.utils.data_management import format_track_title
from src.utils.file_operations import get_audio_files


class PipelineStage:
    def __init__(self, record_type, source_dir=UNPROCESSED_DIR):
        self.record_type = record_type
        self.session = database.create_session()
        self.source_dir = source_dir
        self.track_files = get_audio_files(source_dir)
        self.cmd_overrides = {}

    def execute(self):
        try:
            self.create_tag_records()
            self.session.commit()
        except Exception as e:
            self.session.rollback()
            handle(e)
        finally:
            self.session.close()

    def create_tag_records(self):
        factory_name = TAG_RECORD_FACTORIES.get(self.record_type, None)
        if factory_name is None:
            raise Exception('Did not find a factory for record type %s' % self.record_type)

        tag_records = {}
        for track_file_name in self.track_files:
            try:
                track = self.session.query(Track).filter_by(file_name=track_file_name).first()

                cmd_args = dict(ChainMap(
                    {
                        'record_type': self.record_type,
                        'file_name': track_file_name,
                        'file_dir': PROCESSING_DIR,
                        'track_id': track.id,
                        'session': self.session
                    },
                    self.cmd_overrides
                ))
                factory = getattr(tag_record_factories, factory_name)(**cmd_args)

                tag_record = factory.create_tag_record()
                if tag_record is None:
                    continue

                tag_records[track_file_name] = tag_record

            except Exception as e:
                handle(e, 'Exception occurred processing %s:' % track_file_name)
                continue

        return tag_records


class InitialPipelineStage(PipelineStage):
    def __init__(self, record_type, source_dir=UNPROCESSED_DIR, target_dir=PROCESSING_DIR):
        super().__init__(record_type, source_dir)
        self.target_dir = target_dir

    def execute(self):
        try:
            self.initialize_tracks_in_database()
            self.create_tag_records()
            self.session.commit()
        except Exception as e:
            self.session.rollback()
            handle(e)
        finally:
            self.session.close()

    def initialize_tracks_in_database(self):
        ingest_tracks(self.source_dir, self.target_dir)


class PostRBPipelineStage(PipelineStage):
    def execute(self):
        try:
            self.cmd_overrides = {'rb_overrides': PostRBPipelineStage.load_rb_tags()}
            self.create_tag_records()
            self.session.commit()
        except Exception as e:
            self.session.rollback()
            handle(e)
        finally:
            self.session.close()

    @staticmethod
    def load_rb_tags():
        track_tags = {}

        with open(RB_TAG_FILE, 'r', encoding='utf-16', errors='ignore') as f:
            lines = [x.strip() for x in f.readlines() if not is_empty(x)]
            for i, line in enumerate(lines):
                if i == 0:
                    continue

                tags = line.split('\t')
                track_tags[tags[1]] = {
                    ID3Tag.BPM.name.lower(): float(tags[2]),
                    ID3Tag.KEY.name.lower(): tags[3]
                }

        return track_tags


class FinalPipelineStage(PipelineStage):
    def __init__(self, record_type, source_dir=PROCESSING_DIR, target_dir=FINALIZED_DIR):
        super().__init__(record_type, source_dir)
        self.target_dir = target_dir

    def execute(self):
        try:
            tag_records = self.create_tag_records()
            self.write_tags(tag_records)
            self.update_track_table(tag_records)
            self.session.commit()
        except Exception as e:
            self.session.rollback()
            handle(e)
        finally:
            self.session.close()

    def write_tags(self, tag_records):
        for track_file, tag_record in tag_records.items():
            try:
                old_path = join(self.source_dir, track_file)
                new_path = join(self.target_dir, track_file)
                copyfile(old_path, new_path)

                audio_file = AudioFile(track_file, self.target_dir)
                audio_file.write_tags({
                    TrackDBCols.BPM.value: float(tag_record.bpm),
                    TrackDBCols.KEY.value: tag_record.key
                })

            except Exception as e:
                handle(e, 'Exception occurred processing %s:' % track_file)
                continue

    def update_track_table(self, tag_records):
        for track_file, tag_record in tag_records.items():
            try:
                old_path = join(self.target_dir, track_file)
                _, ext = splitext(old_path)

                audio_file = AudioFile(track_file, self.target_dir)
                metadata = audio_file.get_metadata()

                formatted_title = format_track_title(metadata[TrackDBCols.TITLE.value]) + ext
                new_path = join(PROCESSED_MUSIC_DIR, formatted_title)
                metadata[TrackDBCols.FILE_NAME.value] = new_path

                track = self.session.query(Track).filter_by(id=tag_record.track_id).first()
                metadata[TrackDBCols.DATE_ADDED.value] = track.date_added

                metadata[TrackDBCols.COMMENT.value] = audio_file.generate_comment(metadata)
                for col, val in metadata.items():
                    setattr(track, col, val)

                copyfile(old_path, new_path)
                audio_file = AudioFile(formatted_title)
                audio_file.write_tags(metadata)

            except Exception as e:
                handle(e, 'Exception occurred processing %s:' % track_file)
                continue
