from os import listdir, remove, stat as osstat
from os.path import isfile, join, splitext
from shutil import copyfile

from src.definitions.common import IS_UNIX, PROCESSED_MUSIC_DIR
from src.definitions.file_operations import AUDIO_TYPES, FILE_STAGING_DIR


def delete_track_files(track, track_directory=PROCESSED_MUSIC_DIR):
    file_name = track.file_name
    file_path = join(track_directory, file_name)

    if isfile(file_path):
        remove(file_path)

    staging_path = join(FILE_STAGING_DIR, file_name)
    if isfile(staging_path):
        remove(staging_path)


def get_audio_files(input_dir=PROCESSED_MUSIC_DIR):
    return [f for f in listdir(input_dir) if isfile(join(input_dir, f)) and splitext(f)[-1].lower() in AUDIO_TYPES]


def get_flac_files(input_dir):
    return [f for f in listdir(input_dir) if isfile(join(input_dir, f)) and splitext(f)[-1].lower() == '.flac']


def get_file_creation_time(full_path):
    try:
        return osstat(full_path).st_birthtime if IS_UNIX else osstat(full_path).st_ctime
    except Exception:
        return osstat(full_path).st_ctime


def get_track_load_path(track):
    file_path = join(PROCESSED_MUSIC_DIR, track.file_name)

    if FILE_STAGING_DIR is None:
        return file_path

    if not isfile(file_path):
        stage_tracks([track])

    return join(FILE_STAGING_DIR, file_path)


def stage_tracks(tracks):
    if FILE_STAGING_DIR is None:
        return

    for track_name in [t.file_name for t in tracks]:
        file_path = join(PROCESSED_MUSIC_DIR, track_name)
        if not isfile(file_path):
            continue

        staged_path = join(FILE_STAGING_DIR, track_name)
        if isfile(staged_path):
            continue

        copyfile(file_path, staged_path)
