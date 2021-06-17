from os import chmod, listdir, stat as osstat
from os.path import basename, isfile, join, splitext
from shutil import copyfile
import stat

from src.definitions.common import IS_UNIX, PROCESSED_MUSIC_DIR
from src.definitions.file_operations import AUDIO_TYPES, FILE_STAGING_DIR


def get_audio_files(input_dir=PROCESSED_MUSIC_DIR):
    """
    Gets all the audio files in the given directory.

    :param input_dir: Directory to inspect for audio files.
    """
    return [f for f in listdir(input_dir) if isfile(join(input_dir, f)) and splitext(f)[-1].lower() in AUDIO_TYPES]


def get_file_creation_time(full_path):
    try:
        return osstat(full_path).st_birthtime if IS_UNIX else osstat(full_path).st_ctime
    except Exception:
        return osstat(full_path).st_ctime


def get_track_load_target(track):
    if FILE_STAGING_DIR is None:
        return track.file_path

    if not isfile(track.file_path):
        stage_tracks([track])

    return join(FILE_STAGING_DIR, basename(track.file_path))


def set_audio_file_permissions(audio_dir=PROCESSED_MUSIC_DIR):
    """
    Makes all audio files in directory readable and writable.

    :param audio_dir: Directory where audio files are located.
    """

    permissions = stat.S_IREAD | stat.S_IROTH | stat.S_IWRITE | stat.S_IWOTH
    audio_files = get_audio_files(audio_dir)
    for file in audio_files:
        chmod(join(audio_dir, file), permissions)


def stage_tracks(tracks):
    if FILE_STAGING_DIR is None:
        return

    print('Staging %d tracks' % len(tracks))

    for track_path in [t.file_path for t in tracks]:
        if not isfile(track_path):
            continue

        base_name = basename(track_path)
        staged_path = join(FILE_STAGING_DIR, base_name)
        if isfile(staged_path):
            continue

        copyfile(track_path, staged_path)
