from os import chmod, listdir, stat
from os.path import isfile, join, splitext

from src.definitions.common import IS_UNIX, PROCESSED_MUSIC_DIR
from src.definitions.file_operations import AUDIO_TYPES


def get_audio_files(input_dir=PROCESSED_MUSIC_DIR):
    """
    Gets all the audio files in the given directory.

    :param input_dir: Directory to inspect for audio files.
    """
    return [f for f in listdir(input_dir) if isfile(join(input_dir, f)) and splitext(f)[-1].lower() in AUDIO_TYPES]


def get_file_creation_time(full_path):
    try:
        return stat(full_path).st_birthtime if IS_UNIX else stat(full_path).st_ctime
    except Exception:
        return stat(full_path).st_ctime


def set_audio_file_permissions(audio_dir=PROCESSED_MUSIC_DIR):
    """
    Makes all audio files in directory readable and writable.

    :param audio_dir: Directory where audio files are located.
    """

    permissions = stat.S_IREAD | stat.S_IROTH | stat.S_IWRITE | stat.S_IWOTH
    audio_files = get_audio_files(audio_dir)
    for file in audio_files:
        chmod(join(audio_dir, file), permissions)
