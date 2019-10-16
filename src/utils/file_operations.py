from eyed3 import load
from os import chmod, listdir, remove
from os.path import basename, isfile, join
from shutil import copyfile
import stat

from src.definitions.data_management import ID3Tag
from src.definitions.file_operations import *


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


def separate_low_and_high_quality(source_dir, lq_dir, hq_dir):
    """
    Takes all files in source_dir and moves the low quality ones to low_quality_dir and the high quality ones to
    high_quality_dir. This is useful for cleaning up directories containing audio files or varying quality.
    N.B.: this will delete all files in the original directory.

    :param source_dir - directory containing all audio files
    :param lq_dir - directory to save low quality files to
    :param hq_dir - directory to save high quality files to
    """

    for f in get_audio_files(source_dir):
        track_path = join(source_dir, f)
        track_name = basename(f)

        # Determine destination based on file quality estimate
        destination = hq_dir if is_high_quality(track_path) else lq_dir
        new_name = join(destination, track_name)
        print('Moving:\t%s\nto:\t\t%s' % (track_name, destination))

        # Move file to destination and delete from source
        copyfile(f, new_name)
        remove(f)


def set_audio_file_permissions(audio_dir):
    """
    Makes all audio files in directory readable and writable.

    :param audio_dir - directory where audio files are located.
    """

    permissions = stat.S_IREAD | stat.S_IROTH | stat.S_IWRITE | stat.S_IWOTH
    audio_files = get_audio_files(audio_dir)
    for file in audio_files:
        chmod(join(audio_dir, file), permissions)
