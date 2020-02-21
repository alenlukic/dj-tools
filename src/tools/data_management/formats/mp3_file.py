from collections import defaultdict

from eyed3 import load
from eyed3.id3 import frames

from src.definitions.data_management import ALL_ID3_TAGS
from src.tools.data_management.formats.audio_file import AudioFile


class MP3File(AudioFile):
    def __init__(self, full_path):
        AudioFile.__init__(self, full_path)

    def read_id3(self):
        """ Read ID3 data from file. """
        id3 = load(self.full_path)
        if id3 is None:
            raise Exception('Could not load ID3 data for %s' % self.full_path)

        return id3

    def read_tags(self):
        """ Read relevant tags from ID3 data. """
        md = self.id3.tag
        frame_types = {frames.TextFrame, frames.CommentFrame, frames.UserTextFrame}
        track_frames = list(md.frameiter())
        tag_dict = {frame.id.decode('utf-8'): frame.text for frame in
                    filter(lambda t: type(t) in frame_types, track_frames)}.items()

        return defaultdict(str, {k: v for k, v in tag_dict if k in ALL_ID3_TAGS})
