"""Unit tests for src/lib/feature_extraction/compact_descriptor.py

Run with:
    python -m pytest src/tests/test_compact_descriptor.py -v
"""

import numpy as np
import pytest

from src.feature_extraction.config import DESCRIPTOR_DIMS, SAMPLE_RATE
from src.feature_extraction.compact_descriptor import (
    CompactDescriptor,
    _MIN_AUDIO_SAMPLES,
    _extract_zone_vector,
    cosine_similarity,
    pack_vector,
    unpack_vector,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _sine_wave(duration_s=5.0, freq_hz=440.0, sr=SAMPLE_RATE):
    """Return a float32 mono sine wave."""
    t = np.linspace(0, duration_s, int(sr * duration_s), endpoint=False)
    return np.sin(2 * np.pi * freq_hz * t).astype(np.float32), sr


def _pink_noise(duration_s=5.0, sr=SAMPLE_RATE, rng_seed=42):
    """Return float32 mono pink-ish noise (white filtered to 1/f)."""
    rng = np.random.default_rng(rng_seed)
    white = rng.standard_normal(int(sr * duration_s)).astype(np.float32)
    # lightweight 1/f approximation via cumsum of white noise
    pink = np.cumsum(white)
    pink -= pink.mean()
    peak = np.abs(pink).max()
    return (pink / peak if peak > 0 else pink), sr


# ---------------------------------------------------------------------------
# _extract_zone_vector
# ---------------------------------------------------------------------------

class TestExtractZoneVector:
    def test_output_shape_and_dtype(self):
        y, sr = _sine_wave()
        vec = _extract_zone_vector(y, sr)
        assert vec.shape == (DESCRIPTOR_DIMS,), f"expected ({DESCRIPTOR_DIMS},), got {vec.shape}"
        assert vec.dtype == np.float32

    def test_output_shape_noise(self):
        y, sr = _pink_noise()
        vec = _extract_zone_vector(y, sr)
        assert vec.shape == (DESCRIPTOR_DIMS,)
        assert vec.dtype == np.float32

    def test_no_nans_or_infs(self):
        y, sr = _sine_wave()
        vec = _extract_zone_vector(y, sr)
        assert not np.any(np.isnan(vec)), "descriptor contains NaN"
        assert not np.any(np.isinf(vec)), "descriptor contains Inf"

    def test_short_audio_raises(self):
        sr = SAMPLE_RATE
        too_short = np.zeros(_MIN_AUDIO_SAMPLES - 1, dtype=np.float32)
        with pytest.raises(ValueError, match="too short"):
            _extract_zone_vector(too_short, sr)

    def test_minimum_length_accepted(self):
        sr = SAMPLE_RATE
        at_limit = np.random.default_rng(0).standard_normal(_MIN_AUDIO_SAMPLES).astype(np.float32)
        vec = _extract_zone_vector(at_limit, sr)
        assert vec.shape == (DESCRIPTOR_DIMS,)

    def test_chroma_range(self):
        """chroma_cqt outputs are in [0, 1]; beat-sync mean/std should stay bounded."""
        y, sr = _sine_wave()
        vec = _extract_zone_vector(y, sr)
        chroma_mean = vec[0:12]
        chroma_std = vec[12:24]
        assert chroma_mean.min() >= -1e-6, "chroma mean below 0"
        assert chroma_mean.max() <= 1.0 + 1e-6, "chroma mean above 1"
        assert (chroma_std >= 0).all(), "chroma std negative"

    def test_bpm_normalized(self):
        """BPM dim should be clamped to [0, 1]."""
        y, sr = _sine_wave()
        vec = _extract_zone_vector(y, sr)
        bpm_dim = float(vec[24])
        assert 0.0 <= bpm_dim <= 1.0, f"BPM dim out of range: {bpm_dim}"

    def test_tempogram_sums_to_one_or_zero(self):
        """Normalised tempogram histogram must sum to 1 (or 0 if silent)."""
        y, sr = _sine_wave()
        vec = _extract_zone_vector(y, sr)
        hist = vec[25:41]
        hist_sum = hist.sum()
        assert abs(hist_sum - 1.0) < 1e-4 or hist_sum == 0.0, (
            f"tempogram histogram sum {hist_sum:.6f} not close to 1"
        )

    def test_deterministic(self):
        """Same audio produces identical descriptors."""
        y, sr = _sine_wave()
        v1 = _extract_zone_vector(y, sr)
        v2 = _extract_zone_vector(y, sr)
        np.testing.assert_array_equal(v1, v2)

    def test_different_audio_different_descriptor(self):
        y1, sr = _sine_wave(freq_hz=440.0)
        y2, sr = _sine_wave(freq_hz=880.0)
        v1 = _extract_zone_vector(y1, sr)
        v2 = _extract_zone_vector(y2, sr)
        assert not np.allclose(v1, v2), "440 Hz and 880 Hz produced identical descriptors"


# ---------------------------------------------------------------------------
# pack_vector / unpack_vector
# ---------------------------------------------------------------------------

class TestPackUnpack:
    def test_roundtrip_exact(self):
        rng = np.random.default_rng(7)
        original = rng.standard_normal(DESCRIPTOR_DIMS).astype(np.float32)
        packed = pack_vector(original)
        recovered = unpack_vector(packed)
        np.testing.assert_array_equal(original, recovered)

    def test_packed_size(self):
        vec = np.zeros(DESCRIPTOR_DIMS, dtype=np.float32)
        packed = pack_vector(vec)
        assert len(packed) == DESCRIPTOR_DIMS * 4, (
            f"expected {DESCRIPTOR_DIMS * 4} bytes, got {len(packed)}"
        )

    def test_unpack_is_writable(self):
        """unpack_vector must return a writable array (not a memoryview slice)."""
        vec = np.ones(DESCRIPTOR_DIMS, dtype=np.float32)
        recovered = unpack_vector(pack_vector(vec))
        recovered[0] = 99.0  # should not raise


# ---------------------------------------------------------------------------
# cosine_similarity
# ---------------------------------------------------------------------------

class TestCosineSimilarity:
    def test_identical_vectors(self):
        v = np.ones(DESCRIPTOR_DIMS, dtype=np.float32)
        assert cosine_similarity(v, v) == pytest.approx(1.0, abs=1e-6)

    def test_opposite_vectors_clamped(self):
        v = np.ones(DESCRIPTOR_DIMS, dtype=np.float32)
        assert cosine_similarity(v, -v) == 0.0

    def test_orthogonal_vectors(self):
        v1 = np.zeros(DESCRIPTOR_DIMS, dtype=np.float32)
        v1[0] = 1.0
        v2 = np.zeros(DESCRIPTOR_DIMS, dtype=np.float32)
        v2[1] = 1.0
        assert cosine_similarity(v1, v2) == pytest.approx(0.0, abs=1e-6)

    def test_zero_vector_returns_zero(self):
        v = np.ones(DESCRIPTOR_DIMS, dtype=np.float32)
        z = np.zeros(DESCRIPTOR_DIMS, dtype=np.float32)
        assert cosine_similarity(v, z) == 0.0
        assert cosine_similarity(z, v) == 0.0

    def test_result_in_unit_range(self):
        rng = np.random.default_rng(99)
        for _ in range(20):
            v1 = rng.standard_normal(DESCRIPTOR_DIMS).astype(np.float32)
            v2 = rng.standard_normal(DESCRIPTOR_DIMS).astype(np.float32)
            sim = cosine_similarity(v1, v2)
            assert 0.0 <= sim <= 1.0, f"similarity {sim} outside [0,1]"


# ---------------------------------------------------------------------------
# CompactDescriptor (end-to-end with synthetic audio)
# ---------------------------------------------------------------------------

class TestCompactDescriptor:
    def test_compute_sets_global_vector(self, tmp_path):
        """CompactDescriptor.compute() populates global_vector when given a valid path."""
        import soundfile as sf

        y, sr = _sine_wave(duration_s=10.0)
        audio_file = tmp_path / "test_track.wav"
        sf.write(str(audio_file), y, sr)

        class _FakeTrack:
            id = 0
            file_name = "test_track.wav"

        desc = CompactDescriptor(_FakeTrack())
        desc.compute(audio_path=str(audio_file))

        assert desc.global_vector is not None
        assert desc.global_vector.shape == (DESCRIPTOR_DIMS,)
        assert desc.global_vector.dtype == np.float32

    def test_short_track_skips_intro_outro(self, tmp_path):
        """Tracks shorter than 2 × DESCRIPTOR_ZONE_SECONDS get no intro/outro vectors."""
        import soundfile as sf

        y, sr = _sine_wave(duration_s=10.0)
        audio_file = tmp_path / "short_track.wav"
        sf.write(str(audio_file), y, sr)

        class _FakeTrack:
            id = 1
            file_name = "short_track.wav"

        desc = CompactDescriptor(_FakeTrack())
        desc.compute(audio_path=str(audio_file))

        assert desc.intro_vector is None
        assert desc.outro_vector is None

    def test_long_track_produces_intro_outro(self, tmp_path):
        """Tracks longer than 2 × DESCRIPTOR_ZONE_SECONDS get intro and outro vectors."""
        import soundfile as sf
        from src.feature_extraction.config import DESCRIPTOR_ZONE_SECONDS

        duration = DESCRIPTOR_ZONE_SECONDS * 2 + 10  # just over the threshold
        y, sr = _sine_wave(duration_s=float(duration))
        audio_file = tmp_path / "long_track.wav"
        sf.write(str(audio_file), y, sr)

        class _FakeTrack:
            id = 2
            file_name = "long_track.wav"

        desc = CompactDescriptor(_FakeTrack())
        desc.compute(audio_path=str(audio_file))

        assert desc.intro_vector is not None
        assert desc.outro_vector is not None
        assert desc.intro_vector.shape == (DESCRIPTOR_DIMS,)
        assert desc.outro_vector.shape == (DESCRIPTOR_DIMS,)

    def test_pack_methods_return_bytes(self, tmp_path):
        import soundfile as sf

        y, sr = _sine_wave(duration_s=10.0)
        audio_file = tmp_path / "pack_test.wav"
        sf.write(str(audio_file), y, sr)

        class _FakeTrack:
            id = 3
            file_name = "pack_test.wav"

        desc = CompactDescriptor(_FakeTrack())
        desc.compute(audio_path=str(audio_file))

        assert isinstance(desc.pack_global(), bytes)
        assert len(desc.pack_global()) == DESCRIPTOR_DIMS * 4
        assert desc.pack_intro() is None
        assert desc.pack_outro() is None
