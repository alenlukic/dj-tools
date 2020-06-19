from os.path import join

from src.db import database
from src.db.entities.track import Track
from src.definitions.common import CONFIG, PROCESSED_MUSIC_DIR
from src.definitions.data_management import ID3Tag
from src.definitions.db import TagRecordType
import src.tools.db.tag_record_factory as tag_record_factories
from src.utils.common import is_empty
from src.utils.errors import handle_error
from src.utils.file_operations import get_audio_files


class TagRecordPipeline:
    PIPELINE_DIR = CONFIG['PIPELINE_DIR']
    RECORD_FACTORIES = {
        TagRecordType.INITIAL.value: 'TagRecordFactory',
        TagRecordType.POST_MIK.value: 'PostMIKRecordFactory',
        TagRecordType.POST_RB.value: 'PostRBRecordFactory',
        TagRecordType.FINAL.value: 'FinalRecordFactory'
    }

    def __init__(self, record_type, track_dir=PIPELINE_DIR):
        self.record_type = record_type
        self.session = database.create_session()
        self.track_dir = track_dir
        self.track_files = get_audio_files(track_dir)

    def create_tag_records(self):
        database.enable_dry_run()

        factory_name = self.RECORD_FACTORIES.get(self.record_type, None)
        if factory_name is None:
            raise Exception('Did not find a factory for record type %s' % self.record_type)

        rb_overrides = self._load_rb_tags() if self.record_type == TagRecordType.POST_RB.value else None

        try:
            for track_file in self.track_files:
                track_path = join(self.track_dir, track_file)
                processed_track_path = join(PROCESSED_MUSIC_DIR, track_file)
                track = self.session.query(Track).filter_by(file_path=processed_track_path).first()

                if track is None:
                    print('%s not found, skipping' % processed_track_path)
                    continue

                cmd_args = {
                    'record_type': self.record_type,
                    'file_path': track_path,
                    'track_id': track.id,
                    'session': self.session
                }
                if self.record_type == TagRecordType.POST_RB.value:
                    cmd_args['rb_overrides'] = rb_overrides

                factory = getattr(tag_record_factories, factory_name)(**cmd_args)
                factory.create_tag_record()

            self.session.commit()

        except Exception as e:
            self.session.rollback()
            handle_error(e)

        finally:
            self.session.close()
            database.disable_dry_run()

    def _load_rb_tags(self):
        rb_tag_file = CONFIG['REKORDBOX_TAG_FILE']
        track_tags = {}

        with open(rb_tag_file, 'r', encoding='utf-16', errors='ignore') as f:
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
