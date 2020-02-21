from collections import defaultdict

import mutagen

from src.definitions.data_management import ALL_ID3_TAGS, METADATA_KEY_TO_ID3
from src.tools.data_management.formats.audio_file import AudioFile


class AIFFFile(AudioFile):
    def __init__(self, full_path):
        AudioFile.__init__(self, full_path)

    def read_id3(self):
        """ Read ID3 data from file. """

        id3 = mutagen.File(self.full_path)
        if id3 is None:
            raise Exception('Could not load ID3 data for %s' % self.full_path)

        return id3

    def read_tags(self):
        """ Read relevant tags from ID3 data. """
        tag_dict = self.id3.items()
        return defaultdict(str, {k: v.text[0] for k, v in tag_dict if k in ALL_ID3_TAGS and len(v.text or []) > 0})

    def write_tags(self):
        """ Writes ID3 tags to file. """

        track_metadata = self.get_metadata()
        for k, v in track_metadata.items():
            mk = METADATA_KEY_TO_ID3.get(k)
            if mk in self.id3:
                self.id3[mk].text = [v]

        self.id3.save()
