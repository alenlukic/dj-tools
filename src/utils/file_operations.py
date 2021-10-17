from os import listdir, remove, stat as osstat
from os.path import basename, isfile, join, splitext
from shutil import copyfile

from src.definitions.common import IS_UNIX, PROCESSED_MUSIC_DIR
from src.definitions.file_operations import AUDIO_TYPES, FILE_STAGING_DIR


def delete_track_files(track):
    file_path = track.file_path
    if isfile(file_path):
        remove(file_path)

    staging_path = join(FILE_STAGING_DIR, basename(file_path))
    if isfile(staging_path):
        remove(staging_path)


def get_audio_files(input_dir=PROCESSED_MUSIC_DIR):
    return [f for f in listdir(input_dir) if isfile(join(input_dir, f)) and splitext(f)[-1].lower() in AUDIO_TYPES]


def get_file_creation_time(full_path):
    try:
        return osstat(full_path).st_birthtime if IS_UNIX else osstat(full_path).st_ctime
    except Exception:
        return osstat(full_path).st_ctime


def get_track_load_path(track):
    if FILE_STAGING_DIR is None:
        return track.file_path

    if not isfile(track.file_path):
        stage_tracks([track])

    return join(FILE_STAGING_DIR, basename(track.file_path))


def stage_tracks(tracks):
    if FILE_STAGING_DIR is None:
        return

    for track_path in [t.file_path for t in tracks]:
        if not isfile(track_path):
            continue

        base_name = basename(track_path)
        staged_path = join(FILE_STAGING_DIR, base_name)
        if isfile(staged_path):
            continue

        copyfile(track_path, staged_path)
