from collections import defaultdict

from src.db.entities.tag_record import *
from src.definitions.database import TAG_COLUMNS
from src.definitions.data_management import ID3Tag, CANONICAL_KEY_MAP
from src.tools.data_management.audio_file import AudioFile


class TagRecordFactory:
    """ TODO. """

    def __init__(self, file_path, track_id, session):
        """ TODO. """
        self.file_path = file_path
        self.track_id = track_id
        self.audio_file = AudioFile(self.file_path)
        self.row = self.create_row()
        self.session = session

    def build(self, cmd, args):
        """ TODO. """
        getattr(self, cmd)(**args)

    def create_row(self):
        """ TODO. """
        row = {k.name.lower(): self.audio_file.get_tag(k) for k in TAG_COLUMNS}
        row['track_id'] = self.track_id
        return row

    def create_initial_tag_record(self):
        """ TODO. """
        if self.session.query(InitialTagRecord).filter_by(track_id=self.track_id).first() is not None:
            return

        self.session.add(InitialTagRecord(**self.row))

    def create_post_mik_tag_record(self):
        """ TODO. """
        if self.session.query(PostMIKTagRecord).filter_by(track_id=self.track_id).first() is not None:
            return

        mik_comment = self.audio_file.get_tag(ID3Tag.COMMENT_ENG)
        try:
            if mik_comment is not None:
                key_bpm = [e.strip() for e in mik_comment.split(' - ')]
                if len(key_bpm) == 2:
                    self.row[ID3Tag.BPM.name.lower()] = float(key_bpm[1])
                    self.row[ID3Tag.KEY.name.lower()] = key_bpm[0]
                else:
                    raise Exception('Incorrect format')
        except Exception:
            pass

        self.session.add(PostMIKTagRecord(**self.row))

    def create_post_rekordbox_tag_record(self, rb_overrides):
        """ TODO. """
        if self.session.query(PostRekordboxTagRecord).filter_by(track_id=self.track_id).first() is not None:
            return

        title = self.row[ID3Tag.TITLE.name.lower()]
        for k, v in rb_overrides[title].items():
            self.row[k] = v
        self.session.add(PostRekordboxTagRecord(**self.row))

    def create_final_tag_record(self):
        """ TODO. """
        if self.session.query(FinalTagRecord).filter_by(track_id=self.track_id).first() is not None:
            return
        initial_record = self.session.query(InitialTagRecord).filter_by(track_id=self.track_id).first()
        post_mik_record = self.session.query(PostMIKTagRecord).filter_by(track_id=self.track_id).first()
        post_rb_record = self.session.query(PostRekordboxTagRecord).filter_by(track_id=self.track_id).first()
        row = {
            'track_id': initial_record.track_id,
            'title': initial_record.title,
            'bpm': self._get_final_bpm(initial_record, post_mik_record, post_rb_record),
            'key': self._get_final_key(initial_record, post_mik_record, post_rb_record),
            'energy': post_mik_record.energy,
            'artist': initial_record.artist,
            'remixer': initial_record.remixer
        }
        self.session.add(FinalTagRecord(**row))

    def _get_final_bpm(self, initial_record, mik_record, rb_record):
        bpm_dict = defaultdict(int)
        for record in [initial_record, mik_record, rb_record]:
            bpm_dict[record.bpm] += 1

        reverse_bpm_dict = defaultdict(list)
        for k, v in bpm_dict.items():
            reverse_bpm_dict[v].append(k)

        max_bpm_freq = max(list(reverse_bpm_dict.keys()))
        if len(reverse_bpm_dict[max_bpm_freq]) == 1:
            return reverse_bpm_dict[max_bpm_freq][0]

        return rb_record.bpm

    def _get_final_key(self, initial_record, mik_record, rb_record):
        key_dict = defaultdict(int)
        record_keys = ([(record, CANONICAL_KEY_MAP.get(record.key.lower()).capitalize())
                        for record in [initial_record, mik_record, rb_record]])
        for _, key in record_keys:
            key_dict[key] += 1

        reverse_key_dict = defaultdict(list)
        for k, v in key_dict.items():
            reverse_key_dict[v].append(k)

        max_key_freq = max(list(reverse_key_dict.keys()))
        if len(reverse_key_dict[max_key_freq]) == 1:
            return reverse_key_dict[max_key_freq][0]

        return record_keys[2][1]
