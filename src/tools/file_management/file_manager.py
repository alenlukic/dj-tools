from os import chmod
import stat

from src.definitions.common import *
from src.utils.file_management import *


class FileManager:
    """ Class encapsulating file operations and manipulation. """

    def __init__(self, audio_dir=PROCESSED_MUSIC_DIR):
        """
        Initializes class with music directory info.

        :param audio_dir - directory containing processed (e.g. renamed) tracks.
        """

        self.audio_dir = audio_dir
        self.audio_files = get_audio_files(self.audio_dir)

    def set_audio_file_permissions(self):
        """ Makes all audio files in user's music directory readable and writable. """
        permissions = stat.S_IREAD | stat.S_IROTH | stat.S_IWRITE | stat.S_IWOTH
        for file in self.audio_files:
            chmod(join(self.audio_dir, file), permissions)
