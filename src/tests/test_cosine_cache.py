"""Tests for src/harmonic_mixing/cosine_cache.py and cache integration.

Run with:
    python -m pytest src/tests/test_cosine_cache.py -v
"""

import threading
from unittest.mock import MagicMock, patch

import pytest

from src.harmonic_mixing.cosine_cache import CosineCache


# ---------------------------------------------------------------------------
# Unit tests: basic cache semantics
# ---------------------------------------------------------------------------


class TestCosineCacheGetPut:
    def test_get_miss_returns_none(self):
        cache = CosineCache()
        assert cache.get(1, 2) is None

    def test_put_then_get_returns_value(self):
        cache = CosineCache()
        cache.put(1, 2, 0.95)
        assert cache.get(1, 2) == 0.95

    def test_canonical_ordering_reversed_ids(self):
        cache = CosineCache()
        cache.put(5, 3, 0.75)
        assert cache.get(3, 5) == 0.75
        assert cache.get(5, 3) == 0.75

    def test_overwrite_existing_key(self):
        cache = CosineCache()
        cache.put(1, 2, 0.5)
        cache.put(1, 2, 0.9)
        assert cache.get(1, 2) == 0.9

    def test_size(self):
        cache = CosineCache()
        assert cache.size() == 0
        cache.put(1, 2, 0.5)
        cache.put(3, 4, 0.6)
        assert cache.size() == 2


class TestCosineCacheLRUEviction:
    def test_eviction_at_max_plus_one(self):
        max_entries = 5
        cache = CosineCache(max_entries=max_entries)
        for i in range(max_entries):
            cache.put(i, i + 1000, float(i))
        assert cache.size() == max_entries

        cache.put(999, 1999, 0.99)
        assert cache.size() == max_entries
        # Oldest entry (0, 1000) should have been evicted
        assert cache.get(0, 1000) is None
        # Newest entry should be present
        assert cache.get(999, 1999) == 0.99

    def test_lru_eviction_at_500001(self):
        """Verify the default 500000-entry cap evicts the LRU entry."""
        max_entries = 500_000
        cache = CosineCache(max_entries=max_entries)
        for i in range(max_entries):
            cache.put(i, i + 1_000_000, float(i) / max_entries)
        assert cache.size() == max_entries

        cache.put(999_999, 1_999_999, 0.42)
        assert cache.size() == max_entries
        assert cache.get(0, 1_000_000) is None
        assert cache.get(999_999, 1_999_999) == 0.42

    def test_get_refreshes_lru_order(self):
        cache = CosineCache(max_entries=3)
        cache.put(1, 2, 0.1)
        cache.put(3, 4, 0.2)
        cache.put(5, 6, 0.3)
        # Access the oldest to refresh it
        cache.get(1, 2)
        # Add a new entry; (3,4) should be evicted since it's now oldest
        cache.put(7, 8, 0.4)
        assert cache.get(3, 4) is None
        assert cache.get(1, 2) == 0.1


class TestCosineCacheThreadSafety:
    def test_concurrent_puts_no_crash(self):
        cache = CosineCache(max_entries=10_000)
        errors = []

        def writer(start):
            try:
                for i in range(1000):
                    cache.put(start + i, start + i + 100_000, float(i))
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=writer, args=(t * 10_000,)) for t in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert cache.size() <= 10_000


# ---------------------------------------------------------------------------
# BFS warm_from_db
# ---------------------------------------------------------------------------


def _make_sim_row(id1, id2, sim, version="1"):
    row = MagicMock()
    row.id1 = id1
    row.id2 = id2
    row.cosine_similarity = sim
    row.descriptor_version = version
    return row


class TestWarmFromDb:
    @patch("src.harmonic_mixing.cosine_cache.database")
    def test_depth_1_and_depth_2(self, mock_db_module):
        mock_session = MagicMock()
        mock_db_module.create_session.return_value = mock_session

        depth1_rows = [
            _make_sim_row(10, 20, 0.8),
            _make_sim_row(10, 30, 0.7),
        ]
        depth2_rows_for_20 = [
            _make_sim_row(20, 40, 0.6),
        ]
        depth2_rows_for_30 = [
            _make_sim_row(30, 50, 0.5),
        ]

        def query_side_effect(model):
            return mock_session._query_result

        mock_query = MagicMock()
        mock_session.query.return_value = mock_query

        call_count = {"n": 0}
        results_sequence = [depth1_rows, depth2_rows_for_20, depth2_rows_for_30]

        def filter_by_side_effect(**kwargs):
            mock_filtered = MagicMock()
            mock_filtered.all.return_value = results_sequence[call_count["n"]]
            call_count["n"] += 1
            return mock_filtered

        mock_query.filter_by.side_effect = filter_by_side_effect

        cache = CosineCache()
        cache.warm_from_db(10)

        assert cache.get(10, 20) == 0.8
        assert cache.get(10, 30) == 0.7
        assert cache.get(20, 40) == 0.6
        assert cache.get(30, 50) == 0.5
        assert cache.size() == 4

    @patch("src.harmonic_mixing.cosine_cache.database")
    def test_warm_creates_own_session(self, mock_db_module):
        mock_session = MagicMock()
        mock_db_module.create_session.return_value = mock_session
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter_by.return_value.all.return_value = []

        cache = CosineCache()
        cache.warm_from_db(42)

        mock_db_module.create_session.assert_called_once()
        mock_session.close.assert_called_once()

    @patch("src.harmonic_mixing.cosine_cache.database")
    def test_warm_closes_session_on_error(self, mock_db_module):
        mock_session = MagicMock()
        mock_db_module.create_session.return_value = mock_session
        mock_session.query.side_effect = RuntimeError("boom")

        cache = CosineCache()
        cache.warm_from_db(1)

        mock_session.close.assert_called_once()


# ---------------------------------------------------------------------------
# Integration: similarity score consults cache before DB/compute
# ---------------------------------------------------------------------------


class TestSimilarityScoreCacheIntegration:
    def test_cache_hit_skips_db(self):
        """When cache has a value, get_similarity_score must return it
        without touching descriptor caches or db_session."""
        from src.harmonic_mixing.transition_match import TransitionMatch
        from src.data_management.config import TrackDBCols
        from src.harmonic_mixing.config import CamelotPriority, MatchFactors

        cache = CosineCache()
        cache.put(100, 200, 0.88)

        original_db_session = TransitionMatch.db_session
        original_cosine_cache = TransitionMatch.cosine_cache
        try:
            TransitionMatch.cosine_cache = cache
            TransitionMatch.db_session = None

            cur_md = {TrackDBCols.ID: 100, TrackDBCols.TITLE: "Track A"}
            cand_md = {TrackDBCols.ID: 200, TrackDBCols.TITLE: "Track B"}
            match = TransitionMatch(cand_md, cur_md, CamelotPriority.SAME_KEY)

            result = match.get_similarity_score()
            assert result == 0.88
            assert match.factors[MatchFactors.SIMILARITY] == 0.88
        finally:
            TransitionMatch.db_session = original_db_session
            TransitionMatch.cosine_cache = original_cosine_cache

    def test_cache_miss_falls_through_to_compute_and_stores(self):
        """On cache miss, the score must be computed and stored in cache."""
        from src.harmonic_mixing.transition_match import TransitionMatch
        from src.data_management.config import TrackDBCols
        from src.harmonic_mixing.config import CamelotPriority

        cache = CosineCache()
        mock_session = MagicMock()

        mock_desc = MagicMock()
        import numpy as np
        mock_desc.global_vector = np.ones(75, dtype=np.float32).tobytes()

        mock_session.query.return_value.filter_by.return_value.first.return_value = mock_desc

        original_db_session = TransitionMatch.db_session
        original_cosine_cache = TransitionMatch.cosine_cache
        original_od_cache = TransitionMatch._on_deck_descriptor_cache.copy()
        original_cd_cache = TransitionMatch._candidate_descriptor_cache.copy()
        try:
            TransitionMatch.db_session = mock_session
            TransitionMatch.cosine_cache = cache
            TransitionMatch._on_deck_descriptor_cache.clear()
            TransitionMatch._candidate_descriptor_cache.clear()

            cur_md = {TrackDBCols.ID: 300, TrackDBCols.TITLE: "Track C"}
            cand_md = {TrackDBCols.ID: 400, TrackDBCols.TITLE: "Track D"}
            match = TransitionMatch(cand_md, cur_md, CamelotPriority.SAME_KEY)

            result = match.get_similarity_score()
            assert result == pytest.approx(0.7, abs=1e-6)
            assert cache.get(300, 400) == pytest.approx(0.7, abs=1e-6)
        finally:
            TransitionMatch.db_session = original_db_session
            TransitionMatch.cosine_cache = original_cosine_cache
            TransitionMatch._on_deck_descriptor_cache = original_od_cache
            TransitionMatch._candidate_descriptor_cache = original_cd_cache

    def test_no_cache_still_works(self):
        """When cosine_cache is None, the old DB/compute path works."""
        from src.harmonic_mixing.transition_match import TransitionMatch
        from src.data_management.config import TrackDBCols
        from src.harmonic_mixing.config import CamelotPriority

        mock_session = MagicMock()
        mock_session.query.return_value.filter_by.return_value.first.return_value = None

        original_db_session = TransitionMatch.db_session
        original_cosine_cache = TransitionMatch.cosine_cache
        original_od_cache = TransitionMatch._on_deck_descriptor_cache.copy()
        original_cd_cache = TransitionMatch._candidate_descriptor_cache.copy()
        try:
            TransitionMatch.db_session = mock_session
            TransitionMatch.cosine_cache = None
            TransitionMatch._on_deck_descriptor_cache.clear()
            TransitionMatch._candidate_descriptor_cache.clear()

            cur_md = {TrackDBCols.ID: 500, TrackDBCols.TITLE: "Track E"}
            cand_md = {TrackDBCols.ID: 600, TrackDBCols.TITLE: "Track F"}
            match = TransitionMatch(cand_md, cur_md, CamelotPriority.SAME_KEY)

            result = match.get_similarity_score()
            assert result == 0.0
        finally:
            TransitionMatch.db_session = original_db_session
            TransitionMatch.cosine_cache = original_cosine_cache
            TransitionMatch._on_deck_descriptor_cache = original_od_cache
            TransitionMatch._candidate_descriptor_cache = original_cd_cache
