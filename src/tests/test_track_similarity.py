"""Tests for src/feature_extraction/track_similarity.py

Run:
    python -m pytest src/tests/test_track_similarity.py -v
"""

import numpy as np
import pytest

from src.feature_extraction.config import DESCRIPTOR_DIMS
from src.feature_extraction.track_similarity import (
    BenchmarkHarness,
    ScorerName,
    _bpm_similarity,
    _best_circular_shift_sim,
    _centered_cosine,
    _dist_to_sim,
    _energy_similarity,
    _harmonic_similarity,
    _rhythm_similarity,
    _safe_cosine,
    _standardized_euclidean_distance,
    _tempogram_similarity,
    _timbre_similarity,
    _zscore_vectors,
    compute_similarity,
    correlation_or_centered_cosine,
    cosine_after_global_zscore,
    current_cosine_clamped,
    extract_blocks,
    get_scorer,
    late_fusion_v1,
    list_scorers,
    raw_cosine_uncapped,
    standardized_euclidean,
)
from src.feature_extraction.compact_descriptor import cosine_similarity


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _random_descriptor(seed=0):
    """Generate a realistic 75-D descriptor vector."""
    rng = np.random.default_rng(seed)
    chroma_mean = rng.uniform(0.0, 1.0, 12).astype(np.float32)
    chroma_std = rng.uniform(0.0, 0.3, 12).astype(np.float32)
    bpm = np.array([rng.uniform(0.0, 1.0)], dtype=np.float32)
    tempogram = rng.dirichlet(np.ones(16)).astype(np.float32)
    mfcc_mean = (rng.standard_normal(13) * 20).astype(np.float32)
    mfcc_std = np.abs(rng.standard_normal(13).astype(np.float32)) * 10
    energy = np.abs(rng.standard_normal(8).astype(np.float32)) * 0.3
    return np.concatenate([
        chroma_mean, chroma_std, bpm, tempogram,
        mfcc_mean, mfcc_std, energy,
    ])


def _zero_descriptor():
    return np.zeros(DESCRIPTOR_DIMS, dtype=np.float32)


def _ones_descriptor():
    return np.ones(DESCRIPTOR_DIMS, dtype=np.float32)


# ---------------------------------------------------------------------------
# 1. current_cosine_clamped preserves existing behavior
# ---------------------------------------------------------------------------

class TestCurrentCosineClamped:
    def test_matches_original_cosine_similarity(self):
        """current_cosine_clamped must produce the same result as the original."""
        for seed in range(20):
            va = _random_descriptor(seed)
            vb = _random_descriptor(seed + 100)
            assert current_cosine_clamped(va, vb) == pytest.approx(
                cosine_similarity(va, vb), abs=1e-7
            )

    def test_identical_vectors(self):
        v = _ones_descriptor()
        assert current_cosine_clamped(v, v) == pytest.approx(1.0, abs=1e-6)

    def test_opposite_clamped_to_zero(self):
        v = _ones_descriptor()
        assert current_cosine_clamped(v, -v) == 0.0

    def test_zero_vector_returns_zero(self):
        assert current_cosine_clamped(_ones_descriptor(), _zero_descriptor()) == 0.0

    def test_result_in_unit_range(self):
        for seed in range(20):
            va = _random_descriptor(seed)
            vb = _random_descriptor(seed + 50)
            sim = current_cosine_clamped(va, vb)
            assert 0.0 <= sim <= 1.0


# ---------------------------------------------------------------------------
# 2. raw_cosine_uncapped differs only for negative-valued cosines
# ---------------------------------------------------------------------------

class TestRawCosineUncapped:
    def test_agrees_when_positive(self):
        va = _ones_descriptor()
        vb = _ones_descriptor() * 0.5
        assert raw_cosine_uncapped(va, vb) == pytest.approx(
            current_cosine_clamped(va, vb), abs=1e-7
        )

    def test_can_be_negative(self):
        v = _ones_descriptor()
        assert raw_cosine_uncapped(v, -v) < 0.0

    def test_differs_from_clamped_when_negative(self):
        v = _ones_descriptor()
        raw = raw_cosine_uncapped(v, -v)
        clamped = current_cosine_clamped(v, -v)
        assert raw < 0.0
        assert clamped == 0.0


# ---------------------------------------------------------------------------
# 3. z-score helpers handle zero-variance dims safely
# ---------------------------------------------------------------------------

class TestZscoreHelpers:
    def test_zero_variance_dims_set_to_one(self):
        a = np.array([1.0, 1.0, 3.0])
        b = np.array([1.0, 1.0, 5.0])
        za, zb = _zscore_vectors(a, b)
        assert np.all(np.isfinite(za))
        assert np.all(np.isfinite(zb))

    def test_with_corpus_stats(self):
        a = np.array([2.0, 4.0])
        b = np.array([3.0, 5.0])
        mu = np.array([0.0, 0.0])
        sigma = np.array([2.0, 2.0])
        za, zb = _zscore_vectors(a, b, mu, sigma)
        np.testing.assert_allclose(za, [1.0, 2.0])
        np.testing.assert_allclose(zb, [1.5, 2.5])

    def test_all_constant_dims(self):
        a = np.ones(10)
        b = np.ones(10)
        za, zb = _zscore_vectors(a, b)
        assert np.all(np.isfinite(za))
        assert np.all(np.isfinite(zb))

    def test_standardized_euclidean_zero_variance(self):
        a = np.array([1.0, 2.0])
        b = np.array([3.0, 4.0])
        variance = np.array([0.0, 0.0])
        d = _standardized_euclidean_distance(a, b, variance)
        assert np.isfinite(d)

    def test_dist_to_sim_inf(self):
        assert _dist_to_sim(float("inf")) == 0.0

    def test_dist_to_sim_nan(self):
        assert _dist_to_sim(float("nan")) == 0.0

    def test_dist_to_sim_zero(self):
        assert _dist_to_sim(0.0) == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# 4. Harmonic scorer is invariant to chroma circular shifts
# ---------------------------------------------------------------------------

class TestHarmonicScorer:
    def test_shift_invariance_on_mean(self):
        """Shifting chroma_mean by any amount should not change similarity."""
        rng = np.random.default_rng(7)
        chroma = rng.uniform(0, 1, 12).astype(np.float32)
        for shift in range(12):
            shifted = np.roll(chroma, shift)
            sim = _best_circular_shift_sim(chroma, shifted)
            assert sim == pytest.approx(1.0, abs=0.05), (
                "shift %d gave sim %.4f" % (shift, sim)
            )

    def test_different_chroma_lower_sim(self):
        """Genuinely different spectral shapes should score lower than identical."""
        a = np.array([1.0, 0.5, 0.2, 0, 0, 0, 0, 0, 0, 0, 0, 0], dtype=np.float32)
        b = np.array([0, 0, 0, 0, 0, 0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0], dtype=np.float32)
        sim_same = _best_circular_shift_sim(a, a)
        sim_diff = _best_circular_shift_sim(a, b)
        assert sim_same > sim_diff

    def test_harmonic_similarity_symmetric(self):
        ba = extract_blocks(_random_descriptor(1))
        bb = extract_blocks(_random_descriptor(2))
        assert _harmonic_similarity(ba, bb) == pytest.approx(
            _harmonic_similarity(bb, ba), abs=1e-7
        )

    def test_harmonic_similarity_bounded(self):
        ba = extract_blocks(_random_descriptor(3))
        bb = extract_blocks(_random_descriptor(4))
        sim = _harmonic_similarity(ba, bb)
        assert -1.1 <= sim <= 1.1


# ---------------------------------------------------------------------------
# 5. Rhythm scorer: same/different BPM × same/different histogram
# ---------------------------------------------------------------------------

class TestRhythmScorer:
    def test_same_bpm_same_histogram(self):
        blocks = extract_blocks(_random_descriptor(10))
        sim = _rhythm_similarity(blocks, blocks)
        assert sim == pytest.approx(1.0, abs=0.05)

    def test_different_bpm_same_histogram(self):
        ba = extract_blocks(_random_descriptor(10))
        bb = extract_blocks(_random_descriptor(10))
        bb["bpm"] = np.array([0.1], dtype=np.float32)
        ba["bpm"] = np.array([0.9], dtype=np.float32)
        sim = _rhythm_similarity(ba, bb)
        assert sim < 0.95

    def test_same_bpm_different_histogram(self):
        ba = extract_blocks(_random_descriptor(10))
        bb = extract_blocks(_random_descriptor(11))
        ba["bpm"] = bb["bpm"].copy()
        sim = _rhythm_similarity(ba, bb)
        assert sim < 1.0

    def test_bpm_similarity_identical(self):
        assert _bpm_similarity(0.5, 0.5) == pytest.approx(1.0, abs=0.01)

    def test_bpm_similarity_large_diff(self):
        assert _bpm_similarity(0.1, 0.9) < 0.3

    def test_tempogram_similarity_identical(self):
        hist = np.array([0.1, 0.2, 0.3, 0.4] + [0.0] * 12, dtype=np.float32)
        assert _tempogram_similarity(hist, hist) == pytest.approx(1.0, abs=1e-6)

    def test_tempogram_similarity_zeros(self):
        z = np.zeros(16, dtype=np.float32)
        assert _tempogram_similarity(z, z) == 1.0


# ---------------------------------------------------------------------------
# 6. Timbre and energy scorers are symmetric and bounded
# ---------------------------------------------------------------------------

class TestTimbreEnergyScorers:
    def test_timbre_symmetric(self):
        ba = extract_blocks(_random_descriptor(20))
        bb = extract_blocks(_random_descriptor(21))
        assert _timbre_similarity(ba, bb) == pytest.approx(
            _timbre_similarity(bb, ba), abs=1e-7
        )

    def test_timbre_bounded(self):
        ba = extract_blocks(_random_descriptor(20))
        bb = extract_blocks(_random_descriptor(21))
        sim = _timbre_similarity(ba, bb)
        assert 0.0 <= sim <= 1.0

    def test_timbre_identical(self):
        ba = extract_blocks(_random_descriptor(20))
        assert _timbre_similarity(ba, ba) == pytest.approx(1.0, abs=1e-6)

    def test_energy_symmetric(self):
        ba = extract_blocks(_random_descriptor(30))
        bb = extract_blocks(_random_descriptor(31))
        assert _energy_similarity(ba, bb) == pytest.approx(
            _energy_similarity(bb, ba), abs=1e-7
        )

    def test_energy_bounded(self):
        ba = extract_blocks(_random_descriptor(30))
        bb = extract_blocks(_random_descriptor(31))
        sim = _energy_similarity(ba, bb)
        assert 0.0 <= sim <= 1.0

    def test_energy_identical(self):
        ba = extract_blocks(_random_descriptor(30))
        assert _energy_similarity(ba, ba) == pytest.approx(1.0, abs=1e-6)


# ---------------------------------------------------------------------------
# 7. Late-fusion score is finite, bounded, symmetric
# ---------------------------------------------------------------------------

class TestLateFusionV1:
    def test_finite(self):
        for seed in range(15):
            va = _random_descriptor(seed)
            vb = _random_descriptor(seed + 50)
            s = late_fusion_v1(va, vb)
            assert np.isfinite(s), "seed %d: not finite" % seed

    def test_bounded(self):
        for seed in range(15):
            va = _random_descriptor(seed)
            vb = _random_descriptor(seed + 50)
            s = late_fusion_v1(va, vb)
            assert 0.0 <= s <= 1.0, "seed %d: %.4f out of bounds" % (seed, s)

    def test_symmetric(self):
        for seed in range(10):
            va = _random_descriptor(seed)
            vb = _random_descriptor(seed + 50)
            assert late_fusion_v1(va, vb) == pytest.approx(
                late_fusion_v1(vb, va), abs=1e-7
            ), "seed %d: asymmetric" % seed

    def test_identical_vectors_high_score(self):
        v = _random_descriptor(0)
        assert late_fusion_v1(v, v) > 0.8

    def test_zero_vectors(self):
        z = _zero_descriptor()
        s = late_fusion_v1(z, z)
        assert np.isfinite(s)


# ---------------------------------------------------------------------------
# 8. Scorer registry routes correctly
# ---------------------------------------------------------------------------

class TestScorerRegistry:
    def test_all_scorers_registered(self):
        for name in ScorerName:
            fn = get_scorer(name)
            assert callable(fn)

    def test_list_scorers_returns_all(self):
        names = list_scorers()
        assert set(ScorerName) == set(names)

    def test_compute_similarity_routes(self):
        va = _random_descriptor(0)
        vb = _random_descriptor(1)
        for name in ScorerName:
            result = compute_similarity(va, vb, scorer=name)
            assert np.isfinite(result)

    def test_default_scorer_is_late_fusion(self):
        va = _random_descriptor(0)
        vb = _random_descriptor(1)
        default = compute_similarity(va, vb)
        explicit = compute_similarity(va, vb, scorer=ScorerName.LATE_FUSION_V1)
        assert default == pytest.approx(explicit, abs=1e-7)


# ---------------------------------------------------------------------------
# 9. Benchmark harness runs end-to-end on small fixture data
# ---------------------------------------------------------------------------

class TestBenchmarkHarness:
    def _fixture_vectors(self, n=10):
        return [_random_descriptor(seed=i) for i in range(n)]

    def test_runs_all_scorers(self):
        vecs = self._fixture_vectors()
        harness = BenchmarkHarness(vecs)
        results = harness.run_all()
        assert len(results) == len(list_scorers())

    def test_result_has_required_fields(self):
        vecs = self._fixture_vectors()
        harness = BenchmarkHarness(vecs)
        r = harness.run_scorer(ScorerName.CURRENT_COSINE_CLAMPED)
        assert "min" in r
        assert "max" in r
        assert "mean" in r
        assert "std" in r
        assert "percentiles" in r
        assert "hubness" in r
        assert "scorer" in r
        assert r["scorer"] == ScorerName.CURRENT_COSINE_CLAMPED.value

    def test_max_pairs_cap(self):
        vecs = self._fixture_vectors(20)
        harness = BenchmarkHarness(vecs, max_pairs=10)
        r = harness.run_scorer(ScorerName.LATE_FUSION_V1)
        assert r["num_pairs"] == 10

    def test_corpus_stats_computed(self):
        vecs = self._fixture_vectors()
        harness = BenchmarkHarness(vecs)
        stats = harness.corpus_stats()
        assert "corpus_mean" in stats
        assert "corpus_std" in stats
        assert "corpus_variance" in stats
        assert "timbre_variance" in stats
        assert "energy_variance" in stats
        assert stats["corpus_mean"].shape == (DESCRIPTOR_DIMS,)

    def test_hubness_fields_present(self):
        vecs = self._fixture_vectors()
        harness = BenchmarkHarness(vecs)
        r = harness.run_scorer(ScorerName.LATE_FUSION_V1)
        hub = r["hubness"]
        assert "top_k" in hub
        assert "max_hub_occurrence" in hub
        assert "fraction_never_in_topk" in hub

    def test_single_pair(self):
        vecs = self._fixture_vectors(2)
        harness = BenchmarkHarness(vecs)
        r = harness.run_scorer(ScorerName.LATE_FUSION_V1)
        assert r["num_pairs"] == 1


# ---------------------------------------------------------------------------
# extract_blocks sanity
# ---------------------------------------------------------------------------

class TestExtractBlocks:
    def test_block_shapes(self):
        v = _random_descriptor(0)
        blocks = extract_blocks(v)
        assert blocks["chroma_mean"].shape == (12,)
        assert blocks["chroma_std"].shape == (12,)
        assert blocks["bpm"].shape == (1,)
        assert blocks["tempogram"].shape == (16,)
        assert blocks["mfcc_mean"].shape == (13,)
        assert blocks["mfcc_std"].shape == (13,)
        assert blocks["energy_brightness"].shape == (8,)

    def test_blocks_cover_full_vector(self):
        v = _random_descriptor(0)
        blocks = extract_blocks(v)
        total = sum(b.size for b in blocks.values())
        assert total == DESCRIPTOR_DIMS
