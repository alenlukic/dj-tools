from os import listdir
from os.path import isfile, join

from src.definitions.file_management import *


def get_audio_files(input_dir):
    """
    Gets all the audio files in the given directory.

    :param input_dir - directory to inspect for audio files.
    """
    files = list(filter(lambda f: isfile(join(input_dir, f)), listdir(input_dir)))
    return list(filter(lambda f: f.split('.')[-1].lower() in AUDIO_TYPES, files))


