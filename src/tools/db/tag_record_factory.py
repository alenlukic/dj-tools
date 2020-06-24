from collections import defaultdict

import src.db.entities.tag_record as tag_records
from src.definitions.db import TAG_COLUMNS
from src.definitions.data_management import ID3Tag, CANONICAL_KEY_MAP
from src.tools.data_management.audio_file import AudioFile


class TagRecordFactory:
    def __init__(self, record_type, file_path, track_id, session):
        self.file_path = file_path
        self.track_id = track_id
        self.session = session
        self.tag_record = None
        self.TagRecordEntity = getattr(tag_records, record_type)
        self.audio_file = AudioFile(self.file_path)
        self.row = self.create_row()

    def create_tag_record(self):
        if self.session.query(self.TagRecordEntity).filter_by(track_id=self.track_id).first() is not None:
            raise Exception('%s already exists in table for %s record types' %
                            (self.track_id, self.TagRecordEntity.__class__.__name__))

        self.update_row()
        self.update_database()

        return self.tag_record

    def create_row(self):
        row = {k.name.lower(): self.audio_file.get_tag(k) for k in TAG_COLUMNS}
        row['track_id'] = self.track_id
        return row

    def update_row(self):
        pass

    def update_database(self):
        self.tag_record = self.TagRecordEntity(**self.row)
        self.session.add(self.tag_record)


class PostMIKRecordFactory(TagRecordFactory):
    def update_row(self):
        # MIK won't write float bpm to ID3, so we write to the comment tag instead
        mik_comment = self.audio_file.get_tag(ID3Tag.COMMENT_ENG)
        try:
            if mik_comment is not None:
                key_bpm = [e.strip() for e in mik_comment.split(' - ')]
                if len(key_bpm) == 2:
                    self.row[ID3Tag.BPM.name.lower()] = float(key_bpm[1])
                    self.row[ID3Tag.KEY.name.lower()] = key_bpm[0]
        except Exception:
            pass


class PostRBRecordFactory(TagRecordFactory):
    def __init__(self, record_type, file_path, track_id, session, rb_overrides):
        super().__init__(record_type, file_path, track_id, session)
        self.rb_overrides = rb_overrides

    def update_row(self):
        title = self.row[ID3Tag.TITLE.name.lower()]
        for k, v in self.rb_overrides[title].items():
            self.row[k] = v


class FinalRecordFactory(TagRecordFactory):
    def update_row(self):
        track_id = self.track_id
        initial_record = self.session.query(tag_records.InitialTagRecord).filter_by(track_id=track_id).first()
        post_mik_record = self.session.query(tag_records.PostMIKTagRecord).filter_by(track_id=track_id).first()
        post_rb_record = self.session.query(tag_records.PostRekordboxTagRecord).filter_by(track_id=track_id).first()
        self.row = {
            'track_id': track_id,
            'title': initial_record.title,
            'bpm': self._get_final_bpm(initial_record, post_mik_record, post_rb_record),
            'key': self._get_final_key(initial_record, post_mik_record, post_rb_record),
            'energy': post_mik_record.energy,
            'artist': initial_record.artist,
            'remixer': initial_record.remixer
        }

    def _get_final_bpm(self, initial_record, mik_record, rb_record):
        bpm_dict = defaultdict(int)
        for record in [initial_record, mik_record, rb_record]:
            bpm_dict[float(record.bpm)] += 1

        reverse_bpm_dict = defaultdict(list)
        for k, v in bpm_dict.items():
            reverse_bpm_dict[v].append(k)

        max_bpm_freq = max(list(reverse_bpm_dict.keys()))
        if len(reverse_bpm_dict[max_bpm_freq]) == 1:
            return reverse_bpm_dict[max_bpm_freq][0]

        return float(rb_record.bpm)

    def _get_final_key(self, initial_record, mik_record, rb_record):
        initial_record_key = CANONICAL_KEY_MAP.get(initial_record.key.lower()).capitalize()
        mik_record_keys = [CANONICAL_KEY_MAP.get(mik_key.lower()).capitalize() for mik_key in mik_record.key.split('/')]
        rb_record_key = CANONICAL_KEY_MAP.get(rb_record.key.lower()).capitalize()

        key_dict = defaultdict(int)
        key_dict[initial_record_key] += 1
        key_dict[rb_record_key] += 1
        for mik_record_key in mik_record_keys:
            key_dict[mik_record_key] += 1

        reverse_key_dict = defaultdict(list)
        for k, v in key_dict.items():
            reverse_key_dict[v].append(k)

        max_key_freq = max(list(reverse_key_dict.keys()))
        if len(reverse_key_dict[max_key_freq]) == 1:
            return reverse_key_dict[max_key_freq][0]

        return rb_record_key
