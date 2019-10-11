from src.definitions.file_processing import *
from src.utils.file_processing import *


class DataManager:

    def __init__(self, audio_dir=PROCESSED_MUSIC_DIR, data_dir=DATA_DIR):
        """
        Initializes class with music directory info.

        :param audio_dir - directory containing processed (e.g. renamed) tracks.
        """

        self.audio_dir = audio_dir
        self.audio_files = get_audio_files(self.audio_dir)

    def generate_artist_count(self):
        for f in self.audio_files:
            track_path = join(self.audio_dir, f)
            id3_data = extract_id3_data(track_path)

            # Use heuristics to derive artists from track title if no ID3 data
            if id3_data is None:
                continue
