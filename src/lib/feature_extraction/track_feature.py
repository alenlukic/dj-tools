from os.path import exists, join
import json
import librosa
import numpy as np
from shutil import copyfile

from src.db.entities.feature_value import FeatureValue
from src.definitions.feature_extraction import *
from src.utils.feature_extraction import load_json_from_file


class TrackFeature:
    """ Encapsulates a track feature. """

    def __init__(self, track):
        """
        Constructor.

        :param track: The track for which to compute a feature.
        """

        self.track = track
        self.feature_file = join(FEATURE_DIR, str(track.id))
        self.feature_name = None
        self.feature_value = None
        self.preprocessed_value = None
        self.postprocessed_value = None
        self.track_features = {}

    def get_feature(self):
        """ Return the computed feature value. """
        if self.feature_value is None:
            self.save()
        return self.feature_value

    def preprocess(self, feature_value):
        """ Transform feature value prior to serialization. """
        return feature_value

    def postprocess(self, feature_value):
        """ Transform feature value after deserialization. """
        return feature_value

    def load(self):
        """ Load the track's features as a JSON and get the existing feature value, if any. """

        feature_json = load_json_from_file(self.feature_file)
        self.feature_value = feature_json.get(self.feature_name)
        if self.feature_value is None:
            self.compute()
        if self.feature_value is not None:
            self.feature_value = self.postprocess(self.feature_value)
        return feature_json

    def save(self):
        """ Save the track's features as a JSON and persist the computed feature value, if any. """
        self.track_features = self.load()
        if self.feature_value is None:
            return

        if exists(self.feature_file):
            copyfile(self.feature_file, join(FEATURE_DIR, '_old_' + str(self.track.id)))

        with open(self.feature_file, 'w') as fp:
            self.track_features[self.feature_name] = self.preprocess(self.feature_value)
            json.dump(self.track_features, fp)

    def compute(self):
        """ Compute feature value. """
        pass


class SegmentedMeanMelSpectrogram(TrackFeature):
    def __init__(self, track, db_session, n_mels=N_MELS):
        super().__init__(track)
        self.db_session = db_session
        self.feature_name = Feature.SMMS.value
        self.n_mels = n_mels

    def preprocess(self, feature_value):
        """ Transform feature value prior to serialization. """
        if self.preprocessed_value is None:
            self.preprocessed_value = [[np.format_float_scientific(v, precision=3) for v in r] for r in feature_value]
        return self.preprocessed_value

    def postprocess(self, feature_value):
        """ Transform feature value after deserialization. """
        if self.postprocessed_value is None:
            self.postprocessed_value = np.array([[float(v) for v in row] for row in feature_value])
        return self.postprocessed_value

    def compute(self):
        """ Compute the segmented mean Mel spectrogram. """

        # Load samples
        samples, _ = librosa.load(self.track.file_path, SAMPLE_RATE)
        n = len(samples)

        # Create overlapping windows
        windows = []
        for i in range(0, n, OVERLAP_WINDOW):
            end = i + WINDOW_SIZE + 1
            if end >= n:
                padding = end - n
                windows.append(np.concatenate((samples[i:n], np.zeros(padding)), axis=None))
            else:
                windows.append(samples[i:end])

        # Calculate Mel spectrogram for each overlapping window
        window_spectrograms = [librosa.feature.melspectrogram(y=w, sr=SAMPLE_RATE, n_mels=self.n_mels) for w in windows]
        spectrogram_chunks = np.array_split(window_spectrograms, NUM_ROW_CHUNKS)

        # Calculate mean Mel coefficient vector for each chunk
        mean_mel_spectrogram = []
        for spectrogram in spectrogram_chunks:
            mel_coeff_means = np.zeros(self.n_mels)

            for mel_coeffs in spectrogram:
                for coeff_index, coeff_row in enumerate(mel_coeffs):
                    mel_coeff_means[coeff_index] += np.mean(coeff_row)

            num_rows = float(len(spectrogram) * len(spectrogram[0]))
            mean_mel_spectrogram.append(np.vectorize(lambda m: m / num_rows)(mel_coeff_means))

        self.feature_value = mean_mel_spectrogram

    def save(self):
        super().save()
        fv_row = {
            'track_id': self.track.id,
            'features': {
                self.feature_name: self.preprocess(self.feature_value)
            }
        }
        self.db_session.guarded_add(FeatureValue(**fv_row))
