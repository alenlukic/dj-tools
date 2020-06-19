from src.db.entities.tag_record import *
from src.definitions.database import TAG_COLUMNS
from src.definitions.database import ID3Tag
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

    def create_row(self):
        """ TODO. """
        row = {k.name.lower(): self.audio_file.get_tag(k) for k in TAG_COLUMNS}
        row['track_id'] = self.track_id
        return row

    def create_initial_tag_record(self):
        """ TODO. """
        self.session.add(InitialTagRecord(**self.row))

    def create_post_mik_tag_record(self):
        """ TODO. """
        mik_comment = self.audio_file.get_tag(ID3Tag.COMMENT_ENG)
        if mik_comment is not None:
            key_bpm = [e.strip() for e in mik_comment.split(' - ')]
            self.row[ID3Tag.BPM.name.lower()] = float(key_bpm[1])

        self.session.add(PostMIKTagRecord(**self.row))

    def create_post_rekordbox_tag_record(self, rb_overrides):
        """ TODO. """
        title = self.row[ID3Tag.TITLE.name.lower()]
        for k, v in rb_overrides[title].items():
            self.row[k] = v
        self.session.add(PostRekordboxTagRecord(**self.row))

    def create_final_tag_record(self):
        """ TODO. """
        initial_record = self.session.query(InitialTagRecord).filter_by(track_id=self.track_id).first()
        post_mik_record = self.session.query(PostMIKTagRecord).filter_by(track_id=self.track_id).first()
        post_rb_record = self.session.query(PostRekordboxTagRecord).filter_by(track_id=self.track_id).first()
        self.session.add(FinalTagRecord(**self.row))

    def build(self, cmd, args):
        """ TODO. """
        getattr(self, cmd)(**args)
