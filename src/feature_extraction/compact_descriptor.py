import numpy as np
import librosa

from src.feature_extraction.config import (
    DESCRIPTOR_BPM_MIN,
    DESCRIPTOR_BPM_RANGE,
    DESCRIPTOR_DIMS,
    DESCRIPTOR_TEMPOGRAM_BINS,
    DESCRIPTOR_VERSION,
    DESCRIPTOR_ZONE_SECONDS,
    SAMPLE_RATE,
)
from src.utils.file_operations import get_track_load_path

# CQT needs at least 1 s of audio at the target sample rate; anything shorter
# is either corrupt data or a non-music file and should be skipped.
_MIN_AUDIO_SAMPLES = SAMPLE_RATE  # 1 second at 44 100 Hz


def _extract_zone_vector(y, sr):
    """Extract a 75-d compact descriptor from a segment of audio samples.

    Layout (75 dims total):
        [0:12]   beat-synchronous chroma_cqt mean  (harmonic)
        [12:24]  beat-synchronous chroma_cqt std   (harmonic)
        [24]     BPM scalar, normalized to [0, 1]  (rhythm)
        [25:41]  tempogram histogram, 16 bins       (rhythm)
        [41:54]  MFCC means, 13 coefficients        (timbre)
        [54:67]  MFCC stds,  13 coefficients        (timbre)
        [67]     RMS mean                           (energy)
        [68]     RMS std                            (energy)
        [69]     spectral centroid mean, normalized (brightness)
        [70]     spectral centroid std,  normalized (brightness)
        [71]     spectral rolloff mean,  normalized (brightness)
        [72]     spectral rolloff std,   normalized (brightness)
        [73]     zero-crossing rate mean            (energy)
        [74]     zero-crossing rate std             (energy)
    """
    if len(y) < _MIN_AUDIO_SAMPLES:
        raise ValueError(
            "Audio segment too short for feature extraction: %d samples "
            "(minimum %d, ~%.2f s)" % (len(y), _MIN_AUDIO_SAMPLES, _MIN_AUDIO_SAMPLES / SAMPLE_RATE)
        )
    # Harmonic-percussive source separation
    y_harm, y_perc = librosa.effects.hpss(y)

    # Beat tracking on percussive component
    tempo, beat_frames = librosa.beat.beat_track(y=y_perc, sr=sr)
    bpm = float(np.atleast_1d(tempo)[0])

    # Beat-synchronous chroma CQT on harmonic component
    chroma = librosa.feature.chroma_cqt(y=y_harm, sr=sr)
    if beat_frames is not None and len(beat_frames) > 0:
        chroma_sync = librosa.util.sync(chroma, beat_frames, aggregate=np.mean)
    else:
        chroma_sync = chroma
    chroma_mean = np.mean(chroma_sync, axis=1)   # (12,)
    chroma_std = np.std(chroma_sync, axis=1)     # (12,)

    # Tempogram: collapse to 16-bin histogram summary
    tempogram = librosa.feature.tempogram(y=y_perc, sr=sr)
    tempogram_row_means = np.mean(tempogram, axis=1)   # (n_tempo_bins,)
    n_bins = len(tempogram_row_means)
    group_size = max(n_bins // DESCRIPTOR_TEMPOGRAM_BINS, 1)
    tempogram_hist = np.array([
        np.mean(tempogram_row_means[i * group_size:(i + 1) * group_size])
        for i in range(DESCRIPTOR_TEMPOGRAM_BINS)
    ], dtype=np.float32)
    hist_sum = tempogram_hist.sum()
    if hist_sum > 0:
        tempogram_hist = tempogram_hist / hist_sum

    # BPM scalar normalized to [0, 1] over expected DJ range
    bpm_norm = float(np.clip((bpm - DESCRIPTOR_BPM_MIN) / DESCRIPTOR_BPM_RANGE, 0.0, 1.0))

    # MFCC on full signal
    mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
    mfcc_mean = np.mean(mfcc, axis=1)   # (13,)
    mfcc_std = np.std(mfcc, axis=1)     # (13,)

    # Energy / brightness features
    nyquist = sr / 2.0

    rms = librosa.feature.rms(y=y)[0]
    rms_mean = float(np.mean(rms))
    rms_std = float(np.std(rms))

    centroid = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
    centroid_mean = float(np.mean(centroid)) / nyquist
    centroid_std = float(np.std(centroid)) / nyquist

    rolloff = librosa.feature.spectral_rolloff(y=y, sr=sr)[0]
    rolloff_mean = float(np.mean(rolloff)) / nyquist
    rolloff_std = float(np.std(rolloff)) / nyquist

    zcr = librosa.feature.zero_crossing_rate(y=y)[0]
    zcr_mean = float(np.mean(zcr))
    zcr_std = float(np.std(zcr))

    descriptor = np.concatenate([
        chroma_mean,                                                          # 12
        chroma_std,                                                           # 12
        [bpm_norm],                                                           # 1
        tempogram_hist,                                                       # 16
        mfcc_mean,                                                            # 13
        mfcc_std,                                                             # 13
        [rms_mean, rms_std, centroid_mean, centroid_std,                      # 4
         rolloff_mean, rolloff_std, zcr_mean, zcr_std],                       # 4
    ])

    assert len(descriptor) == DESCRIPTOR_DIMS, (
        "Descriptor length mismatch: got %d, expected %d" % (len(descriptor), DESCRIPTOR_DIMS)
    )
    return descriptor.astype(np.float32)


def pack_vector(v):
    """Pack a float32 numpy array to raw bytes for BYTEA storage."""
    return v.astype(np.float32).tobytes()


def unpack_vector(b):
    """Unpack raw BYTEA bytes back to a float32 numpy array."""
    return np.frombuffer(b, dtype=np.float32).copy()


def cosine_similarity(v1, v2):
    """Return cosine similarity in [0, 1] between two descriptor vectors.

    Returns 0.0 if either vector is a zero vector.
    """
    norm1 = np.linalg.norm(v1)
    norm2 = np.linalg.norm(v2)
    if norm1 == 0.0 or norm2 == 0.0:
        return 0.0
    raw = float(np.dot(v1, v2) / (norm1 * norm2))
    # Clamp to [0, 1]: cosine can be negative for very dissimilar audio
    return max(0.0, raw)


def compute_similarity(vec_a, vec_b, scorer=None):
    """Compute similarity between two descriptor vectors using the named scorer.

    Parameters
    ----------
    vec_a, vec_b : np.ndarray
        75-D descriptor vectors.
    scorer : ScorerName or None
        Scorer to use. Defaults to ``ScorerName.LATE_FUSION_V1``.

    Returns
    -------
    float
        Similarity score (bounded, typically in [0, 1]).
    """
    from src.feature_extraction.track_similarity import (
        ScorerName,
        compute_similarity as _compute,
    )
    if scorer is None:
        scorer = ScorerName.LATE_FUSION_V1
    return _compute(vec_a, vec_b, scorer=scorer)


class CompactDescriptor:
    """Extracts and holds a compact 75-dim audio descriptor for a track.

    Produces three zone vectors:
      * global_vector  — whole track
      * intro_vector   — first DESCRIPTOR_ZONE_SECONDS seconds (None if track too short)
      * outro_vector   — last  DESCRIPTOR_ZONE_SECONDS seconds (None if track too short)
    """

    def __init__(self, track):
        self.track = track
        self.global_vector = None
        self.intro_vector = None
        self.outro_vector = None
        self.version = DESCRIPTOR_VERSION

    def compute(self, audio_path=None):
        if audio_path is None:
            audio_path = get_track_load_path(self.track)
        y, sr = librosa.load(audio_path, sr=SAMPLE_RATE, mono=True)

        self.global_vector = _extract_zone_vector(y, sr)

        zone_samples = int(DESCRIPTOR_ZONE_SECONDS * sr)
        if len(y) > zone_samples * 2:
            self.intro_vector = _extract_zone_vector(y[:zone_samples], sr)
            self.outro_vector = _extract_zone_vector(y[-zone_samples:], sr)

    def pack_global(self):
        return pack_vector(self.global_vector)

    def pack_intro(self):
        return pack_vector(self.intro_vector) if self.intro_vector is not None else None

    def pack_outro(self):
        return pack_vector(self.outro_vector) if self.outro_vector is not None else None
