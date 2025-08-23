from collections import defaultdict

import src.db.entities.tag_record as tag_records
from src.definitions.ingestion_pipeline import TAG_COLUMNS
from src.definitions.data_management import ID3Tag, CANONICAL_KEY_MAP
from src.lib.data_management.definitions.audio_file import AudioFile
from src.lib.error_management.service import handle


class TagRecordFactory:
    def __init__(self, record_type, file_name, file_dir, track_id, session):
        self.track_id = track_id
        self.session = session
        self.tag_record = None
        self.TagRecordEntity = getattr(tag_records, record_type)
        self.audio_file = AudioFile(file_name, file_dir)
        self.row = self.create_row()

    def create_tag_record(self):
        if (
            self.session.query(self.TagRecordEntity)
            .filter_by(track_id=self.track_id)
            .first()
            is not None
        ):
            raise Exception(
                "%s already exists in table for %s record types"
                % (self.track_id, self.TagRecordEntity.__class__.__name__)
            )

        try:
            self.update_row()
        except Exception as e:
            handle(e)
            return

        self.update_database()

        return self.tag_record

    def create_row(self):
        row = {k.name.lower(): self.audio_file.get_tag(k) for k in TAG_COLUMNS}
        row["track_id"] = self.track_id
        return row

    def update_row(self):
        pass

    def update_database(self):
        self.tag_record = self.TagRecordEntity(**self.row)
        self.session.guarded_add(self.tag_record)


class InitialRecordFactory(TagRecordFactory):
    def update_row(self):
        del self.row[ID3Tag.ENERGY.name.lower()]


class PostMIKRecordFactory(TagRecordFactory):
    def update_row(self):
        mik_comment = self.audio_file.get_tag(ID3Tag.COMMENT_ENG)
        if mik_comment is None:
            return

        key_bpm = [e.strip() for e in mik_comment.split(" - ")]
        if len(key_bpm) == 2:
            self.row[ID3Tag.BPM.name.lower()] = float(key_bpm[1])
            self.row[ID3Tag.KEY.name.lower()] = key_bpm[0]


class PostRBRecordFactory(TagRecordFactory):
    def __init__(
        self, record_type, file_name, file_dir, track_id, session, rb_overrides
    ):
        super().__init__(record_type, file_name, file_dir, track_id, session)
        self.rb_overrides = rb_overrides

    def update_row(self):
        title = self.row[ID3Tag.TITLE.name.lower()]
        for k, v in self.rb_overrides[title].items():
            self.row[k] = v


class FinalRecordFactory(TagRecordFactory):
    def update_row(self):
        track_id = self.track_id
        initial_record = (
            self.session.query(tag_records.InitialTagRecord)
            .filter_by(track_id=track_id)
            .first()
        )
        post_mik_record = (
            self.session.query(tag_records.PostMIKTagRecord)
            .filter_by(track_id=track_id)
            .first()
        )
        post_rb_record = (
            self.session.query(tag_records.PostRekordboxTagRecord)
            .filter_by(track_id=track_id)
            .first()
        )

        self.row = {
            "track_id": track_id,
            "title": initial_record.title,
            "bpm": FinalRecordFactory._get_final_bpm(
                initial_record, post_mik_record, post_rb_record
            ),
            "key": FinalRecordFactory._get_final_key(
                initial_record, post_mik_record, post_rb_record
            ),
            "energy": post_mik_record.energy,
        }

    @staticmethod
    def _get_final_bpm(initial_record, mik_record, rb_record):
        bpm_dict = defaultdict(int)
        for record in filter(
            lambda r: r is not None and r.bpm is not None,
            [initial_record, mik_record, rb_record],
        ):
            bpm_dict[float(record.bpm)] += 1

        reverse_bpm_dict = defaultdict(list)
        for k, v in bpm_dict.items():
            reverse_bpm_dict[v].append(k)

        max_bpm_freq = max(list(reverse_bpm_dict.keys()))
        if len(reverse_bpm_dict[max_bpm_freq]) == 1:
            return reverse_bpm_dict[max_bpm_freq][0]

        return float(rb_record.bpm)

    @staticmethod
    def _get_final_key(initial_record, mik_record, rb_record):
        initial_record_key = (
            None
            if (initial_record is None or initial_record.key is None)
            else CANONICAL_KEY_MAP.get(initial_record.key.lower())
        )
        mik_record_keys = (
            [
                CANONICAL_KEY_MAP.get(mik_key.lower())
                for mik_key in mik_record.key.split("/")
            ]
            if (mik_record is not None and mik_record.key is not None)
            else []
        )
        rb_record_key = (
            CANONICAL_KEY_MAP.get(rb_record.key.lower())
            if (rb_record is not None and rb_record.key is not None)
            else None
        )

        key_dict = defaultdict(int)
        for key in filter(
            lambda rk: rk is not None,
            [initial_record_key] + mik_record_keys + [rb_record_key],
        ):
            key_dict[key.capitalize()] += 1

        reverse_key_dict = defaultdict(list)
        for k, v in key_dict.items():
            reverse_key_dict[v].append(k)

        max_key_freq = max(list(reverse_key_dict.keys()))
        if len(reverse_key_dict[max_key_freq]) == 1:
            return reverse_key_dict[max_key_freq][0]

        return rb_record_key
