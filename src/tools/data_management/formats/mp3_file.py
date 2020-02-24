from collections import defaultdict

from eyed3 import load
from eyed3.id3 import frames

from src.definitions.data_management import ALL_ID3_TAGS, METADATA_KEY_TO_ID3, UNSUPPORTED_ID3_TAGS
from src.tools.data_management.formats.audio_file import AudioFile


class MP3File(AudioFile):
    def __init__(self, full_path):
        AudioFile.__init__(self, full_path)

    def read_id3(self):
        """ Read ID3 data from file. """

        id3 = load(self.full_path).tag
        if id3 is None:
            raise Exception('Could not load ID3 data for %s' % self.full_path)

        return id3

    def read_tags(self):
        """ Read relevant tags from ID3 data. """

        frame_types = {frames.TextFrame, frames.CommentFrame, frames.UserTextFrame}
        track_frames = list(self.id3.frameiter())
        tag_dict = {frame.id.decode('utf-8'): frame.text for frame in
                    filter(lambda t: type(t) in frame_types, track_frames)}.items()

        return defaultdict(str, {k: v for k, v in tag_dict if k in ALL_ID3_TAGS})

    def write_tag(self, tag, value, kwargs={}):
        """ Write specified ID3 to file. """
        frame = self._get_frame_with_metadata_key(tag, kwargs.get('track_frames') or [])
        if frame is not None:
            frame.text = value

    def write_tags(self):
        """ Writes metadata to ID3 tags and saves to file. """

        # Remove tags not supported by eyed3
        self._remove_unsupported_tags(self.id3.tag)

        track_frames = list(self.id3.tag.frameiter())
        track_metadata = self.get_metadata()
        for k, v in track_metadata.items():
            self.write_tag(k, v, {'track_frames': track_frames})

        self.id3.save()

    @staticmethod
    def _get_frame_with_metadata_key(metadata_key, track_frames):
        """
        Uses metadata key to retrieve corresponding ID3 frame, if available.

        :param metadata_key: The metadata key.
        :param track_frames: Track's ID3 frames.
        """

        tag = METADATA_KEY_TO_ID3.get(metadata_key)
        if tag is None:
            return None

        target_frame = list(filter(lambda frame: frame.id.decode('utf-8') == tag, track_frames))
        if len(target_frame) == 1:
            return target_frame[0]

        return None

    @staticmethod
    def _remove_unsupported_tags(md_tag):
        """
        Remove any tags not currently supported by eyed3.

        :param md_tag: Wrapper for a track's ID3 tags.
        """

        frame_set = md_tag.frame_set
        for k, tags in frame_set.items():
            for unsupported_tag in list(filter(
                    lambda frame: frame.id.decode('utf-8') in UNSUPPORTED_ID3_TAGS, tags)):
                tags.remove(unsupported_tag)
            dict.__setitem__(frame_set, k, tags)
