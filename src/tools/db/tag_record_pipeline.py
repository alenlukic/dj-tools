from ast import literal_eval
from os.path import join, exists
from shutil import copyfile

from src.db import database
from src.db.entities.track import Track
from src.db.entities.tag_record import FinalTagRecord
from src.definitions.common import CONFIG, EXPERIMENTAL_MUSIC_DIR, PIPELINE_MUSIC_DIR, PROCESSED_MUSIC_DIR
from src.definitions.data_management import MD_COMPOSITE_REGEX, ID3Tag, TrackDBCols
from src.definitions.db import TagRecordType
from src.tools.data_management.audio_file import AudioFile
import src.tools.db.tag_record_factory as tag_record_factories
from src.utils.data_management import normalize_tag_text
from src.utils.common import is_empty
from src.utils.errors import handle_error
from src.utils.file_operations import get_audio_files


class TagRecordPipeline:
    RECORD_FACTORIES = {
        TagRecordType.INITIAL.value: 'TagRecordFactory',
        TagRecordType.POST_MIK.value: 'PostMIKRecordFactory',
        TagRecordType.POST_RB.value: 'PostRBRecordFactory',
        TagRecordType.FINAL.value: 'FinalRecordFactory'
    }

    def __init__(self, record_type, source_dir=PIPELINE_MUSIC_DIR, target_dir=EXPERIMENTAL_MUSIC_DIR):
        self.record_type = record_type
        self.session = database.create_session()
        self.source_dir = source_dir
        self.target_dir = target_dir
        self.track_files = get_audio_files(source_dir)

    def create_tag_records(self):
        factory_name = self.RECORD_FACTORIES.get(self.record_type, None)
        if factory_name is None:
            raise Exception('Did not find a factory for record type %s' % self.record_type)

        rb_overrides = self._load_rb_tags() if self.record_type == TagRecordType.POST_RB.value else None

        try:
            for track_file in self.track_files:
                track_path = join(self.source_dir, track_file)
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

    # def sync_final_records(self):
    #     """ Syncs records in the final_tags table to tracks' ID3 tags and the tracks table. TODO: clean this up!"""
    #     # final_records = {fr.title: fr for fr in self.session.query(FinalTagRecord).all()}
    #     tracks = {t.file_path: t for t in self.session.query(Track).all()}
    #
    #     for track_file in self.track_files:
    #         source_path = join(PROCESSED_MUSIC_DIR, track_file)
    #         track = tracks[source_path]
    #         audio_file = AudioFile(source_path)

            # title = track.title
            # record = final_records[normalize_tag_text(title)]

            # title_sans_md = MD_COMPOSITE_REGEX.split(title)[1].strip().split(' - ')[-1].strip()
            # bpm = float(record.bpm)
            # key = record.key
            # energy = None if record.energy is None else int(record.energy)
            #
            # updated_tags = {k: v for k, v in {
            #     TrackDBCols.TITLE.value: title_sans_md,
            #     TrackDBCols.BPM.value: bpm,
            #     TrackDBCols.KEY.value: key,
            #     TrackDBCols.ENERGY.value: energy
            # }.items() if v is not None}

            # key = audio_file.get_tag(ID3Tag.KEY, None)
            # camelot_code = audio_file.format_camelot_code(key.lower())
            # bpm = audio_file.format_bpm()
            # title_sans_md = MD_COMPOSITE_REGEX.split(track.title)[1].strip()
            # title = ' '.join([audio_file.generate_title_prefix(camelot_code, key, bpm), title_sans_md])

            # updated_tags = {k: v for k, v in {
            #     TrackDBCols.TITLE.value: title,
            #     TrackDBCols.BPM.value: bpm
            # }.items() if v is not None}
            # audio_file.write_tags(updated_tags)

            # track.title = title
            # track.bpm = float(bpm)

            # comment = literal_eval(audio_file.generate_metadata()[TrackDBCols.COMMENT.value])
            # comment[TrackDBCols.TITLE.value] = title
            # comment[TrackDBCols.BPM.value] = track.bpm
            # comment = str(comment)
            # audio_file.write_tags({TrackDBCols.COMMENT.value: track.comment})
            # track.comment = comment

        # self.session.commit()

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
