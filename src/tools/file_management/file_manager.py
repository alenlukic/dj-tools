from eyed3 import load
from os import chmod, remove
from os.path import basename
from shutil import copyfile
import stat

from src.definitions.common import *
from src.definitions.data_management import ID3Tag
from src.utils.file_management import *


class FileManager:
    """ Class encapsulating file operations and manipulation. """

    def __init__(self, audio_dir=PROCESSED_MUSIC_DIR, data_dir=DATA_DIR):
        """
        Initializes class with music directory info.

        :param audio_dir - directory containing processed (e.g. renamed) tracks.
        """

        self.audio_dir = audio_dir
        self.data_dir = data_dir
        self.audio_files = get_audio_files(self.audio_dir)

    def set_audio_file_permissions(self):
        """ Makes all audio files in user's music directory readable and writable. """
        permissions = stat.S_IREAD | stat.S_IROTH | stat.S_IWRITE | stat.S_IWOTH
        for file in self.audio_files:
            chmod(join(self.audio_dir, file), permissions)

    @staticmethod
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
            destination = hq_dir if FileManager._is_high_quality(track_path) else lq_dir
            new_name = join(destination, track_name)
            print('Moving:\t%s\nto:\t\t%s' % (track_name, destination))

            # Move file to destination and delete from source
            copyfile(f, new_name)
            remove(f)

    @staticmethod
    def _is_high_quality(track_path):
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
