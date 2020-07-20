from os.path import join
import json
from shutil import copyfile

from src.definitions.feature_extraction import *
from src.utils.feature_extraction import load_json_from_file


class TrackFeature:
    def __init__(self, track):
        self.track = track
        self.feature_file = join(FEATURE_DIR, str(track.id))
        self.track_features = self.load()
        self.feature_name = None
        self.feature_value = None

    def get_feature(self):
        return self.feature_value

    def load(self):
        return load_json_from_file(self.feature_file)

    def save(self):
        copyfile(self.feature_file, join(FEATURE_DIR, str(self.track.id)) + '_old')
        with open(self.feature_file, 'w') as fp:
            self.track_features[self.feature_name] = self.feature_value
            json.dump(self.track_features, fp, indent=2)

    def compute(self):
        pass


class MelSpectrogram(TrackFeature):
    def __init__(self, track):
        super().__init__(track)
        self.track = track
        self.feature_name = 'Mel Spectrogram'
