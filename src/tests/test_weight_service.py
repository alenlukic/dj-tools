"""Tests for src/harmonic_mixing/weight_service.py.

Run with:
    python -m pytest src/tests/test_weight_service.py -v
"""

from unittest.mock import patch

import pytest

from src.harmonic_mixing.config import MatchFactors


def _make_service(**overrides):
    """Create a WeightService with DB persistence mocked out."""
    with patch("src.harmonic_mixing.weight_service.WeightService._load_from_db"):
        with patch("src.harmonic_mixing.weight_service.WeightService._persist_to_db"):
            from src.harmonic_mixing.weight_service import WeightService
            svc = WeightService()
            for k, v in overrides.items():
                if k in svc._raw_weights:
                    svc._raw_weights[k] = v
            return svc


class TestWeightFetch:
    def test_returns_expected_shape(self):
        svc = _make_service()
        result = svc.get_weights()
        assert "raw_weights" in result
        assert "effective_weights" in result
        assert "raw_sum" in result
        assert "target_sum" in result
        assert "is_sum_valid" in result
        assert "message" in result

    def test_raw_weights_on_0_100_scale(self):
        svc = _make_service()
        result = svc.get_weights()
        for factor in MatchFactors:
            raw = result["raw_weights"][factor.name]
            assert 0 <= raw <= 100

    def test_effective_weights_sum_to_100(self):
        svc = _make_service()
        result = svc.get_weights()
        eff_sum = sum(result["effective_weights"].values())
        assert eff_sum == pytest.approx(100.0, abs=0.1)

    def test_is_sum_valid_when_sum_matches_target(self):
        svc = _make_service()
        n = len(svc._raw_weights)
        for k in svc._raw_weights:
            svc._raw_weights[k] = 1.0 / n
        result = svc.get_weights()
        assert result["is_sum_valid"] is True
        assert result["message"] is None

    def test_is_sum_invalid_when_sum_differs(self):
        svc = _make_service()
        for k in svc._raw_weights:
            svc._raw_weights[k] = 0.5
        result = svc.get_weights()
        assert result["is_sum_valid"] is False
        assert result["message"] is not None
        assert "normalized" in result["message"].lower()


class TestWeightUpdate:
    @patch("src.harmonic_mixing.weight_service.WeightService._persist_to_db")
    @patch("src.harmonic_mixing.weight_service.WeightService._load_from_db")
    def test_update_persists_and_returns(self, mock_load, mock_persist):
        from src.harmonic_mixing.weight_service import WeightService
        svc = WeightService()
        result = svc.update_weights({"BPM": 50, "CAMELOT": 50})
        assert result["raw_weights"]["BPM"] == 50.0
        assert result["raw_weights"]["CAMELOT"] == 50.0
        mock_persist.assert_called()

    def test_unknown_keys_ignored(self):
        svc = _make_service()
        original_bpm = svc._raw_weights["BPM"]
        with patch.object(svc, "_persist_to_db"):
            svc.update_weights({"NONEXISTENT_FACTOR": 99})
        assert svc._raw_weights["BPM"] == original_bpm

    def test_update_does_not_reject_non_100_sum(self):
        svc = _make_service()
        with patch.object(svc, "_persist_to_db"):
            result = svc.update_weights({"BPM": 10, "CAMELOT": 10})
        assert "raw_weights" in result
        assert result["raw_weights"]["BPM"] == 10.0
        assert result["raw_weights"]["CAMELOT"] == 10.0


class TestEffectiveWeightsForScoring:
    def test_effective_weights_sum_to_one(self):
        svc = _make_service()
        eff = svc.get_effective_weights_for_scoring()
        assert sum(eff.values()) == pytest.approx(1.0, abs=1e-9)

    def test_all_zero_weights_distributes_evenly(self):
        svc = _make_service()
        for k in svc._raw_weights:
            svc._raw_weights[k] = 0.0
        eff = svc.get_effective_weights_for_scoring()
        n = len(svc._raw_weights)
        for v in eff.values():
            assert v == pytest.approx(1.0 / n, abs=1e-9)

    def test_normalization_preserves_ratios(self):
        svc = _make_service()
        for k in svc._raw_weights:
            svc._raw_weights[k] = 0.0
        svc._raw_weights["BPM"] = 0.6
        svc._raw_weights["CAMELOT"] = 0.4
        eff = svc.get_effective_weights_for_scoring()
        assert eff["BPM"] == pytest.approx(0.6, abs=1e-9)
        assert eff["CAMELOT"] == pytest.approx(0.4, abs=1e-9)

    def test_scoring_functional_when_sum_not_100(self):
        """Retrieval must not crash when raw weights don't sum to 100."""
        svc = _make_service()
        for k in svc._raw_weights:
            svc._raw_weights[k] = 0.5
        eff = svc.get_effective_weights_for_scoring()
        assert sum(eff.values()) == pytest.approx(1.0, abs=1e-9)
        assert all(v > 0 for v in eff.values())


class TestWeightPropagation:
    """PUT /api/weights must propagate immediately to the scoring path."""

    @patch("src.harmonic_mixing.weight_service.WeightService._persist_to_db")
    @patch("src.harmonic_mixing.weight_service.WeightService._load_from_db")
    def test_update_syncs_effective_weights_to_transition_match(
        self, mock_load, mock_persist
    ):
        from src.harmonic_mixing.transition_match import TransitionMatch
        from src.harmonic_mixing.weight_service import WeightService

        WeightService.reset()
        svc = WeightService()
        WeightService._instance = svc

        try:
            TransitionMatch.effective_weights = None

            from src.harmonic_mixing.transition_match_finder import TransitionMatchFinder
            TransitionMatchFinder._sync_effective_weights()

            assert TransitionMatch.effective_weights is not None
            prev_bpm = TransitionMatch.effective_weights.get("BPM")

            svc.update_weights({"BPM": 80})
            TransitionMatchFinder._sync_effective_weights()

            new_bpm = TransitionMatch.effective_weights.get("BPM")
            assert new_bpm != prev_bpm
            assert new_bpm > prev_bpm
        finally:
            WeightService.reset()
            TransitionMatch.effective_weights = None
