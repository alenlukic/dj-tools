"""Endpoint-level integration tests for the API routes added in ui-v4/v5.

Covers:
    GET  /api/admin/cache-stats
    GET  /api/weights
    PUT  /api/weights

Run with:
    python -m pytest src/tests/test_api_routes.py -v
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.harmonic_mixing.cosine_cache import CosineCache


@pytest.fixture(autouse=True)
def _reset_weight_singleton():
    yield
    from src.harmonic_mixing.weight_service import WeightService
    WeightService._instance = None


@pytest.fixture()
def weight_patches():
    """Keep WeightService DB calls mocked for the duration of a test."""
    with patch("src.harmonic_mixing.weight_service.WeightService._load_from_db"), \
         patch("src.harmonic_mixing.weight_service.WeightService._persist_to_db"):
        from src.harmonic_mixing.weight_service import WeightService
        WeightService._instance = None
        yield


@pytest.fixture()
def mock_finder():
    finder = MagicMock()
    finder.cosine_cache = None
    finder._sync_effective_weights = MagicMock()
    return finder


@pytest.fixture()
def client(mock_finder, weight_patches):
    """A TestClient with match finder and weight DB stubbed out."""
    with patch("src.api.routes._get_match_finder", return_value=mock_finder):
        from src.api.app import create_app
        app = create_app()
        yield TestClient(app)


# ---------------------------------------------------------------------------
# GET /api/admin/cache-stats
# ---------------------------------------------------------------------------


class TestCacheStatsEndpoint:
    def test_returns_200_with_no_cache(self):
        finder = MagicMock()
        finder.cosine_cache = None

        with patch("src.api.routes._get_match_finder", return_value=finder):
            from src.api.app import create_app
            with TestClient(create_app()) as tc:
                resp = tc.get("/api/admin/cache-stats")

        assert resp.status_code == 200
        data = resp.json()
        assert data["used"] == 0
        assert data["capacity"] == 0
        assert data["hit_rate"] == 0.0
        assert data["key_distribution"] == []
        assert data["bpm_distribution"] == []
        assert data["recent_entries"] == []
        assert data["recent_exits"] == []

    def test_returns_200_with_populated_cache(self):
        cache = CosineCache(max_entries=100)
        cache.put(10, 20, 0.85)
        cache.put(10, 30, 0.70)
        cache.get(10, 20)  # hit
        cache.get(99, 100)  # miss

        finder = MagicMock()
        finder.cosine_cache = cache

        with patch("src.api.routes._get_match_finder", return_value=finder), \
             patch("src.api.routes._build_cache_distributions", return_value=([], [])):
            from src.api.app import create_app
            with TestClient(create_app()) as tc:
                resp = tc.get("/api/admin/cache-stats")

        assert resp.status_code == 200
        data = resp.json()
        assert data["used"] == 2
        assert data["capacity"] == 100
        assert data["hits"] == 1
        assert data["misses"] == 1
        assert data["hit_rate_basis"] == "process_lifetime"
        assert len(data["recent_entries"]) == 2

    def test_response_matches_schema(self):
        cache = CosineCache(max_entries=50)
        cache.put(1, 2, 0.5)

        finder = MagicMock()
        finder.cosine_cache = cache

        with patch("src.api.routes._get_match_finder", return_value=finder), \
             patch("src.api.routes._build_cache_distributions", return_value=([], [])):
            from src.api.app import create_app
            with TestClient(create_app()) as tc:
                resp = tc.get("/api/admin/cache-stats")

        data = resp.json()
        required_keys = {
            "used", "capacity", "usage_ratio",
            "hits", "misses", "hit_rate",
            "hit_rate_numerator", "hit_rate_denominator", "hit_rate_basis",
            "key_distribution", "bpm_distribution",
            "recent_entries", "recent_exits",
        }
        assert required_keys.issubset(data.keys())


# ---------------------------------------------------------------------------
# GET /api/weights
# ---------------------------------------------------------------------------


class TestGetWeightsEndpoint:
    def test_returns_200_with_expected_shape(self, client):
        resp = client.get("/api/weights")

        assert resp.status_code == 200
        data = resp.json()
        assert "raw_weights" in data
        assert "effective_weights" in data
        assert "raw_sum" in data
        assert "target_sum" in data
        assert "is_sum_valid" in data
        assert "message" in data

    def test_effective_weights_sum_to_target(self, client):
        data = client.get("/api/weights").json()
        eff_sum = sum(data["effective_weights"].values())
        assert eff_sum == pytest.approx(100.0, abs=0.1)

    def test_raw_weights_contains_all_factors(self, client):
        from src.harmonic_mixing.config import MatchFactors
        data = client.get("/api/weights").json()
        for factor in MatchFactors:
            assert factor.name in data["raw_weights"]


# ---------------------------------------------------------------------------
# PUT /api/weights
# ---------------------------------------------------------------------------


class TestPutWeightsEndpoint:
    def test_update_returns_200_with_new_values(self, client, mock_finder):
        resp = client.put("/api/weights", json={"weights": {"BPM": 50, "CAMELOT": 50}})

        assert resp.status_code == 200
        data = resp.json()
        assert data["raw_weights"]["BPM"] == 50.0
        assert data["raw_weights"]["CAMELOT"] == 50.0
        mock_finder._sync_effective_weights.assert_called_once()

    def test_non_100_sum_returns_warning(self, client):
        resp = client.put("/api/weights", json={"weights": {"BPM": 10, "CAMELOT": 10}})

        assert resp.status_code == 200
        data = resp.json()
        assert data["is_sum_valid"] is False
        assert data["message"] is not None
        assert "normalized" in data["message"].lower()

    def test_non_100_sum_update_then_get_round_trip(self, client):
        """PUT with non-100 sum, then GET, verifying consistency."""
        put_resp = client.put(
            "/api/weights",
            json={"weights": {"BPM": 10, "CAMELOT": 10}},
        )
        assert put_resp.status_code == 200
        put_data = put_resp.json()
        assert put_data["is_sum_valid"] is False

        get_resp = client.get("/api/weights")
        assert get_resp.status_code == 200
        get_data = get_resp.json()

        assert get_data["raw_weights"]["BPM"] == put_data["raw_weights"]["BPM"]
        assert get_data["raw_weights"]["CAMELOT"] == put_data["raw_weights"]["CAMELOT"]
        assert get_data["is_sum_valid"] is False

        eff_sum = sum(get_data["effective_weights"].values())
        assert eff_sum == pytest.approx(100.0, abs=0.1)

    def test_unknown_keys_ignored(self, client):
        resp = client.put(
            "/api/weights",
            json={"weights": {"NONEXISTENT": 99}},
        )
        assert resp.status_code == 200

    def test_empty_body_returns_422(self, client):
        resp = client.put("/api/weights", json={})
        assert resp.status_code == 422
