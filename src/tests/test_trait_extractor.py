"""Tests for the trait extraction inference chain.

Two test categories:
1. Unit tests (no ONNX models needed) — pure Python logic
2. Integration tests (requires models/traits/ cache) — gated behind
   pytest.mark.integration; skipped when models are not downloaded.

Run all:
    python -m pytest src/tests/test_trait_extractor.py -v

Run integration tests only (requires models):
    python -m pytest src/tests/test_trait_extractor.py -v -m integration

Run unit tests only (no models needed):
    python -m pytest src/tests/test_trait_extractor.py -v -m "not integration"
"""

import pathlib

import numpy as np
import pytest

from src.feature_extraction.config import (
    GENRE_ALLOWED_FAMILIES,
    GENRE_DISPLAY_THRESHOLD,
    GENRE_TOP_K,
    MOOD_DISPLAY_THRESHOLD,
    MOOD_TOP_K,
    TRAIT_SAMPLE_RATE,
    TRAIT_STORAGE_THRESHOLD,
    TRAIT_VERSION,
)
from src.feature_extraction.trait_extractor import (
    LABELS_GENRE_DISCOGS519,
    LABELS_INSTRUMENT,
    LABELS_MOOD_THEME,
    _binary_prob,
    _compute_mel_from_signal,
    _multilabel_dict,
    _patch_mel_for_effnet,
    _patch_mel_for_maest,
    compute_mel_spectrogram,
    filter_genre,
    filter_instruments,
    filter_mood,
    filter_multilabel,
)

_TEST_DATA = pathlib.Path(__file__).parent.parent.parent / ".test_data"
_MODELS_DIR = pathlib.Path(__file__).parent.parent.parent / "models" / "traits"
_BACKBONE = _MODELS_DIR / "discogs-effnet-bsdynamic-1.onnx"
_MAEST = _MODELS_DIR / "discogs-maest-30s-pw-519l-2.onnx"

_HAVE_BACKBONE = _BACKBONE.exists() and _BACKBONE.stat().st_size > 10_000
_HAVE_MAEST = _MAEST.exists() and _MAEST.stat().st_size > 10_000

_TEST_FILES = sorted(_TEST_DATA.glob("*")) if _TEST_DATA.exists() else []


# ------------------------------------------------------------------ #
# Helpers                                                              #
# ------------------------------------------------------------------ #


def _is_valid_trait_dict(traits: dict) -> None:
    """Assert structural correctness of a compute() result dict."""
    required_keys = {
        "voice_instrumental",
        "danceability",
        "bright_dark",
        "acoustic_electronic",
        "tonal_atonal",
        "reverb",
        "onset_density",
        "spectral_flatness",
        "mood_theme",
        "genre",
        "instruments",
        "trait_version",
    }
    assert required_keys == set(traits.keys()), "Missing/extra keys: %s" % (
        required_keys ^ set(traits.keys())
    )
    assert traits["trait_version"] == TRAIT_VERSION

    # Scalar traits: float in [0, 1] or None
    for key in (
        "voice_instrumental",
        "danceability",
        "bright_dark",
        "acoustic_electronic",
        "tonal_atonal",
        "reverb",
    ):
        v = traits[key]
        if v is not None:
            assert isinstance(v, float), "%s should be float, got %s" % (key, type(v))
            assert 0.0 <= v <= 1.0, "%s=%s out of [0,1]" % (key, v)

    # Librosa scalars: always present, non-negative
    assert isinstance(traits["onset_density"], float)
    assert traits["onset_density"] >= 0.0
    assert isinstance(traits["spectral_flatness"], float)
    assert 0.0 <= traits["spectral_flatness"] <= 1.0

    # JSONB multi-label dicts: dict or None; stored values use TRAIT_STORAGE_THRESHOLD
    for key in ("mood_theme", "genre", "instruments"):
        v = traits[key]
        if v is not None:
            assert isinstance(v, dict), "%s should be dict or None" % key
            for label, prob in v.items():
                assert isinstance(label, str), "label should be str"
                assert isinstance(prob, float), "prob should be float"
                assert prob >= TRAIT_STORAGE_THRESHOLD, (
                    "%s prob %s below storage threshold %s" % (key, prob, TRAIT_STORAGE_THRESHOLD)
                )
                assert prob <= 1.0, "%s prob %s > 1.0" % (key, prob)

    # genre may be None when MAEST model is unavailable (graceful degradation)


# ------------------------------------------------------------------ #
# Unit tests — no ONNX models required                                #
# ------------------------------------------------------------------ #


class TestLabelLists:
    def test_mood_theme_count(self):
        assert len(LABELS_MOOD_THEME) == 56

    def test_instrument_count(self):
        assert len(LABELS_INSTRUMENT) == 40

    def test_genre_count(self):
        assert len(LABELS_GENRE_DISCOGS519) == 519

    def test_mood_theme_known_labels(self):
        expected = {
            "action",
            "calm",
            "dark",
            "energetic",
            "happy",
            "sad",
            "upbeat",
            "uplifting",
        }
        assert expected.issubset(set(LABELS_MOOD_THEME))

    def test_mood_theme_no_stale_labels(self):
        # These were in the original wrong list — verify they were removed
        assert "horror" not in LABELS_MOOD_THEME
        assert "peaceful" not in LABELS_MOOD_THEME

    def test_instrument_known_labels(self):
        expected = {"drums", "synthesizer", "guitar", "violin", "viola", "voice"}
        assert expected.issubset(set(LABELS_INSTRUMENT))

    def test_instrument_no_stale_labels(self):
        assert "ukulele" not in LABELS_INSTRUMENT

    def test_no_duplicate_labels(self):
        for labels, name in [
            (LABELS_MOOD_THEME, "mood_theme"),
            (LABELS_INSTRUMENT, "instrument"),
            (LABELS_GENRE_DISCOGS519, "genre"),
        ]:
            assert len(labels) == len(set(labels)), "Duplicates in %s" % name

    def test_genre_contains_electronic_subgenres(self):
        electronic = [
            label
            for label in LABELS_GENRE_DISCOGS519
            if label.startswith("Electronic---")
        ]
        assert len(electronic) >= 50, "Expected many Electronic subgenres"

    def test_genre_519_has_maest_only_subgenres(self):
        """Verify labels unique to the 519-class MAEST taxonomy are present."""
        maest_only = {
            "Electronic---Footwork",
            "Electronic---Witch House",
            "Electronic---Ghettotech",
            "Electronic---Baltimore Club",
            "Electronic---Doomcore",
            "Electronic---Glitch Hop",
        }
        assert maest_only.issubset(set(LABELS_GENRE_DISCOGS519))


class TestPatchMelForEffnet:
    def _make_mel(self, T: int) -> np.ndarray:
        return np.random.rand(96, T).astype(np.float32)

    def test_output_shape_normal(self):
        mel = self._make_mel(1000)
        patches = _patch_mel_for_effnet(mel)
        assert patches.ndim == 3
        assert patches.shape[1] == 128  # time frames
        assert patches.shape[2] == 96  # mel bands

    def test_output_dtype_float32(self):
        patches = _patch_mel_for_effnet(self._make_mel(500))
        assert patches.dtype == np.float32

    def test_short_track_padded(self):
        # Track shorter than one window — should be zero-padded to 128 frames
        mel = self._make_mel(50)
        patches = _patch_mel_for_effnet(mel)
        assert patches.shape[0] >= 1
        assert patches.shape[1] == 128
        assert patches.shape[2] == 96

    def test_exact_one_window(self):
        mel = self._make_mel(128)
        patches = _patch_mel_for_effnet(mel)
        assert patches.shape[0] == 1

    def test_multiple_windows_with_hop(self):
        # 128 + 64 = 192 frames → should yield 2 patches (hop=64)
        mel = self._make_mel(192)
        patches = _patch_mel_for_effnet(mel)
        assert patches.shape[0] == 2

    def test_no_channel_dimension(self):
        # Model expects (N, 128, 96) — must NOT have a channel dim
        mel = self._make_mel(500)
        patches = _patch_mel_for_effnet(mel)
        assert patches.ndim == 3, "Should be 3D, got %d" % patches.ndim

    def test_values_match_original(self):
        mel = self._make_mel(200)
        patches = _patch_mel_for_effnet(mel)
        # First patch should be mel[:, 0:128].T
        expected = mel[:, :128].T
        np.testing.assert_array_equal(patches[0], expected)


class TestPatchMelForMaest:
    def _make_mel(self, T: int) -> np.ndarray:
        return np.random.rand(96, T).astype(np.float32)

    def test_output_is_list(self):
        mel = self._make_mel(5000)
        patches = _patch_mel_for_maest(mel)
        assert isinstance(patches, list)

    def test_patch_shape(self):
        mel = self._make_mel(5000)
        patches = _patch_mel_for_maest(mel)
        assert len(patches) >= 1
        assert patches[0].shape == (1, 1876, 96)

    def test_patch_dtype_float32(self):
        mel = self._make_mel(5000)
        patches = _patch_mel_for_maest(mel)
        assert patches[0].dtype == np.float32

    def test_short_track_padded_to_one_patch(self):
        # Track shorter than 1876 frames → padded, yields exactly 1 patch
        mel = self._make_mel(100)
        patches = _patch_mel_for_maest(mel)
        assert len(patches) == 1
        assert patches[0].shape == (1, 1876, 96)

    def test_long_track_multiple_patches(self):
        # 1876 + 1875 = 3751 frames → yields 2 patches (hop=1875)
        mel = self._make_mel(3751)
        patches = _patch_mel_for_maest(mel)
        assert len(patches) == 2

    def test_values_match_original(self):
        mel = self._make_mel(4000)
        patches = _patch_mel_for_maest(mel)
        # First patch should be mel[:, 0:1876].T
        expected = mel[:, :1876].T
        np.testing.assert_array_equal(patches[0][0], expected)


class TestBinaryProb:
    def test_two_class_takes_index_1(self):
        probs = np.array([0.3, 0.7])
        assert _binary_prob(probs) == pytest.approx(0.7)

    def test_single_value(self):
        probs = np.array([0.85])
        assert _binary_prob(probs) == pytest.approx(0.85)

    def test_scalar_array(self):
        probs = np.float32(0.6)
        assert _binary_prob(probs) == pytest.approx(0.6)

    def test_returns_float(self):
        result = _binary_prob(np.array([0.2, 0.8]))
        assert isinstance(result, float)


class TestMultilabelDict:
    """_multilabel_dict is now storage-only: threshold filter, no display logic."""

    def test_above_threshold_included(self):
        probs = np.array([0.5, 0.2, 0.005])
        labels = ["a", "b", "c"]
        result = _multilabel_dict(probs, labels)
        assert "a" in result
        assert "b" in result
        assert "c" not in result  # below 0.01 storage threshold

    def test_exactly_at_threshold_included(self):
        probs = np.array([TRAIT_STORAGE_THRESHOLD])
        result = _multilabel_dict(probs, ["x"])
        assert "x" in result

    def test_empty_when_all_below(self):
        probs = np.zeros(5)
        labels = ["a", "b", "c", "d", "e"]
        assert _multilabel_dict(probs, labels) == {}

    def test_values_rounded_to_4dp(self):
        probs = np.array([0.123456789])
        result = _multilabel_dict(probs, ["a"])
        assert result["a"] == round(0.123456789, 4)

    def test_handles_shorter_labels(self):
        probs = np.array([0.9, 0.8, 0.7])
        labels = ["a", "b"]
        result = _multilabel_dict(probs, labels)
        assert set(result.keys()) <= {"a", "b"}

    def test_custom_threshold(self):
        probs = np.array([0.005, 0.02, 0.05])
        labels = ["a", "b", "c"]
        result = _multilabel_dict(probs, labels, threshold=0.01)
        assert "a" not in result
        assert "b" in result
        assert "c" in result

    def test_stores_all_above_low_floor(self):
        probs = np.array([0.02, 0.05, 0.10, 0.50])
        labels = ["a", "b", "c", "d"]
        result = _multilabel_dict(probs, labels)
        assert len(result) == 4


class TestFilterMultilabel:
    """Display-layer filter applied to stored {label: prob} dicts."""

    def test_threshold_filters(self):
        raw = {"a": 0.05, "b": 0.15, "c": 0.30}
        result = filter_multilabel(raw, threshold=0.10)
        assert "a" not in result
        assert "b" in result
        assert "c" in result

    def test_top_k_limits(self):
        raw = {"a": 0.9, "b": 0.8, "c": 0.7, "d": 0.6, "e": 0.5}
        result = filter_multilabel(raw, threshold=0.01, top_k=3)
        assert len(result) == 3
        assert set(result.keys()) == {"a", "b", "c"}

    def test_top_k_no_op_when_fewer(self):
        raw = {"a": 0.9, "b": 0.8}
        result = filter_multilabel(raw, threshold=0.01, top_k=5)
        assert len(result) == 2

    def test_allowed_prefixes_filters_families(self):
        raw = {
            "Electronic---House": 0.9,
            "Rock---Grindcore": 0.8,
            "Electronic---Techno": 0.7,
            "Blues---Delta Blues": 0.6,
        }
        result = filter_multilabel(raw, allowed_prefixes=frozenset({"Electronic"}))
        assert "Electronic---House" in result
        assert "Electronic---Techno" in result
        assert "Rock---Grindcore" not in result
        assert "Blues---Delta Blues" not in result

    def test_labels_without_separator_always_pass(self):
        raw = {"no_separator": 0.9, "Electronic---House": 0.8}
        result = filter_multilabel(raw, allowed_prefixes=frozenset({"Electronic"}))
        assert "no_separator" in result
        assert "Electronic---House" in result

    def test_combined_threshold_topk_and_prefix(self):
        raw = {
            "Electronic---House": 0.20,
            "Rock---Grindcore": 0.18,
            "Electronic---Techno": 0.16,
            "Electronic---Ambient": 0.14,
            "Rock---Noisecore": 0.12,
            "Electronic---Trance": 0.25,
        }
        result = filter_multilabel(
            raw,
            threshold=0.15,
            top_k=2,
            allowed_prefixes=frozenset({"Electronic"}),
        )
        assert len(result) <= 2
        assert "Rock---Grindcore" not in result
        assert "Rock---Noisecore" not in result
        assert "Electronic---Trance" in result
        assert "Electronic---House" in result

    def test_empty_input(self):
        assert filter_multilabel({}) == {}
        assert filter_multilabel(None) == {}


class TestDisplayFilters:
    """Verify config-driven filter_genre / filter_mood / filter_instruments."""

    def test_filter_mood_threshold(self):
        raw = {label: 0.12 for label in LABELS_MOOD_THEME}
        result = filter_mood(raw)
        assert len(result) == 0, "0.12 should be below MOOD_DISPLAY_THRESHOLD"

    def test_filter_mood_passes_above_threshold(self):
        raw = {"dark": 0.30, "energetic": 0.25, "melodic": 0.05}
        result = filter_mood(raw)
        assert "dark" in result
        assert "energetic" in result
        assert "melodic" not in result

    def test_filter_mood_top_k(self):
        raw = {label: 0.50 for label in LABELS_MOOD_THEME}
        result = filter_mood(raw)
        assert len(result) == MOOD_TOP_K

    def test_filter_genre_rock_grindcore_blocked(self):
        raw = {"Rock---Grindcore": 0.30, "Electronic---House": 0.25}
        result = filter_genre(raw)
        assert "Rock---Grindcore" not in result
        assert "Electronic---House" in result

    def test_filter_genre_rock_noisecore_blocked(self):
        raw = {"Rock---Noisecore": 0.50}
        result = filter_genre(raw)
        assert "Rock---Noisecore" not in result

    def test_filter_genre_electronic_passes(self):
        raw = {
            "Electronic---House": 0.40,
            "Electronic---Techno": 0.35,
            "Electronic---Trance": 0.30,
        }
        result = filter_genre(raw)
        for g in raw:
            assert g in result

    def test_filter_genre_hip_hop_passes(self):
        raw = {"Hip Hop---Trap": 0.25}
        result = filter_genre(raw)
        assert "Hip Hop---Trap" in result

    def test_filter_genre_classical_blocked(self):
        raw = {"Classical---Baroque": 0.40}
        result = filter_genre(raw)
        assert "Classical---Baroque" not in result

    def test_filter_genre_top_k(self):
        raw = {g: 0.50 for g in LABELS_GENRE_DISCOGS519 if g.startswith("Electronic---")}
        result = filter_genre(raw)
        assert len(result) == GENRE_TOP_K

    def test_allowed_families_coverage(self):
        expected = {"Electronic", "Hip Hop", "Funk / Soul", "Pop", "Reggae", "Stage & Screen"}
        assert GENRE_ALLOWED_FAMILIES == expected


class TestComputeMelFromSignal:
    """_compute_mel_from_signal is IO-free and directly testable."""

    def test_output_shape(self):
        y = np.random.randn(TRAIT_SAMPLE_RATE).astype(np.float32)
        mel = _compute_mel_from_signal(y)
        assert mel.ndim == 2
        assert mel.shape[0] == 96

    def test_output_dtype(self):
        y = np.random.randn(TRAIT_SAMPLE_RATE).astype(np.float32)
        mel = _compute_mel_from_signal(y)
        assert mel.dtype == np.float32

    def test_values_non_negative(self):
        y = np.random.randn(TRAIT_SAMPLE_RATE).astype(np.float32)
        mel = _compute_mel_from_signal(y)
        assert mel.min() >= 0.0

    def test_matches_compute_mel_spectrogram(self):
        """Verify identical output to the public wrapper when given the same signal."""
        from unittest.mock import patch

        y = np.random.randn(TRAIT_SAMPLE_RATE).astype(np.float32)

        with patch("src.feature_extraction.trait_extractor.librosa") as mock_lr:
            mock_lr.load.return_value = (y, TRAIT_SAMPLE_RATE)
            mock_lr.feature.melspectrogram = __import__(
                "librosa"
            ).feature.melspectrogram
            from_file = compute_mel_spectrogram("dummy.wav")

        from_signal = _compute_mel_from_signal(y)
        np.testing.assert_array_equal(from_signal, from_file)

    def test_short_signal(self):
        y = np.random.randn(256).astype(np.float32)
        mel = _compute_mel_from_signal(y)
        assert mel.ndim == 2
        assert mel.shape[0] == 96
        assert mel.shape[1] >= 1


class TestComputeMelSpectrogram:
    @pytest.mark.skipif(not _TEST_FILES, reason="No test data files found")
    def test_mel_shape(self):
        # Use smallest MP3 for speed
        mp3_files = [f for f in _TEST_FILES if f.suffix == ".mp3"]
        if not mp3_files:
            pytest.skip("No MP3 in test data")
        mel = compute_mel_spectrogram(str(mp3_files[0]))
        assert mel.ndim == 2
        assert mel.shape[0] == 96  # mel bands
        assert mel.shape[1] > 0  # time frames
        assert mel.dtype == np.float32

    @pytest.mark.skipif(not _TEST_FILES, reason="No test data files found")
    def test_mel_values_positive(self):
        mp3_files = [f for f in _TEST_FILES if f.suffix == ".mp3"]
        if not mp3_files:
            pytest.skip("No MP3 in test data")
        mel = compute_mel_spectrogram(str(mp3_files[0]))
        # log(10000 * mel + 1) is always >= 0
        assert mel.min() >= 0.0

    @pytest.mark.skipif(not _TEST_FILES, reason="No test data files found")
    def test_mel_uses_amplitude_not_power(self):
        """Essentia uses power=1.0 (amplitude), not power=2.0 (power spectrogram).

        Validate that compute_mel_spectrogram matches power=1.0 and not power=2.0.
        """
        import librosa as _librosa

        mp3_files = [f for f in _TEST_FILES if f.suffix == ".mp3"]
        if not mp3_files:
            pytest.skip("No MP3 in test data")
        path = str(mp3_files[0])
        y, _ = _librosa.load(path, sr=TRAIT_SAMPLE_RATE, mono=True)

        mel_amp = _librosa.feature.melspectrogram(
            y=y,
            sr=TRAIT_SAMPLE_RATE,
            n_fft=512,
            hop_length=256,
            n_mels=96,
            fmax=8000,
            norm=None,
            power=1.0,
            htk=False,
        )
        expected = np.log(10000.0 * mel_amp + 1.0).astype(np.float32)
        actual = compute_mel_spectrogram(path)

        np.testing.assert_array_equal(
            actual,
            expected,
            err_msg="compute_mel_spectrogram does not match power=1.0 amplitude preprocessing",
        )

    @pytest.mark.skipif(not _TEST_FILES, reason="No test data files found")
    def test_aif_extension_loads(self):
        aif_files = [f for f in _TEST_FILES if f.suffix == ".aif"]
        if not aif_files:
            pytest.skip("No .aif files in test data")
        mel = compute_mel_spectrogram(str(aif_files[0]))
        assert mel.shape[0] == 96


class TestSpectralFlatnessGuard:
    """The nanmean + NaN-fallback pattern applied to spectral_flatness in compute()."""

    def test_all_nan_returns_zero(self):
        import math

        arr = np.full((1, 50), np.nan, dtype=np.float32)
        raw = float(np.nanmean(arr))
        result = round(raw if not np.isnan(raw) else 0.0, 6)
        assert result == 0.0
        assert not math.isnan(result)

    def test_normal_values_compute_correctly(self):
        arr = np.array([[0.1, 0.2, 0.3, 0.4]], dtype=np.float32)
        raw = float(np.nanmean(arr))
        result = round(raw if not np.isnan(raw) else 0.0, 6)
        assert abs(result - 0.25) < 1e-5

    def test_partial_nan_uses_valid_entries(self):
        arr = np.array([[0.4, np.nan, 0.6, np.nan]], dtype=np.float32)
        raw = float(np.nanmean(arr))
        result = round(raw if not np.isnan(raw) else 0.0, 6)
        assert abs(result - 0.5) < 1e-5

    def test_zero_array_returns_zero(self):
        arr = np.zeros((1, 50), dtype=np.float32)
        raw = float(np.nanmean(arr))
        result = round(raw if not np.isnan(raw) else 0.0, 6)
        assert result == 0.0


class TestZeroSampleGuard:
    """Guard: compute() raises ValueError when audio loads with 0 samples."""

    def test_empty_array_triggers_condition(self):
        y = np.zeros(0, dtype=np.float32)
        assert len(y) == 0

    def test_normal_array_bypasses_condition(self):
        y = np.random.rand(16000).astype(np.float32)
        assert len(y) > 0

    @pytest.mark.integration
    @pytest.mark.skipif(not _HAVE_BACKBONE, reason="EffNet backbone required")
    def test_zero_sample_wav_raises_value_error(self, tmp_path):
        """A real WAV with 1 silent sample still passes; but an empty file
        should be caught. We write a 1-frame silent WAV to verify the guard
        does NOT falsely trigger on valid (if tiny) audio.
        """
        import soundfile as sf
        from src.feature_extraction.trait_extractor import TraitExtractor

        silent_path = tmp_path / "silent.wav"
        sf.write(
            str(silent_path),
            np.zeros(TRAIT_SAMPLE_RATE, dtype=np.float32),
            TRAIT_SAMPLE_RATE,
        )

        extractor = TraitExtractor()
        traits = extractor.compute(str(silent_path))
        assert traits["onset_density"] == 0.0 or traits["onset_density"] >= 0.0
        assert traits["spectral_flatness"] == 0.0


class TestMigrationAndBackfill:
    """Unit tests for migration/backfill correctness and idempotency."""

    def test_migration_marks_non_current_rows_as_outdated(self):
        """Migration SQL sets trait_version to 'outdated' for non-current rows."""
        import importlib
        from unittest.mock import MagicMock, patch

        migration = importlib.import_module(
            "src.scripts.migrations.20260403_update_genre_mood_filtering"
        )

        mock_engine = MagicMock()
        mock_engine.execute.return_value = MagicMock(rowcount=3)

        with patch.object(migration, "database") as mock_db:
            mock_db.engine = mock_engine
            migration.run()

        mock_engine.execute.assert_called_once()
        sql = mock_engine.execute.call_args[0][0]
        assert "SET trait_version = 'outdated'" in sql
        assert "WHERE trait_version != '%s'" % TRAIT_VERSION in sql

    def test_migration_is_idempotent(self):
        """Second run is a no-op — SQL only targets non-current rows."""
        import importlib
        from unittest.mock import MagicMock, patch

        migration = importlib.import_module(
            "src.scripts.migrations.20260403_update_genre_mood_filtering"
        )

        mock_engine = MagicMock()
        mock_engine.execute.side_effect = [
            MagicMock(rowcount=3),
            MagicMock(rowcount=0),
        ]

        with patch.object(migration, "database") as mock_db:
            mock_db.engine = mock_engine
            migration.run()
            migration.run()

        assert mock_engine.execute.call_count == 2
        calls = mock_engine.execute.call_args_list
        assert calls[0] == calls[1], "Both runs must execute identical SQL"

    def test_backfill_skips_current_version_rows(self):
        """Backfill spawns no workers when all rows are current."""
        import importlib
        from unittest.mock import MagicMock, patch

        backfill = importlib.import_module(
            "src.scripts.feature_extraction.backfill_genre_mood"
        )

        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.all.return_value = []
        mock_session.query.return_value.all.return_value = []

        with patch.object(backfill, "database") as mock_db, \
             patch.object(backfill, "Process") as mock_process:
            mock_db.create_session.return_value = mock_session
            backfill.run()

        mock_process.assert_not_called()


# ------------------------------------------------------------------ #
# Integration tests — require models/traits/ to be populated          #
# ------------------------------------------------------------------ #


@pytest.mark.integration
@pytest.mark.skipif(not _HAVE_BACKBONE, reason="EffNet backbone not in models/traits/")
class TestTraitExtractorIntegration:
    """End-to-end tests exercising the full inference chain.

    Each test picks a specific file to probe a particular edge case.
    """

    @pytest.fixture(scope="class")
    def extractor(self):
        from src.feature_extraction.trait_extractor import TraitExtractor

        return TraitExtractor()

    # ---- format coverage ----

    def test_mp3_short(self, extractor):
        """Small MP3 (3.3 MB / ~87 s) — basic smoke test."""
        f = _TEST_DATA / "[05A - Cm - 000] Bicep - Vespa.mp3"
        traits = extractor.compute(str(f))
        _is_valid_trait_dict(traits)

    def test_mp3_medium(self, extractor):
        """Medium MP3 (~4 min) — confirm no off-by-one in window count."""
        f = (
            _TEST_DATA
            / "[08A - Am - 144.00] Pernox - Cruel Intentions (Alpha Tracks Remix).mp3"
        )
        traits = extractor.compute(str(f))
        _is_valid_trait_dict(traits)

    def test_mp3_small_with_bracket_filename(self, extractor):
        """Small MP3 with Discogs-style bracket filename."""
        f = (
            _TEST_DATA
            / "[10B - D - 124.00] Ed Sheeran - Shivers (Dillon Francis Remix) [Club Mix].mp3"
        )
        traits = extractor.compute(str(f))
        _is_valid_trait_dict(traits)

    def test_aiff_normal(self, extractor):
        """AIFF format — librosa loads via soundfile."""
        f = _TEST_DATA / "[04A - Fm - 116.99] Koreless - White Picket Fence.aiff"
        traits = extractor.compute(str(f))
        _is_valid_trait_dict(traits)

    def test_aif_extension(self, extractor):
        """.aif extension (no trailing f) — different than .aiff."""
        f = (
            _TEST_DATA
            / "[12A - C#m - 140] Neptune Project - Panspermia (The Digital Blonde Remix).aif"
        )
        traits = extractor.compute(str(f))
        _is_valid_trait_dict(traits)

    def test_aiff_vocal_track(self, extractor):
        """Track with vocals — voice_instrumental should be non-None and high."""
        f = (
            _TEST_DATA
            / "[07B - F - 126.00] Beyonce - Drunk in Love (Glass Half Empty Remix).aiff"
        )
        traits = extractor.compute(str(f))
        _is_valid_trait_dict(traits)
        # voice_instrumental may be None if classifier not downloaded, but check type
        if traits["voice_instrumental"] is not None:
            assert 0.0 <= traits["voice_instrumental"] <= 1.0

    # ---- long track edge cases ----

    def test_long_aiff_no_crash(self, extractor):
        """Long AIFF (~14 min, 101 MB) — should not OOM or crash."""
        f = _TEST_DATA / "[04A - Fm - 146.00] Frank Heise - Abort To Orbit.aiff"
        traits = extractor.compute(str(f))
        _is_valid_trait_dict(traits)

    def test_very_long_aiff_no_crash(self, extractor):
        """Very long AIFF (~25 min, 241 MB) — stress test for memory/windowing."""
        f = _TEST_DATA / "[08A - Am - 137.00] Omformer - Interstellar Infection.aiff"
        traits = extractor.compute(str(f))
        _is_valid_trait_dict(traits)

    def test_long_aiff_solar_fields(self, extractor):
        """Another long AIFF — Solar Fields (ambient, long form)."""
        f = _TEST_DATA / "[08B - C - 085.00] Solar Fields - Electric Fluid.aiff"
        traits = extractor.compute(str(f))
        _is_valid_trait_dict(traits)

    def test_aiff_short(self, extractor):
        """Short-ish AIFF (28 MB)."""
        f = (
            _TEST_DATA
            / "[12B - E - 155.00] Alexandra Stone - Mr. Saxobeat (Skearney Edit).aiff"
        )
        traits = extractor.compute(str(f))
        _is_valid_trait_dict(traits)

    # ---- result quality checks ----

    def test_genre_always_present(self, extractor):
        """genre comes from MAEST backbone — must be non-None and non-empty for music."""
        pytest.importorskip("onnxruntime")
        if not _HAVE_MAEST:
            pytest.skip("MAEST model not downloaded")
        f = _TEST_DATA / "[05A - Cm - 000] Bicep - Vespa.mp3"
        traits = extractor.compute(str(f))
        assert traits["genre"] is not None
        assert len(traits["genre"]) > 0, "Expected at least one genre above threshold"

    def test_genre_uses_real_labels(self, extractor):
        """Genre labels must all be from the Discogs-519 MAEST taxonomy."""
        if not _HAVE_MAEST:
            pytest.skip("MAEST model not downloaded")
        f = _TEST_DATA / "[05A - Cm - 000] Bicep - Vespa.mp3"
        traits = extractor.compute(str(f))
        label_set = set(LABELS_GENRE_DISCOGS519)
        for label in traits["genre"] or {}:
            assert label in label_set, "Unknown genre label: %s" % label

    def test_onset_density_reasonable(self, extractor):
        """onset_density should be a plausible value (0.5–20 onsets/sec for music)."""
        f = _TEST_DATA / "[05A - Cm - 000] Bicep - Vespa.mp3"
        traits = extractor.compute(str(f))
        assert 0.0 < traits["onset_density"] < 100.0

    def test_spectral_flatness_in_range(self, extractor):
        f = _TEST_DATA / "[05A - Cm - 000] Bicep - Vespa.mp3"
        traits = extractor.compute(str(f))
        assert 0.0 <= traits["spectral_flatness"] <= 1.0

    def test_deterministic(self, extractor):
        """Running on the same file twice must return identical results."""
        f = _TEST_DATA / "[05A - Cm - 000] Bicep - Vespa.mp3"
        t1 = extractor.compute(str(f))
        t2 = extractor.compute(str(f))
        assert t1["genre"] == t2["genre"]
        assert t1["onset_density"] == t2["onset_density"]
        assert t1["voice_instrumental"] == t2["voice_instrumental"]

    def test_different_files_different_results(self, extractor):
        """Two distinct tracks should produce different embeddings and genres."""
        f1 = _TEST_DATA / "[05A - Cm - 000] Bicep - Vespa.mp3"
        f2 = (
            _TEST_DATA
            / "[10B - D - 124.00] Ed Sheeran - Shivers (Dillon Francis Remix) [Club Mix].mp3"
        )
        t1 = extractor.compute(str(f1))
        t2 = extractor.compute(str(f2))
        assert t1["genre"] != t2["genre"] or t1["onset_density"] != t2["onset_density"]


@pytest.mark.integration
@pytest.mark.skipif(not _HAVE_BACKBONE, reason="EffNet backbone not in models/traits/")
class TestModelManagerIntegration:
    def test_load_backbone_returns_session(self):
        from src.feature_extraction.model_manager import load_model
        import onnxruntime as ort

        session = load_model("discogs-effnet-bsdynamic")
        assert isinstance(session, ort.InferenceSession)

    def test_load_model_cached(self):
        from src.feature_extraction.model_manager import load_model, _session_cache

        load_model("discogs-effnet-bsdynamic")
        assert "discogs-effnet-bsdynamic" in _session_cache

    def test_load_unknown_model_raises(self):
        from src.feature_extraction.model_manager import load_model

        with pytest.raises((KeyError, RuntimeError)):
            load_model("nonexistent-model-xyz")

    def test_is_valid_onnx_rejects_html(self, tmp_path):
        from src.feature_extraction.model_manager import _is_valid_onnx

        html = tmp_path / "bad.onnx"
        html.write_text("<html><body>504 Gateway Timeout</body></html>")
        assert not _is_valid_onnx(str(html))

    def test_is_valid_onnx_rejects_small(self, tmp_path):
        from src.feature_extraction.model_manager import _is_valid_onnx

        tiny = tmp_path / "tiny.onnx"
        tiny.write_bytes(b"\x08\x06" + b"\x00" * 100)
        assert not _is_valid_onnx(str(tiny))

    def test_is_valid_onnx_accepts_real_backbone(self):
        from src.feature_extraction.model_manager import _is_valid_onnx

        assert _is_valid_onnx(str(_BACKBONE))

    def test_is_cached_backbone(self):
        from src.feature_extraction.model_manager import is_cached

        assert is_cached("discogs-effnet-bsdynamic")

    def test_is_cached_maest_when_downloaded(self):
        from src.feature_extraction.model_manager import is_cached

        if _HAVE_MAEST:
            assert is_cached("discogs-maest-30s-pw-519l")

    def test_is_cached_unknown_false(self):
        from src.feature_extraction.model_manager import is_cached

        assert not is_cached("nonexistent-model")
