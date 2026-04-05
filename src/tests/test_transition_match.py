"""Tests for transition match scoring, factor computation, and self-exclusion.

Run with:
    python -m pytest src/tests/test_transition_match.py -v
"""

from collections import defaultdict
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from src.data_management.config import TrackDBCols
from src.harmonic_mixing.config import (
    CamelotPriority,
    CollectionStat,
    MatchFactors,
)
from src.harmonic_mixing.transition_match import TransitionMatch, jsonb_cosine_similarity


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_BASE_TIME = datetime(2024, 1, 1)
_COLLECTION_MD = {
    CollectionStat.OLDEST: _BASE_TIME,
    CollectionStat.NEWEST: _BASE_TIME + timedelta(days=365),
    CollectionStat.TIME_RANGE: timedelta(days=365),
}


def _make_md(track_id, title="Track", bpm=128.0, energy=7,
             camelot_code="08A", date_added=None):
    md = {
        TrackDBCols.ID: track_id,
        TrackDBCols.TITLE: title,
        TrackDBCols.BPM: bpm,
        TrackDBCols.CAMELOT_CODE: camelot_code,
        TrackDBCols.ENERGY: energy,
        TrackDBCols.FILE_NAME: f"track_{track_id}.mp3",
    }
    if date_added is not None:
        md[TrackDBCols.DATE_ADDED] = date_added
    return md


def _make_trait(voice_instrumental=0.3, danceability=0.7, bright_dark=0.5,
                genre=None, mood_theme=None, instruments=None):
    trait = MagicMock()
    trait.voice_instrumental = voice_instrumental
    trait.danceability = danceability
    trait.bright_dark = bright_dark
    trait.genre = genre if genre is not None else {"house": 0.8, "techno": 0.2}
    trait.mood_theme = mood_theme if mood_theme is not None else {"energetic": 0.7, "dark": 0.3}
    trait.instruments = instruments if instruments is not None else {"synth": 0.9, "drums": 0.8}
    return trait


class _MatchFixture:
    """Context manager that sets TransitionMatch class state for testing."""

    def __init__(self, collection_md=None):
        self._collection_md = collection_md or _COLLECTION_MD
        self._originals = {}

    def __enter__(self):
        self._originals = {
            "collection_metadata": TransitionMatch.collection_metadata,
            "db_session": TransitionMatch.db_session,
            "cosine_cache": TransitionMatch.cosine_cache,
            "effective_weights": TransitionMatch.effective_weights,
            "od_desc": TransitionMatch._on_deck_descriptor_cache.copy(),
            "cd_desc": TransitionMatch._candidate_descriptor_cache.copy(),
            "od_trait": TransitionMatch._on_deck_trait_cache.copy(),
            "cd_trait": TransitionMatch._candidate_trait_cache.copy(),
        }
        TransitionMatch.collection_metadata = self._collection_md
        TransitionMatch.db_session = MagicMock()
        TransitionMatch.cosine_cache = None
        TransitionMatch.effective_weights = None
        TransitionMatch._on_deck_descriptor_cache.clear()
        TransitionMatch._candidate_descriptor_cache.clear()
        TransitionMatch._on_deck_trait_cache.clear()
        TransitionMatch._candidate_trait_cache.clear()
        return self

    def __exit__(self, *exc):
        TransitionMatch.collection_metadata = self._originals["collection_metadata"]
        TransitionMatch.db_session = self._originals["db_session"]
        TransitionMatch.cosine_cache = self._originals["cosine_cache"]
        TransitionMatch.effective_weights = self._originals["effective_weights"]
        TransitionMatch._on_deck_descriptor_cache = self._originals["od_desc"]
        TransitionMatch._candidate_descriptor_cache = self._originals["cd_desc"]
        TransitionMatch._on_deck_trait_cache = self._originals["od_trait"]
        TransitionMatch._candidate_trait_cache = self._originals["cd_trait"]

    def seed_traits(self, track_id, trait):
        TransitionMatch._on_deck_trait_cache[track_id] = trait
        TransitionMatch._candidate_trait_cache[track_id] = trait


# ---------------------------------------------------------------------------
# 1. jsonb_cosine_similarity
# ---------------------------------------------------------------------------

class TestJsonbCosineSimilarity:
    def test_identical_dict_returns_one(self):
        d = {"house": 0.8, "techno": 0.2}
        assert jsonb_cosine_similarity(d, d) == pytest.approx(1.0, abs=1e-7)

    def test_empty_dict_returns_zero(self):
        assert jsonb_cosine_similarity({}, {"a": 1.0}) == 0.0
        assert jsonb_cosine_similarity({"a": 1.0}, {}) == 0.0
        assert jsonb_cosine_similarity({}, {}) == 0.0

    def test_disjoint_keys_returns_zero(self):
        assert jsonb_cosine_similarity({"a": 1.0}, {"b": 1.0}) == 0.0

    def test_partial_overlap(self):
        d1 = {"house": 0.8, "techno": 0.2}
        d2 = {"house": 0.6, "trance": 0.4}
        sim = jsonb_cosine_similarity(d1, d2)
        assert 0.0 < sim < 1.0

    def test_symmetric(self):
        d1 = {"a": 0.5, "b": 0.3}
        d2 = {"b": 0.7, "c": 0.2}
        assert jsonb_cosine_similarity(d1, d2) == pytest.approx(
            jsonb_cosine_similarity(d2, d1), abs=1e-7
        )


# ---------------------------------------------------------------------------
# 2. Same-track factor values (metadata-only factors)
# ---------------------------------------------------------------------------

class TestSameTrackMetadataFactors:
    """Factors that depend only on track metadata dicts, not trait DB lookups."""

    def test_same_bpm_returns_one(self):
        with _MatchFixture():
            md = _make_md(1, bpm=128.0)
            match = TransitionMatch(md, md, CamelotPriority.SAME_KEY)
            assert match.get_bpm_score() == pytest.approx(1.0)

    def test_same_energy_returns_one(self):
        with _MatchFixture():
            md = _make_md(1, energy=7)
            match = TransitionMatch(md, md, CamelotPriority.SAME_KEY)
            assert match.get_energy_score() == pytest.approx(1.0)

    def test_same_key_camelot_priority(self):
        with _MatchFixture():
            md = _make_md(1)
            match = TransitionMatch(md, md, CamelotPriority.SAME_KEY.value)
            assert match.get_camelot_priority_score() == pytest.approx(1.0)

    def test_camelot_enum_alias_takes_major_minor_branch(self):
        """SAME_KEY aliases MAJOR_MINOR_JUMP in the enum; passing the enum
        object (not .value) hits the MAJOR_MINOR_JUMP branch → 0.9."""
        with _MatchFixture():
            md = _make_md(1)
            match = TransitionMatch(md, md, CamelotPriority.SAME_KEY)
            assert match.get_camelot_priority_score() == pytest.approx(0.9)


# ---------------------------------------------------------------------------
# 3. Same-track trait-based factor values
# ---------------------------------------------------------------------------

class TestSameTrackTraitFactors:
    """Factors backed by TrackTrait DB lookups — mock the trait cache."""

    def test_same_genre_similarity_returns_one(self):
        with _MatchFixture() as fx:
            trait = _make_trait(genre={"house": 0.8, "techno": 0.2})
            fx.seed_traits(1, trait)
            md = _make_md(1)
            match = TransitionMatch(md, md, CamelotPriority.SAME_KEY)
            assert match.get_genre_similarity_score() == pytest.approx(1.0, abs=1e-6)

    def test_same_mood_continuity_returns_one(self):
        with _MatchFixture() as fx:
            trait = _make_trait(mood_theme={"energetic": 0.7, "dark": 0.3})
            fx.seed_traits(1, trait)
            md = _make_md(1)
            match = TransitionMatch(md, md, CamelotPriority.SAME_KEY)
            assert match.get_mood_continuity_score() == pytest.approx(1.0, abs=1e-6)

    def test_same_instrument_similarity_returns_one(self):
        with _MatchFixture() as fx:
            trait = _make_trait(instruments={"synth": 0.9, "drums": 0.8})
            fx.seed_traits(1, trait)
            md = _make_md(1)
            match = TransitionMatch(md, md, CamelotPriority.SAME_KEY)
            assert match.get_instrument_similarity_score() == pytest.approx(1.0, abs=1e-6)

    def test_same_danceability_returns_one(self):
        with _MatchFixture() as fx:
            trait = _make_trait(danceability=0.7)
            fx.seed_traits(1, trait)
            md = _make_md(1)
            match = TransitionMatch(md, md, CamelotPriority.SAME_KEY)
            assert match.get_danceability_score() == pytest.approx(1.0)

    def test_same_timbre_returns_one(self):
        with _MatchFixture() as fx:
            trait = _make_trait(bright_dark=0.6)
            fx.seed_traits(1, trait)
            md = _make_md(1)
            match = TransitionMatch(md, md, CamelotPriority.SAME_KEY)
            assert match.get_timbre_score() == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# 4. Vocal clash penalty semantics
# ---------------------------------------------------------------------------

class TestVocalClashSemantics:
    """vocal_clash_score is a penalty: 1.0 = no clash, ~0.0 = heavy clash."""

    def test_two_instrumentals_score_one(self):
        with _MatchFixture() as fx:
            trait = _make_trait(voice_instrumental=0.0)
            fx.seed_traits(1, trait)
            fx.seed_traits(2, trait)
            md_a = _make_md(1)
            md_b = _make_md(2)
            match = TransitionMatch(md_b, md_a, CamelotPriority.SAME_KEY)
            assert match.get_vocal_clash_score() == pytest.approx(1.0)

    def test_two_vocals_score_low(self):
        with _MatchFixture() as fx:
            trait = _make_trait(voice_instrumental=0.9)
            fx.seed_traits(1, trait)
            fx.seed_traits(2, trait)
            md_a = _make_md(1)
            md_b = _make_md(2)
            match = TransitionMatch(md_b, md_a, CamelotPriority.SAME_KEY)
            assert match.get_vocal_clash_score() == pytest.approx(0.1, abs=1e-6)

    def test_mixed_vocal_instrumental(self):
        with _MatchFixture() as fx:
            vocal_trait = _make_trait(voice_instrumental=0.8)
            inst_trait = _make_trait(voice_instrumental=0.1)
            fx.seed_traits(1, vocal_trait)
            fx.seed_traits(2, inst_trait)
            md_a = _make_md(1)
            md_b = _make_md(2)
            match = TransitionMatch(md_b, md_a, CamelotPriority.SAME_KEY)
            # min(0.8, 0.1) = 0.1 → score = 0.9
            assert match.get_vocal_clash_score() == pytest.approx(0.9, abs=1e-6)


# ---------------------------------------------------------------------------
# 5. Source-track exclusion from candidates
# ---------------------------------------------------------------------------

class TestSourceTrackExclusion:
    """The canonical finder path must exclude the source track by ID."""

    def test_self_excluded_from_same_key_matches(self):
        from src.harmonic_mixing.transition_match_finder import TransitionMatchFinder

        source_md = _make_md(42, title="Source Track", bpm=128.0, camelot_code="08A")
        other_md = _make_md(99, title="Other Track", bpm=128.0, camelot_code="08A")

        camelot_map = defaultdict(lambda: defaultdict(list))
        camelot_map["08A"][128.0] = [source_md, other_md]

        finder = object.__new__(TransitionMatchFinder)
        finder.camelot_map = camelot_map

        with _MatchFixture():
            harmonic_codes = [(8, "A", CamelotPriority.SAME_KEY.value)]
            same_key, higher_key, lower_key = finder._get_matches_for_code(
                harmonic_codes, source_md, sort_results=False
            )

            candidate_ids = [m.metadata[TrackDBCols.ID] for m in same_key]
            assert 42 not in candidate_ids
            assert 99 in candidate_ids

    def test_self_excluded_across_all_buckets(self):
        from src.harmonic_mixing.transition_match_finder import TransitionMatchFinder
        from src.harmonic_mixing.utils import format_camelot_number

        source_md = _make_md(10, bpm=128.0, camelot_code="08A")

        camelot_map = defaultdict(lambda: defaultdict(list))
        for code_num in range(1, 13):
            for letter in ("A", "B"):
                code = format_camelot_number(code_num) + letter
                camelot_map[code][128.0] = [
                    source_md,
                    _make_md(code_num * 100, bpm=128.0, camelot_code=code),
                ]

        finder = object.__new__(TransitionMatchFinder)
        finder.camelot_map = camelot_map

        with _MatchFixture():
            from src.harmonic_mixing.transition_match_finder import TransitionMatchFinder
            harmonic_codes = TransitionMatchFinder._get_all_harmonic_codes(source_md)
            same_key, higher_key, lower_key = finder._get_matches_for_code(
                harmonic_codes, source_md, sort_results=False
            )

            all_ids = [m.metadata[TrackDBCols.ID] for m in same_key + higher_key + lower_key]
            assert 10 not in all_ids


# ---------------------------------------------------------------------------
# 6. Non-self scoring sanity
# ---------------------------------------------------------------------------

class TestNonSelfScoring:
    """A non-self match with known metadata produces a plausible score."""

    def test_close_bpm_different_track(self):
        with _MatchFixture() as fx:
            trait_a = _make_trait(danceability=0.7, bright_dark=0.5, voice_instrumental=0.1)
            trait_b = _make_trait(danceability=0.75, bright_dark=0.55, voice_instrumental=0.2)
            fx.seed_traits(1, trait_a)
            fx.seed_traits(2, trait_b)

            TransitionMatch.db_session.query.return_value.filter_by.return_value.first.return_value = None
            TransitionMatch.cosine_cache = None

            md_a = _make_md(1, title="Track A", bpm=128.0, energy=7,
                            date_added=_BASE_TIME + timedelta(days=180))
            md_b = _make_md(2, title="Track B", bpm=129.0, energy=6,
                            date_added=_BASE_TIME + timedelta(days=200))

            match = TransitionMatch(md_b, md_a, CamelotPriority.SAME_KEY)
            score = match.get_score()

            assert score > 0
            assert match.factors[MatchFactors.BPM] > 0.5
            assert match.factors[MatchFactors.ENERGY] > 0.5
            assert match.factors[MatchFactors.DANCEABILITY] > 0.5
            assert match.factors[MatchFactors.TIMBRE] > 0.5

    def test_factors_dict_populated_after_get_score(self):
        """get_score() must populate self.factors for all factor types."""
        with _MatchFixture() as fx:
            trait = _make_trait()
            fx.seed_traits(1, trait)
            fx.seed_traits(2, trait)

            TransitionMatch.db_session.query.return_value.filter_by.return_value.first.return_value = None

            md_a = _make_md(1, title="A", bpm=128.0, energy=7,
                            date_added=_BASE_TIME + timedelta(days=100))
            md_b = _make_md(2, title="B", bpm=130.0, energy=6,
                            date_added=_BASE_TIME + timedelta(days=200))

            match = TransitionMatch(md_b, md_a, CamelotPriority.SAME_KEY)
            match.get_score()

            expected_factors = {
                MatchFactors.BPM, MatchFactors.CAMELOT, MatchFactors.ENERGY,
                MatchFactors.FRESHNESS, MatchFactors.SIMILARITY,
                MatchFactors.GENRE_SIMILARITY, MatchFactors.MOOD_CONTINUITY,
                MatchFactors.VOCAL_CLASH, MatchFactors.DANCEABILITY,
                MatchFactors.TIMBRE, MatchFactors.INSTRUMENT_SIMILARITY,
            }
            assert set(match.factors.keys()) == expected_factors


# ---------------------------------------------------------------------------
# 7. DB-backed score retrieval
# ---------------------------------------------------------------------------


class TestDBBackedScoreRetrieval:
    """Score retrieval must check DB before computing from descriptors."""

    def test_db_hit_returns_persisted_value(self):
        """When DB has the similarity row, it should be returned directly."""
        with _MatchFixture():
            db_row = MagicMock()
            db_row.cosine_similarity = 0.77

            def filter_by_side_effect(**kwargs):
                mock_filtered = MagicMock()
                if "id1" in kwargs and "id2" in kwargs:
                    mock_filtered.first.return_value = db_row
                else:
                    mock_filtered.first.return_value = None
                return mock_filtered

            TransitionMatch.db_session.query.return_value.filter_by.side_effect = (
                filter_by_side_effect
            )

            md_a = _make_md(100, title="A")
            md_b = _make_md(200, title="B")
            match = TransitionMatch(md_b, md_a, CamelotPriority.SAME_KEY)

            with patch.object(TransitionMatch, "_persist_similarity"):
                result = match.get_similarity_score()

            assert result == 0.77
            assert match.factors[MatchFactors.SIMILARITY] == 0.77

    def test_db_hit_warms_cache(self):
        """DB hit should place the value into the in-memory cache."""
        from src.harmonic_mixing.cosine_cache import CosineCache

        cache = CosineCache()
        with _MatchFixture():
            TransitionMatch.cosine_cache = cache
            db_row = MagicMock()
            db_row.cosine_similarity = 0.65

            def filter_by_side_effect(**kwargs):
                mock_filtered = MagicMock()
                if "id1" in kwargs and "id2" in kwargs:
                    mock_filtered.first.return_value = db_row
                else:
                    mock_filtered.first.return_value = None
                return mock_filtered

            TransitionMatch.db_session.query.return_value.filter_by.side_effect = (
                filter_by_side_effect
            )

            md_a = _make_md(100, title="A")
            md_b = _make_md(200, title="B")
            match = TransitionMatch(md_b, md_a, CamelotPriority.SAME_KEY)

            with patch.object(TransitionMatch, "_persist_similarity"):
                match.get_similarity_score()

            assert cache.get(100, 200) == 0.65

    @patch.object(TransitionMatch, "_persist_similarity")
    def test_db_miss_computes_and_persists(self, mock_persist):
        """On DB miss, score is computed from descriptors and persisted."""
        import numpy as np

        with _MatchFixture():
            mock_desc = MagicMock()
            mock_desc.global_vector = np.ones(75, dtype=np.float32).tobytes()

            TransitionMatch.db_session.query.return_value.filter_by.return_value.first.return_value = None

            TransitionMatch._on_deck_descriptor_cache.clear()
            TransitionMatch._candidate_descriptor_cache.clear()

            md_a = _make_md(300, title="A")
            md_b = _make_md(400, title="B")

            call_count = {"n": 0}

            def filter_by_side_effect(**kwargs):
                call_count["n"] += 1
                mock_filtered = MagicMock()
                if "track_id" in kwargs:
                    mock_filtered.first.return_value = mock_desc
                else:
                    mock_filtered.first.return_value = None
                return mock_filtered

            TransitionMatch.db_session.query.return_value.filter_by.side_effect = (
                filter_by_side_effect
            )

            match = TransitionMatch(md_b, md_a, CamelotPriority.SAME_KEY)
            result = match.get_similarity_score()

            assert result > 0
            mock_persist.assert_called_once()
            args = mock_persist.call_args[0]
            assert min(args[0], args[1]) == 300
            assert max(args[0], args[1]) == 400

    def test_symmetric_pair_lookup_uses_canonical_order(self):
        """Swapped IDs must produce the same canonical DB lookup."""
        with _MatchFixture():
            db_row = MagicMock()
            db_row.cosine_similarity = 0.55

            filter_by_calls = []

            def filter_by_side_effect(**kwargs):
                filter_by_calls.append(kwargs)
                mock_filtered = MagicMock()
                if "id1" in kwargs:
                    mock_filtered.first.return_value = db_row
                else:
                    mock_filtered.first.return_value = None
                return mock_filtered

            TransitionMatch.db_session.query.return_value.filter_by.side_effect = (
                filter_by_side_effect
            )

            md_a = _make_md(500, title="A")
            md_b = _make_md(300, title="B")
            match = TransitionMatch(md_b, md_a, CamelotPriority.SAME_KEY)

            with patch.object(TransitionMatch, "_persist_similarity"):
                match.get_similarity_score()

            db_lookup = [c for c in filter_by_calls if "id1" in c]
            assert len(db_lookup) >= 1
            assert db_lookup[0]["id1"] == 300
            assert db_lookup[0]["id2"] == 500


# ---------------------------------------------------------------------------
# 7b. Descriptor-missing fallback must not persist stale zeros
# ---------------------------------------------------------------------------


class TestDescriptorMissingNoPersist:
    """When descriptors are absent, 0.0 is returned as the factor but must NOT
    be persisted or cached — otherwise backfilled descriptors would never
    trigger recomputation."""

    @patch.object(TransitionMatch, "_persist_similarity")
    def test_missing_descriptors_not_persisted(self, mock_persist):
        with _MatchFixture():
            TransitionMatch.db_session.query.return_value.filter_by.return_value.first.return_value = None
            TransitionMatch._on_deck_descriptor_cache.clear()
            TransitionMatch._candidate_descriptor_cache.clear()

            md_a = _make_md(600, title="A")
            md_b = _make_md(700, title="B")

            match = TransitionMatch(md_b, md_a, CamelotPriority.SAME_KEY)
            result = match.get_similarity_score()

            assert result == 0.0
            assert match.factors[MatchFactors.SIMILARITY] == 0.0
            mock_persist.assert_not_called()

    def test_missing_descriptors_not_cached(self):
        from src.harmonic_mixing.cosine_cache import CosineCache

        cache = CosineCache()
        with _MatchFixture():
            TransitionMatch.cosine_cache = cache
            TransitionMatch.db_session.query.return_value.filter_by.return_value.first.return_value = None
            TransitionMatch._on_deck_descriptor_cache.clear()
            TransitionMatch._candidate_descriptor_cache.clear()

            md_a = _make_md(600, title="A")
            md_b = _make_md(700, title="B")

            match = TransitionMatch(md_b, md_a, CamelotPriority.SAME_KEY)
            result = match.get_similarity_score()

            assert result == 0.0
            assert cache.get(600, 700) is None


# ---------------------------------------------------------------------------
# 8. Effective weight override in scoring
# ---------------------------------------------------------------------------


class TestEffectiveWeightOverride:
    def test_effective_weights_used_when_set(self):
        """When effective_weights is set, get_score uses them."""
        with _MatchFixture() as fx:
            trait = _make_trait()
            fx.seed_traits(1, trait)
            fx.seed_traits(2, trait)

            TransitionMatch.db_session.query.return_value.filter_by.return_value.first.return_value = None

            custom_weights = {f.name: 0.0 for f in MatchFactors}
            custom_weights[MatchFactors.BPM.name] = 1.0
            TransitionMatch.effective_weights = custom_weights

            md_a = _make_md(1, title="A", bpm=128.0, energy=7,
                            date_added=_BASE_TIME + timedelta(days=100))
            md_b = _make_md(2, title="B", bpm=128.0, energy=6,
                            date_added=_BASE_TIME + timedelta(days=200))

            match = TransitionMatch(md_b, md_a, CamelotPriority.SAME_KEY)
            score = match.get_score()

            assert score == pytest.approx(100 * 1.0 * match.factors[MatchFactors.BPM])

    def test_none_effective_weights_falls_back_to_config(self):
        """When effective_weights is None, MATCH_WEIGHTS from config is used."""
        from src.harmonic_mixing.config import MATCH_WEIGHTS as cfg_weights

        with _MatchFixture() as fx:
            trait = _make_trait()
            fx.seed_traits(1, trait)
            fx.seed_traits(2, trait)

            TransitionMatch.db_session.query.return_value.filter_by.return_value.first.return_value = None
            TransitionMatch.effective_weights = None

            md_a = _make_md(1, title="A", bpm=128.0, energy=7,
                            date_added=_BASE_TIME + timedelta(days=100))
            md_b = _make_md(2, title="B", bpm=128.0, energy=6,
                            date_added=_BASE_TIME + timedelta(days=200))

            match = TransitionMatch(md_b, md_a, CamelotPriority.SAME_KEY)
            score = match.get_score()

            expected = 100 * sum(
                match.factors[f] * cfg_weights[f.name] for f in MatchFactors
            )
            assert score == pytest.approx(expected, abs=0.01)


# ---------------------------------------------------------------------------
# 9. TrackTrait participation in scoring — canary tests
# ---------------------------------------------------------------------------

class TestTraitParticipationInScoring:
    """Prove TrackTrait data is consumed by the active scoring path.

    These tests would FAIL if trait-backed factors were removed, bypassed,
    or hardcoded to a constant.
    """

    TRAIT_FACTORS = {
        MatchFactors.GENRE_SIMILARITY,
        MatchFactors.MOOD_CONTINUITY,
        MatchFactors.VOCAL_CLASH,
        MatchFactors.DANCEABILITY,
        MatchFactors.TIMBRE,
        MatchFactors.INSTRUMENT_SIMILARITY,
    }

    def test_all_trait_factors_zero_without_traits(self):
        """When no TrackTrait rows exist, every trait-backed factor is 0.0."""
        with _MatchFixture():
            TransitionMatch.db_session.query.return_value.filter_by.return_value.first.return_value = None

            md_a = _make_md(1, title="A", bpm=128.0, energy=7,
                            date_added=_BASE_TIME + timedelta(days=100))
            md_b = _make_md(2, title="B", bpm=129.0, energy=6,
                            date_added=_BASE_TIME + timedelta(days=200))

            match = TransitionMatch(md_b, md_a, CamelotPriority.SAME_KEY)
            match.get_score()

            for factor in self.TRAIT_FACTORS:
                assert match.factors[factor] == 0.0, (
                    f"{factor.name} should be 0.0 without traits"
                )

    def test_trait_factors_nonzero_with_traits(self):
        """When TrackTrait rows are present, trait-backed factors produce
        non-zero scores — proving real data consumption."""
        with _MatchFixture() as fx:
            trait_a = _make_trait(
                voice_instrumental=0.2,
                danceability=0.7,
                bright_dark=0.5,
                genre={"house": 0.8, "techno": 0.2},
                mood_theme={"energetic": 0.7, "dark": 0.3},
                instruments={"synth": 0.9, "drums": 0.8},
            )
            trait_b = _make_trait(
                voice_instrumental=0.3,
                danceability=0.75,
                bright_dark=0.55,
                genre={"house": 0.6, "trance": 0.4},
                mood_theme={"energetic": 0.5, "happy": 0.5},
                instruments={"synth": 0.7, "bass guitar": 0.5},
            )
            fx.seed_traits(1, trait_a)
            fx.seed_traits(2, trait_b)

            TransitionMatch.db_session.query.return_value.filter_by.return_value.first.return_value = None

            md_a = _make_md(1, title="A", bpm=128.0, energy=7,
                            date_added=_BASE_TIME + timedelta(days=100))
            md_b = _make_md(2, title="B", bpm=129.0, energy=6,
                            date_added=_BASE_TIME + timedelta(days=200))

            match = TransitionMatch(md_b, md_a, CamelotPriority.SAME_KEY)
            match.get_score()

            for factor in self.TRAIT_FACTORS:
                assert match.factors[factor] > 0.0, (
                    f"{factor.name} should be > 0.0 with trait data present"
                )

    def test_total_score_higher_with_traits_than_without(self):
        """The weighted total score must increase when TrackTrait data is
        present, proving traits contribute to the final output."""
        with _MatchFixture():
            TransitionMatch.db_session.query.return_value.filter_by.return_value.first.return_value = None

            md_a = _make_md(1, title="A", bpm=128.0, energy=7,
                            date_added=_BASE_TIME + timedelta(days=100))
            md_b = _make_md(2, title="B", bpm=129.0, energy=6,
                            date_added=_BASE_TIME + timedelta(days=200))

            match_no_traits = TransitionMatch(md_b, md_a, CamelotPriority.SAME_KEY)
            score_without = match_no_traits.get_score()

        with _MatchFixture() as fx:
            trait = _make_trait(
                voice_instrumental=0.1,
                danceability=0.7,
                bright_dark=0.5,
                genre={"house": 0.8},
                mood_theme={"energetic": 0.7},
                instruments={"synth": 0.9},
            )
            fx.seed_traits(1, trait)
            fx.seed_traits(2, trait)

            TransitionMatch.db_session.query.return_value.filter_by.return_value.first.return_value = None

            md_a = _make_md(1, title="A", bpm=128.0, energy=7,
                            date_added=_BASE_TIME + timedelta(days=100))
            md_b = _make_md(2, title="B", bpm=129.0, energy=6,
                            date_added=_BASE_TIME + timedelta(days=200))

            match_with_traits = TransitionMatch(md_b, md_a, CamelotPriority.SAME_KEY)
            score_with = match_with_traits.get_score()

        assert score_with > score_without, (
            f"Score with traits ({score_with}) must exceed score without ({score_without})"
        )


# ---------------------------------------------------------------------------
# 10. TrackTrait version filtering
# ---------------------------------------------------------------------------

class TestTraitVersionFiltering:
    """Verify that trait DB lookups use TRAIT_VERSION for row filtering."""

    def test_trait_lookup_filters_by_version(self):
        """The DB query for TrackTrait must include trait_version == TRAIT_VERSION."""
        from src.feature_extraction.config import TRAIT_VERSION

        with _MatchFixture():
            mock_filter = TransitionMatch.db_session.query.return_value.filter_by
            mock_filter.return_value.first.return_value = None

            md_a = _make_md(1, title="A")
            md_b = _make_md(2, title="B")
            match = TransitionMatch(md_b, md_a, CamelotPriority.SAME_KEY)

            match.get_genre_similarity_score()

            version_filtered = [
                c for c in mock_filter.call_args_list
                if c.kwargs.get("trait_version") == TRAIT_VERSION
            ]
            assert len(version_filtered) >= 1, (
                f"Expected filter_by(trait_version={TRAIT_VERSION!r}), "
                f"got: {mock_filter.call_args_list}"
            )

    def test_all_six_trait_scorers_return_zero_when_trait_missing(self):
        """Each trait scorer independently returns 0.0 when no TrackTrait
        row is found — confirming no scorer has a hardcoded bypass."""
        with _MatchFixture():
            TransitionMatch.db_session.query.return_value.filter_by.return_value.first.return_value = None

            md_a = _make_md(1, title="A")
            md_b = _make_md(2, title="B")
            match = TransitionMatch(md_b, md_a, CamelotPriority.SAME_KEY)

            assert match.get_genre_similarity_score() == 0.0
            assert match.get_mood_continuity_score() == 0.0
            assert match.get_vocal_clash_score() == 0.0
            assert match.get_danceability_score() == 0.0
            assert match.get_timbre_score() == 0.0
            assert match.get_instrument_similarity_score() == 0.0
