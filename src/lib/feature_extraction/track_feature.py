from os.path import join
import json
import librosa
import numpy as np
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

    def load(self, postprocessor=lambda x: x):
        feature_json = load_json_from_file(self.feature_file)
        self.feature_value = postprocessor(feature_json.get(self.feature_name))
        return feature_json

    def save(self, preprocessor=lambda x: x):
        copyfile(self.feature_file, join(FEATURE_DIR, str(self.track.id)) + '_old')
        with open(self.feature_file, 'w') as fp:
            self.track_features[self.feature_name] = preprocessor(self.feature_value)
            json.dump(self.track_features, fp, indent=2)

    def compute(self):
        pass


class SegmentedMeanMelSpectrogram(TrackFeature):
    def __init__(self, track, n_mels=N_MELS):
        super().__init__(track)
        self.track = track
        self.feature_name = 'Segmented Mean Mel Spectrogram'
        self.n_mels = n_mels

    def load(self, postprocessor=lambda x: np.array(x)):
        return super().load(postprocessor)

    def save(self, preprocessor=lambda x: x.tolist()):
        super().save(preprocessor)

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
