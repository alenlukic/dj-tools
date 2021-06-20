import librosa
import numpy as np

from src.db.entities.feature_value import FeatureValue
from src.definitions.feature_extraction import *
from src.utils.file_operations import get_track_load_target


class TrackFeature:
    """ Encapsulates a track feature. """

    def __init__(self, track, feature_name):
        self.track = track
        self.feature_name = feature_name
        self.feature_value = None
        self.preprocessed_value = None
        self.postprocessed_value = None

    def get_feature(self, compute=False):
        if self.feature_value is None and compute:
            self.compute()

        return self.feature_value

    def preprocess(self, feature_value):
        return feature_value

    def postprocess(self, feature_value):
        return feature_value

    def load(self, db_session):
        track_features = db_session.query(FeatureValue).filter_by(track_id=self.track.id).first()
        if track_features is not None:
            self.feature_value = self.postprocess(track_features.features.get(self.feature_name))

    def compute(self):
        pass


class SegmentedMeanMelSpectrogram(TrackFeature):
    def __init__(self, track, n_mels=N_MELS):
        super().__init__(track, Feature.SMMS.value)
        self.n_mels = n_mels

    def preprocess(self, feature_value):
        if feature_value is None:
            return None

        if self.preprocessed_value is None:
            self.preprocessed_value = [[np.format_float_scientific(v, precision=3) for v in r] for r in feature_value]

        return self.preprocessed_value

    def postprocess(self, feature_value):
        if feature_value is None:
            return None

        if self.postprocessed_value is None:
            self.postprocessed_value = np.array([[float(v) for v in row] for row in feature_value])

        return self.postprocessed_value

    # Compute segmented mean Mel spectrogram
    def compute(self):
        target_path = get_track_load_target(self.track)
        samples, _ = librosa.load(target_path, SAMPLE_RATE)
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
