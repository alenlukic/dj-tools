from eyed3 import load
from os import listdir
from os.path import isfile, join

from src.definitions.data_management import ID3Tag
from src.definitions.file_management import *


def get_audio_files(input_dir):
    """
    Gets all the audio files in the given directory.

    :param input_dir - directory to inspect for audio files.
    """
    files = list(filter(lambda f: isfile(join(input_dir, f)), listdir(input_dir)))
    return list(filter(lambda f: f.split('.')[-1].lower() in AUDIO_TYPES, files))


def is_high_quality(track_path):
    """
    Determine if a track is high quality. Note: this may not work on true 320 kbps MP3 files that are obtained from
    somewhere other than Beatport (e.g. promos, free downloads).

    :param track_path - full qualified path to audio file
    """

    # Lossless files are high quality
    extension = track_path.split('.')[-1]
    if extension in LOSSLESS:
        return True

    # Beatport mp3 files are high quality too
    md = load(track_path)
    return False if md is None else any(frame.id == ID3Tag.BEATPORT for frame in md.tag.frameiter())
