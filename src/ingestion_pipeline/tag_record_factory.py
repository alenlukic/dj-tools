from collections import defaultdict

import src.models.tag_record as tag_records
from src.ingestion_pipeline.config import TAG_COLUMNS
from src.data_management.config import ID3Tag, CANONICAL_KEY_MAP
from src.data_management.audio_file import AudioFile
from src.errors import handle


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
        self.session.add(self.tag_record)

    def get_tag_record(self):
        return self.tag_record


class InitialRecordFactory(TagRecordFactory):
    pass


class PostMIKRecordFactory(TagRecordFactory):
    pass


class PostRBRecordFactory(TagRecordFactory):
    def __init__(
        self,
        record_type,
        file_name,
        file_dir,
        track_id,
        session,
        rb_overrides=None,
    ):
        self.rb_overrides = rb_overrides or {}
        super().__init__(record_type, file_name, file_dir, track_id, session)

    def update_row(self):
        file_name = self.audio_file.get_basename()
        overrides = self.rb_overrides.get(file_name, {})
        for k, v in overrides.items():
            self.row[k] = v


class FinalRecordFactory(TagRecordFactory):
    def __init__(self, record_type, file_name, file_dir, track_id, session):
        super().__init__(record_type, file_name, file_dir, track_id, session)

    def update_row(self):
        self.row = self._build_final_row(self.track_id)

    def _build_final_row(self, track_id):
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
