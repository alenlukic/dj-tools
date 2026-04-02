"""Tests for cosine similarity precompute: model, compute helpers, and orchestration.

Run:
    python -m pytest src/tests/test_cosine_similarity.py -v
"""

from unittest.mock import MagicMock, patch

import pytest

from src.data_management.config import TrackDBCols
from src.feature_extraction.config import DESCRIPTOR_VERSION
from src.models.track_cosine_similarity import TrackCosineSimilarity
from src.scripts.feature_extraction.compute_cosine_similarities import (
    _chunkify,
    _classify_existing_pairs,
    _extract_candidate_ids,
    _get_tracks_for_processing,
    _ordered_pair,
)


# ---------------------------------------------------------------------------
# TrackCosineSimilarity model
# ---------------------------------------------------------------------------


class TestTrackCosineSimilarityModel:
    def test_tablename(self):
        assert TrackCosineSimilarity.__tablename__ == "track_cosine_similarity"

    def test_has_composite_pk_columns(self):
        mapper = TrackCosineSimilarity.__table__
        pk_cols = {c.name for c in mapper.primary_key}
        assert pk_cols == {"id1", "id2"}

    def test_has_check_constraint(self):
        constraints = [
            c
            for c in TrackCosineSimilarity.__table__.constraints
            if hasattr(c, "sqltext")
        ]
        texts = [str(c.sqltext) for c in constraints]
        assert any("id1 < id2" in t for t in texts)

    def test_eq_same_pair(self):
        a = TrackCosineSimilarity(id1=1, id2=2, cosine_similarity=0.9)
        b = TrackCosineSimilarity(id1=1, id2=2, cosine_similarity=0.5)
        assert a == b

    def test_eq_different_pair(self):
        a = TrackCosineSimilarity(id1=1, id2=2)
        b = TrackCosineSimilarity(id1=1, id2=3)
        assert a != b

    def test_hash_deterministic(self):
        a = TrackCosineSimilarity(id1=5, id2=10)
        b = TrackCosineSimilarity(id1=5, id2=10)
        assert hash(a) == hash(b)

    def test_hash_differs_for_different_pairs(self):
        a = TrackCosineSimilarity(id1=1, id2=2)
        b = TrackCosineSimilarity(id1=2, id2=3)
        assert hash(a) != hash(b)

    def test_cosine_similarity_column_not_nullable(self):
        col = TrackCosineSimilarity.__table__.c.cosine_similarity
        assert col.nullable is False

    def test_descriptor_version_column_not_nullable(self):
        col = TrackCosineSimilarity.__table__.c.descriptor_version
        assert col.nullable is False

    def test_foreign_keys_reference_track(self):
        fk1 = list(TrackCosineSimilarity.__table__.c.id1.foreign_keys)
        fk2 = list(TrackCosineSimilarity.__table__.c.id2.foreign_keys)
        assert len(fk1) == 1
        assert len(fk2) == 1
        assert "track.id" in str(fk1[0].target_fullname)
        assert "track.id" in str(fk2[0].target_fullname)


# ---------------------------------------------------------------------------
# _ordered_pair
# ---------------------------------------------------------------------------


class TestOrderedPair:
    def test_already_ordered(self):
        assert _ordered_pair(1, 5) == (1, 5)

    def test_reversed(self):
        assert _ordered_pair(10, 3) == (3, 10)

    def test_equal_ids(self):
        assert _ordered_pair(7, 7) == (7, 7)

    def test_negative_ids(self):
        assert _ordered_pair(-1, -5) == (-5, -1)


# ---------------------------------------------------------------------------
# _extract_candidate_ids
# ---------------------------------------------------------------------------


def _make_match(candidate_id, source_id=1):
    """Create a mock TransitionMatch with the given candidate ID."""
    match = MagicMock()
    match.metadata = {TrackDBCols.ID: candidate_id}
    match.cur_track_md = {TrackDBCols.ID: source_id}
    return match


class TestExtractCandidateIds:
    def test_combines_all_match_lists(self):
        same = [_make_match(10), _make_match(20)]
        higher = [_make_match(30)]
        lower = [_make_match(40)]
        result = _extract_candidate_ids(((same, higher, lower), ""), source_track_id=1)
        assert result == {10, 20, 30, 40}

    def test_deduplicates_across_lists(self):
        same = [_make_match(10)]
        higher = [_make_match(10)]
        lower = [_make_match(10)]
        result = _extract_candidate_ids(((same, higher, lower), ""), source_track_id=1)
        assert result == {10}

    def test_excludes_source_track(self):
        same = [_make_match(1), _make_match(2)]
        result = _extract_candidate_ids(((same, [], []), ""), source_track_id=1)
        assert result == {2}

    def test_empty_matches_returns_empty(self):
        result = _extract_candidate_ids((([], [], []), ""), source_track_id=1)
        assert result == set()

    def test_skips_none_candidate_id(self):
        match = MagicMock()
        match.metadata = {TrackDBCols.ID: None}
        result = _extract_candidate_ids((([match], [], []), ""), source_track_id=1)
        assert result == set()


# ---------------------------------------------------------------------------
# _chunkify (same logic as compute_track_traits, smoke-tested here)
# ---------------------------------------------------------------------------


class TestChunkifyCosine:
    def test_even_split(self):
        result = _chunkify([1, 2, 3, 4], 2)
        assert len(result) == 2

    def test_empty_list(self):
        assert _chunkify([], 3) == []

    def test_all_items_present(self):
        items = list(range(15))
        chunks = _chunkify(items, 4)
        assert sorted(x for c in chunks for x in c) == items


# ---------------------------------------------------------------------------
# Combined orchestration (compute_features_for_tracks)
# ---------------------------------------------------------------------------


class TestComputeFeaturesForTracks:
    @patch(
        "src.scripts.feature_extraction.compute_features_for_tracks"
        ".compute_cosine_similarities"
    )
    @patch(
        "src.scripts.feature_extraction.compute_features_for_tracks"
        ".compute_track_traits"
    )
    @patch("src.scripts.feature_extraction.compute_features_for_tracks.database")
    def test_calls_traits_then_cosine(self, mock_db, mock_traits, mock_cosine):
        from src.scripts.feature_extraction.compute_features_for_tracks import run

        mock_session = MagicMock()
        mock_db.create_session.return_value = mock_session

        call_order = []
        mock_traits.run.side_effect = lambda *a, **kw: call_order.append("traits")
        mock_cosine.run.side_effect = lambda *a, **kw: call_order.append("cosine")

        run({42, 101})
        assert call_order == ["traits", "cosine"]

    @patch(
        "src.scripts.feature_extraction.compute_features_for_tracks"
        ".compute_cosine_similarities"
    )
    @patch(
        "src.scripts.feature_extraction.compute_features_for_tracks"
        ".compute_track_traits"
    )
    @patch("src.scripts.feature_extraction.compute_features_for_tracks.database")
    def test_continues_on_trait_failure(self, mock_db, mock_traits, mock_cosine):
        from src.scripts.feature_extraction.compute_features_for_tracks import run

        mock_session = MagicMock()
        mock_db.create_session.return_value = mock_session
        mock_traits.run.side_effect = RuntimeError("trait crash")

        run({42})
        mock_cosine.run.assert_called_once()

    def test_requires_track_ids(self):
        from src.scripts.feature_extraction.compute_features_for_tracks import run

        with pytest.raises(SystemExit):
            run(set())


# ---------------------------------------------------------------------------
# Finding 1: batch selection must not skip candidate-only tracks
# ---------------------------------------------------------------------------


class TestGetTracksForProcessing:
    def test_explicit_ids_returned_sorted(self):
        mock_session = MagicMock()
        result = _get_tracks_for_processing({30, 10, 20}, mock_session)
        assert result == [10, 20, 30]
        mock_session.query.assert_not_called()

    def test_batch_mode_returns_all_descriptor_tracks(self):
        mock_session = MagicMock()
        desc_rows = [
            MagicMock(track_id=10),
            MagicMock(track_id=20),
            MagicMock(track_id=30),
        ]
        mock_session.query.return_value.filter_by.return_value.all.return_value = (
            desc_rows
        )
        result = _get_tracks_for_processing(set(), mock_session)
        assert result == [10, 20, 30]

    def test_batch_mode_does_not_query_cosine_table(self):
        """Batch selection should rely on descriptors only, not the cosine table."""
        mock_session = MagicMock()
        mock_session.query.return_value.filter_by.return_value.all.return_value = [
            MagicMock(track_id=10)
        ]
        _get_tracks_for_processing(set(), mock_session)
        calls = mock_session.query.call_args_list
        assert len(calls) == 1

    def test_batch_mode_filters_by_current_descriptor_version(self):
        """Batch selection must filter descriptors by DESCRIPTOR_VERSION so that
        a version bump causes all tracks to be reprocessed (Finding 2)."""
        mock_session = MagicMock()
        mock_session.query.return_value.filter_by.return_value.all.return_value = [
            MagicMock(track_id=10)
        ]
        _get_tracks_for_processing(set(), mock_session)
        mock_session.query.return_value.filter_by.assert_called_once_with(
            descriptor_version=DESCRIPTOR_VERSION
        )

    def test_candidate_only_track_still_selected_in_batch(self):
        """A track that only appeared as id2 (candidate) in existing cosine rows
        must still be selected as a source track, because batch selection relies
        on descriptors — never the cosine table (Finding 1)."""
        mock_session = MagicMock()
        mock_session.query.return_value.filter_by.return_value.all.return_value = [
            MagicMock(track_id=10),
            MagicMock(track_id=20),
        ]
        result = _get_tracks_for_processing(set(), mock_session)
        assert result == [10, 20]
        assert mock_session.query.call_count == 1

    def test_empty_ids_triggers_batch_mode(self):
        mock_session = MagicMock()
        mock_session.query.return_value.filter_by.return_value.all.return_value = []
        result = _get_tracks_for_processing(set(), mock_session)
        assert result == []
        mock_session.query.assert_called_once()


# ---------------------------------------------------------------------------
# Finding 2: descriptor-version-aware pair checks
# ---------------------------------------------------------------------------


class TestClassifyExistingPairs:
    def test_current_version_pair_classified_as_existing(self):
        row = TrackCosineSimilarity(
            id1=1, id2=2, cosine_similarity=0.8, descriptor_version=DESCRIPTOR_VERSION
        )
        existing, stale = _classify_existing_pairs([row], DESCRIPTOR_VERSION)
        assert (1, 2) in existing
        assert (1, 2) not in stale

    def test_stale_version_pair_classified_as_stale(self):
        row = TrackCosineSimilarity(
            id1=1, id2=2, cosine_similarity=0.5, descriptor_version="0"
        )
        existing, stale = _classify_existing_pairs([row], DESCRIPTOR_VERSION)
        assert (1, 2) not in existing
        assert (1, 2) in stale

    def test_mixed_versions_separated_correctly(self):
        rows = [
            TrackCosineSimilarity(
                id1=1, id2=2, cosine_similarity=0.5, descriptor_version="0"
            ),
            TrackCosineSimilarity(
                id1=1,
                id2=3,
                cosine_similarity=0.9,
                descriptor_version=DESCRIPTOR_VERSION,
            ),
            TrackCosineSimilarity(
                id1=4, id2=5, cosine_similarity=0.3, descriptor_version="old"
            ),
        ]
        existing, stale = _classify_existing_pairs(rows, DESCRIPTOR_VERSION)
        assert existing == {(1, 3)}
        assert stale == {(1, 2), (4, 5)}

    def test_version_bump_marks_all_old_pairs_stale(self):
        """After a descriptor version bump, all rows from the old version
        must be classified as stale to trigger recomputation (Finding 2)."""
        rows = [
            TrackCosineSimilarity(
                id1=1, id2=2, cosine_similarity=0.8, descriptor_version="1"
            ),
            TrackCosineSimilarity(
                id1=1, id2=3, cosine_similarity=0.7, descriptor_version="1"
            ),
        ]
        existing, stale = _classify_existing_pairs(rows, "2")
        assert existing == set()
        assert stale == {(1, 2), (1, 3)}

    def test_empty_rows_returns_empty_sets(self):
        existing, stale = _classify_existing_pairs([], DESCRIPTOR_VERSION)
        assert existing == set()
        assert stale == set()
