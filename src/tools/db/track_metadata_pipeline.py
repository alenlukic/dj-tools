from os.path import join

from src.db import database
from src.db.entities.track import Track
from src.definitions.common import CONFIG, PROCESSED_MUSIC_DIR
from src.definitions.data_management import ID3Tag
from src.tools.db.tag_record_factory import TagRecordFactory
from src.utils.common import is_empty
from src.utils.errors import handle_error
from src.utils.file_operations import get_audio_files


PIPELINE_DIR = CONFIG['PIPELINE_DIR']


class TrackMetadataPipeline:
    """ TODO. """

    def __init__(self, cmd, track_dir=PIPELINE_DIR):
        self.cmd = cmd
        self.database = database
        self.track_dir = track_dir
        self.track_files = get_audio_files(track_dir)
        self.cmd_args = {'rb_overrides': self._load_rb_tags()} if cmd == 'create_post_rekordbox_tag_record' else {}

    def create_tag_records(self):
        """ TODO. """
        session = self.database.create_session()

        try:
            for track_file in self.track_files:
                track_path = join(PIPELINE_DIR, track_file)
                track_id = session.query(Track).filter_by(file_path=join(PROCESSED_MUSIC_DIR, track_file)).first().id
                record_builder = TagRecordFactory(track_path, track_id, session)
                record_builder.build(self.cmd, self.cmd_args)

            session.commit()

        except Exception as e:
            session.rollback()
            handle_error(e)

        finally:
            session.close()

    def _load_rb_tags(self):
        """ TODO. """
        rb_tag_file = CONFIG['REKORDBOX_TAG_FILE']
        track_tags = {}

        with open(rb_tag_file, 'r', encoding='utf-16', errors='ignore') as f:
            lines = [x.strip() for x in f.readlines() if not is_empty(x)]
            for i, line in enumerate(lines):
                if i == 0:
                    continue
                tags = line.split('\t')
                row_overrides = {
                    ID3Tag.BPM.name.lower(): float(tags[2]),
                    ID3Tag.KEY.name.lower(): tags[3]
                }
                track_tags[tags[1]] = row_overrides

        return track_tags
