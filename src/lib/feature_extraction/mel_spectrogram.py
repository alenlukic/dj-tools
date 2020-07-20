import base64
from collections import defaultdict
import json
import librosa
import numpy as np
import sklearn

from src.db import database
from src.db.entities.track import Track
from src.definitions.feature_extraction import *

np.set_printoptions(precision=3)


def create_mel_spectorgram_matrix(track_path, n_mels=N_MELS):
    # Load samples
    samples, _ = librosa.load(track_path, SAMPLE_RATE)
    n = len(samples)

    # Create overlapping windows
    windows = []
    for i in range(0, n, OVERLAP_WINDOW):
        end = i + OVERLAP_WINDOW + 1
        if end >= n:
            padding = end - n
            windows.append(np.concatenate((samples[i:n], np.zeros(padding)), axis=None))
        else:
            windows.append(samples[i:end])

    # Calculate Mel spectrogram for each overlapping window
    window_mels = [librosa.feature.melspectrogram(y=window, sr=SAMPLE_RATE, n_mels=n_mels) for window in windows]
    mel_chunks = np.array_split(window_mels, NUM_ROW_CHUNKS)

    # Calculate average Mel coefficient vector within each chunk
    mean_mel_spectrogram = []
    for mel_matrixes in mel_chunks:
        coeff_mean_vector = np.zeros(n_mels)

        for mel_matrix in mel_matrixes:
            for coeff_index, row in enumerate(mel_matrix):
                coeff_mean_vector[coeff_index] += np.mean(row)

        num_rows = float(len(mel_matrixes) * len(mel_matrixes[0]))
        mean_mel_spectrogram.append(np.vectorize(lambda m: m / num_rows)(coeff_mean_vector))

    print(mean_mel_spectrogram)
    print('Rows', len(mean_mel_spectrogram), 'Cols', len(mean_mel_spectrogram[0]))
    print('Num samples in original file', n)
    # print('Num mean matrixes', len(mean_mel_matrixes))
    # print('***\n')
    # for i, mean_matrix in enumerate(mean_mel_matrixes):
    #     print(i, 'Num rows', len(mean_matrix), 'Num cols', len(mean_matrix[0]))
    #     print('---')
