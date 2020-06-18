from src.db.entities.tag_record import *
from src.definitions.database import TAG_COLUMNS
from src.tools.data_management.audio_file import AudioFile


def create_row(track):
    audio_file = AudioFile(track.file_path)
    row = {'ID3Tag.%s' % k.name: audio_file.get_tag(k) for k in TAG_COLUMNS}
    row['track_id'] = track.id
    return row


def create_initial_tag_record(track, session):
    row = create_row(track)
    session.add(InitialTagRecord(**row))
    session.commit()


def create_post_mik_tag_record(track, session):
    row = create_row(track)
    session.add(PostMIKTagRecord(**row))
    session.commit()


def create_post_rekordbox_tag_record(track, session):
    row = create_row(track)
    session.add(PostRekordboxTagRecord(**row))
    session.commit()


def create_final_tag_record(track, session):
    """
    TODO: add consolidation logic here.

    :param track:
    :param session:
    """
    row = create_row(track)
    session.add(FinalTagRecord(**row))
    session.commit()
