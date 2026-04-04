import logging

import numpy as np

from src.models.track_descriptor import TrackDescriptor
from src.models.track_cosine_similarity import TrackCosineSimilarity
from src.models.track_trait import TrackTrait
from src.data_management.config import TrackDBCols
from src.feature_extraction.config import DESCRIPTOR_VERSION, TRAIT_VERSION
from src.feature_extraction.trait_extractor import (
    filter_genre,
    filter_instruments,
    filter_mood,
)
from src.harmonic_mixing.config import (
    SAME_LOWER_BOUND,
    SAME_UPPER_BOUND,
    UP_KEY_LOWER_BOUND,
    UP_KEY_UPPER_BOUND,
    DOWN_KEY_LOWER_BOUND,
    DOWN_KEY_UPPER_BOUND,
    CamelotPriority,
    CollectionStat,
    MATCH_WEIGHTS,
    MatchFactors,
)
from src.feature_extraction.compact_descriptor import compute_similarity, unpack_vector

logger = logging.getLogger(__name__)


def jsonb_cosine_similarity(d1: dict, d2: dict) -> float:
    """Cosine similarity between two sparse {label: probability} dicts."""
    if not d1 or not d2:
        return 0.0
    keys = set(d1) | set(d2)
    v1 = np.array([d1.get(k, 0.0) for k in keys])
    v2 = np.array([d2.get(k, 0.0) for k in keys])
    norm1, norm2 = np.linalg.norm(v1), np.linalg.norm(v2)
    if norm1 == 0.0 or norm2 == 0.0:
        return 0.0
    return max(0.0, float(np.dot(v1, v2) / (norm1 * norm2)))


class TransitionMatch:
    """Encapsulates a transition match from current track to next track."""

    collection_metadata = None
    db_session = None
    cosine_cache = None
    effective_weights = None
    _on_deck_descriptor_cache = {}
    _candidate_descriptor_cache = {}
    _on_deck_trait_cache = {}
    _candidate_trait_cache = {}
    result_column_header = "   ".join(["Total Score", "Cos Sim", " Track"])

    @classmethod
    def clear_descriptor_caches(cls):
        """Clear per-session caches. Call before each new track query."""
        cls._on_deck_descriptor_cache.clear()
        cls._candidate_descriptor_cache.clear()
        cls._on_deck_trait_cache.clear()
        cls._candidate_trait_cache.clear()

    def __init__(self, metadata, cur_track_md, camelot_priority):
        self.metadata = metadata
        self.cur_track_md = cur_track_md
        self.camelot_priority = camelot_priority
        self.score = None
        self.factors = {}

    def format(self):
        score = "{:.2f}".format(self.get_score())
        cos_sim = "{:.2f}".format(100 * self.get_similarity_score())
        return ("         " * (6 - len(score))).join(
            [score, cos_sim, self.metadata[TrackDBCols.TITLE]]
        )

    def get_score(self):
        if self.score is None:
            weights = TransitionMatch.effective_weights or MATCH_WEIGHTS
            score_weights = [
                (self.get_camelot_priority_score(), weights[MatchFactors.CAMELOT.name]),
                (self.get_bpm_score(), weights[MatchFactors.BPM.name]),
                (self.get_similarity_score(), weights[MatchFactors.SIMILARITY.name]),
                (self.get_freshness_score(), weights[MatchFactors.FRESHNESS.name]),
                (self.get_energy_score(), weights[MatchFactors.ENERGY.name]),
                (self.get_genre_similarity_score(), weights[MatchFactors.GENRE_SIMILARITY.name]),
                (self.get_mood_continuity_score(), weights[MatchFactors.MOOD_CONTINUITY.name]),
                (self.get_vocal_clash_score(), weights[MatchFactors.VOCAL_CLASH.name]),
                (self.get_danceability_score(), weights[MatchFactors.DANCEABILITY.name]),
                (self.get_timbre_score(), weights[MatchFactors.TIMBRE.name]),
                (self.get_instrument_similarity_score(), weights[MatchFactors.INSTRUMENT_SIMILARITY.name]),
            ]
            self.score = 100 * sum(
                score * weight for score, weight in score_weights
            )

        return self.score

    # ------------------------------------------------------------------ #
    # Low-level feature scorers                                            #
    # ------------------------------------------------------------------ #

    def get_bpm_score(self):
        if MatchFactors.BPM in self.factors:
            return self.factors[MatchFactors.BPM]

        bpm = self.metadata.get(TrackDBCols.BPM)
        cur_track_bpm = self.cur_track_md.get(TrackDBCols.BPM)
        if bpm is None or cur_track_bpm is None:
            self.factors[MatchFactors.BPM] = 0.0
            return 0.0

        absolute_diff = cur_track_bpm - bpm
        if absolute_diff == 0:
            self.factors[MatchFactors.BPM] = 1.0
            return 1.0

        relative_diff = abs(absolute_diff) / float(cur_track_bpm)
        if absolute_diff < 0:
            if relative_diff <= SAME_UPPER_BOUND:
                score = float(SAME_UPPER_BOUND - relative_diff) / SAME_UPPER_BOUND
                self.factors[MatchFactors.BPM] = score
                return score

            if relative_diff <= UP_KEY_UPPER_BOUND:
                midpoint = (UP_KEY_LOWER_BOUND + UP_KEY_UPPER_BOUND) / 2
                result = float(midpoint - abs(midpoint - relative_diff)) / midpoint
                self.factors[MatchFactors.BPM] = result
                return result

            self.factors[MatchFactors.BPM] = 0.0
            return 0.0

        abs_same_lower_bound = abs(SAME_LOWER_BOUND)
        abs_down_key_upper_bound = abs(DOWN_KEY_UPPER_BOUND)
        abs_down_key_lower_bound = abs(DOWN_KEY_LOWER_BOUND)

        score = 0.0
        discount = 0.9

        if relative_diff <= abs_same_lower_bound:
            score = (
                float(abs_same_lower_bound - relative_diff) / abs_same_lower_bound
            )

        if relative_diff <= abs_down_key_lower_bound:
            midpoint = (abs_down_key_lower_bound + abs_down_key_upper_bound) / 2
            score = float(midpoint - abs(midpoint - relative_diff)) / midpoint

        result = score * discount
        self.factors[MatchFactors.BPM] = result
        return result

    def get_camelot_priority_score(self):
        if MatchFactors.CAMELOT in self.factors:
            return self.factors[MatchFactors.CAMELOT]

        if self.camelot_priority == CamelotPriority.ONE_OCTAVE_JUMP:
            self.factors[MatchFactors.CAMELOT] = 0.1
            return 0.1
        if self.camelot_priority == CamelotPriority.ADJACENT_JUMP:
            self.factors[MatchFactors.CAMELOT] = 0.25
            return 0.25
        if self.camelot_priority == CamelotPriority.MAJOR_MINOR_JUMP:
            self.factors[MatchFactors.CAMELOT] = 0.9
            return 0.9

        result = float(self.camelot_priority / CamelotPriority.SAME_KEY.value)
        self.factors[MatchFactors.CAMELOT] = result
        return result

    def get_energy_score(self):
        if MatchFactors.ENERGY in self.factors:
            return self.factors[MatchFactors.ENERGY]

        energy = self.metadata.get(TrackDBCols.ENERGY)
        cur_track_energy = self.cur_track_md.get(TrackDBCols.ENERGY)
        if energy is None or cur_track_energy is None:
            self.factors[MatchFactors.ENERGY] = 0.0
            return 0.0

        result = 1.0 - (abs(energy - cur_track_energy) / 10.0)
        self.factors[MatchFactors.ENERGY] = result
        return result

    def get_freshness_score(self):
        if MatchFactors.FRESHNESS in self.factors:
            return self.factors[MatchFactors.FRESHNESS]

        date_added = self.metadata.get(TrackDBCols.DATE_ADDED)
        if date_added is None:
            self.factors[MatchFactors.FRESHNESS] = 0.5
            return 0.5

        result = (
            date_added - self.collection_metadata[CollectionStat.OLDEST]
        ) / self.collection_metadata[CollectionStat.TIME_RANGE]
        self.factors[MatchFactors.FRESHNESS] = result
        return result

    def get_similarity_score(self):
        if MatchFactors.SIMILARITY in self.factors:
            return self.factors[MatchFactors.SIMILARITY]

        on_deck_id = self.cur_track_md.get(TrackDBCols.ID)
        candidate_id = self.metadata.get(TrackDBCols.ID)

        # 1) In-memory cache check
        if TransitionMatch.cosine_cache is not None:
            cached = TransitionMatch.cosine_cache.get(on_deck_id, candidate_id)
            if cached is not None:
                self.factors[MatchFactors.SIMILARITY] = cached
                return cached

        # 2) Persisted DB check (canonical pair ordering)
        db_result = self._lookup_persisted_similarity(on_deck_id, candidate_id)
        if db_result is not None:
            if TransitionMatch.cosine_cache is not None:
                TransitionMatch.cosine_cache.put(on_deck_id, candidate_id, db_result)
            self.factors[MatchFactors.SIMILARITY] = db_result
            return db_result

        # 3) Compute from descriptors (None when descriptors are absent)
        computed = self._compute_similarity(on_deck_id, candidate_id)

        if computed is not None:
            self._persist_similarity(on_deck_id, candidate_id, computed)
            if TransitionMatch.cosine_cache is not None:
                TransitionMatch.cosine_cache.put(on_deck_id, candidate_id, computed)

        result = computed if computed is not None else 0.0
        self.factors[MatchFactors.SIMILARITY] = result
        return result

    def _lookup_persisted_similarity(self, id1: int, id2: int):
        if self.db_session is None:
            return None
        lo, hi = min(id1, id2), max(id1, id2)
        try:
            row = (
                self.db_session.query(TrackCosineSimilarity)
                .filter_by(id1=lo, id2=hi, descriptor_version=DESCRIPTOR_VERSION)
                .first()
            )
            return row.cosine_similarity if row is not None else None
        except Exception:
            logger.debug("DB similarity lookup failed for (%s, %s)", lo, hi)
            return None

    def _compute_similarity(self, on_deck_id: int, candidate_id: int) -> float:
        if on_deck_id not in TransitionMatch._on_deck_descriptor_cache:
            TransitionMatch._on_deck_descriptor_cache[on_deck_id] = (
                self.db_session.query(TrackDescriptor)
                .filter_by(track_id=on_deck_id, descriptor_version=DESCRIPTOR_VERSION)
                .first()
            )
        on_deck_desc = TransitionMatch._on_deck_descriptor_cache[on_deck_id]

        if candidate_id not in TransitionMatch._candidate_descriptor_cache:
            TransitionMatch._candidate_descriptor_cache[candidate_id] = (
                self.db_session.query(TrackDescriptor)
                .filter_by(track_id=candidate_id, descriptor_version=DESCRIPTOR_VERSION)
                .first()
            )
        candidate_desc = TransitionMatch._candidate_descriptor_cache[candidate_id]

        if on_deck_desc is not None and candidate_desc is not None:
            v1 = unpack_vector(on_deck_desc.global_vector)
            v2 = unpack_vector(candidate_desc.global_vector)
            return compute_similarity(v1, v2)
        return None

    @staticmethod
    def _persist_similarity(id1: int, id2: int, value: float) -> None:
        lo, hi = min(id1, id2), max(id1, id2)
        try:
            from src.db import database
            session = database.create_session()
            try:
                existing = (
                    session.query(TrackCosineSimilarity)
                    .filter_by(id1=lo, id2=hi, descriptor_version=DESCRIPTOR_VERSION)
                    .first()
                )
                if existing is None:
                    row = TrackCosineSimilarity(
                        id1=lo,
                        id2=hi,
                        cosine_similarity=value,
                        descriptor_version=DESCRIPTOR_VERSION,
                    )
                    session.add(row)
                    session.commit()
            except Exception:
                session.rollback()
                logger.debug("Duplicate-safe persist skipped for (%s, %s)", lo, hi)
            finally:
                session.close()
        except Exception:
            logger.debug("Failed to persist similarity for (%s, %s)", lo, hi)

    # ------------------------------------------------------------------ #
    # TrackTrait cache helper                                              #
    # ------------------------------------------------------------------ #

    def _get_on_deck_trait(self):
        on_deck_id = self.cur_track_md.get(TrackDBCols.ID)
        if on_deck_id not in TransitionMatch._on_deck_trait_cache:
            TransitionMatch._on_deck_trait_cache[on_deck_id] = (
                self.db_session.query(TrackTrait)
                .filter_by(track_id=on_deck_id, trait_version=TRAIT_VERSION)
                .first()
            )
        return TransitionMatch._on_deck_trait_cache[on_deck_id]

    def _get_candidate_trait(self):
        candidate_id = self.metadata.get(TrackDBCols.ID)
        if candidate_id not in TransitionMatch._candidate_trait_cache:
            TransitionMatch._candidate_trait_cache[candidate_id] = (
                self.db_session.query(TrackTrait)
                .filter_by(track_id=candidate_id, trait_version=TRAIT_VERSION)
                .first()
            )
        return TransitionMatch._candidate_trait_cache[candidate_id]

    # ------------------------------------------------------------------ #
    # High-level semantic trait scorers                                    #
    # ------------------------------------------------------------------ #

    def get_genre_similarity_score(self):
        if MatchFactors.GENRE_SIMILARITY in self.factors:
            return self.factors[MatchFactors.GENRE_SIMILARITY]

        on_deck = self._get_on_deck_trait()
        candidate = self._get_candidate_trait()
        if on_deck is None or candidate is None:
            self.factors[MatchFactors.GENRE_SIMILARITY] = 0.0
            return 0.0

        result = jsonb_cosine_similarity(
            filter_genre(on_deck.genre or {}),
            filter_genre(candidate.genre or {}),
        )
        self.factors[MatchFactors.GENRE_SIMILARITY] = result
        return result

    def get_mood_continuity_score(self):
        if MatchFactors.MOOD_CONTINUITY in self.factors:
            return self.factors[MatchFactors.MOOD_CONTINUITY]

        on_deck = self._get_on_deck_trait()
        candidate = self._get_candidate_trait()
        if on_deck is None or candidate is None:
            self.factors[MatchFactors.MOOD_CONTINUITY] = 0.0
            return 0.0

        result = jsonb_cosine_similarity(
            filter_mood(on_deck.mood_theme or {}),
            filter_mood(candidate.mood_theme or {}),
        )
        self.factors[MatchFactors.MOOD_CONTINUITY] = result
        return result

    def get_vocal_clash_score(self):
        """Penalty when both tracks carry vocals.

        Score = 1.0 - min(on_deck.voice_instrumental, candidate.voice_instrumental).
        Two instrumentals -> 1.0. Vocal into vocal -> ~0.0.
        """
        if MatchFactors.VOCAL_CLASH in self.factors:
            return self.factors[MatchFactors.VOCAL_CLASH]

        on_deck = self._get_on_deck_trait()
        candidate = self._get_candidate_trait()
        if on_deck is None or candidate is None:
            self.factors[MatchFactors.VOCAL_CLASH] = 0.0
            return 0.0

        vi_on_deck = on_deck.voice_instrumental if on_deck.voice_instrumental is not None else 0.0
        vi_candidate = candidate.voice_instrumental if candidate.voice_instrumental is not None else 0.0
        result = 1.0 - min(vi_on_deck, vi_candidate)
        self.factors[MatchFactors.VOCAL_CLASH] = result
        return result

    def get_danceability_score(self):
        """Reward similar or gently building danceability.

        Base score = 1.0 - abs(diff). Small bonus when candidate is higher
        (building energy on the floor).
        """
        if MatchFactors.DANCEABILITY in self.factors:
            return self.factors[MatchFactors.DANCEABILITY]

        on_deck = self._get_on_deck_trait()
        candidate = self._get_candidate_trait()
        if on_deck is None or candidate is None:
            self.factors[MatchFactors.DANCEABILITY] = 0.0
            return 0.0

        d_on = on_deck.danceability if on_deck.danceability is not None else 0.5
        d_cand = candidate.danceability if candidate.danceability is not None else 0.5
        diff = d_cand - d_on
        base = 1.0 - abs(diff)
        build_bonus = max(0.0, min(0.1, diff))
        result = min(1.0, base + build_bonus)
        self.factors[MatchFactors.DANCEABILITY] = result
        return result

    def get_timbre_score(self):
        """Reward timbral continuity via bright_dark proximity."""
        if MatchFactors.TIMBRE in self.factors:
            return self.factors[MatchFactors.TIMBRE]

        on_deck = self._get_on_deck_trait()
        candidate = self._get_candidate_trait()
        if on_deck is None or candidate is None:
            self.factors[MatchFactors.TIMBRE] = 0.0
            return 0.0

        t_on = on_deck.bright_dark if on_deck.bright_dark is not None else 0.5
        t_cand = candidate.bright_dark if candidate.bright_dark is not None else 0.5
        result = 1.0 - abs(t_on - t_cand)
        self.factors[MatchFactors.TIMBRE] = result
        return result

    def get_instrument_similarity_score(self):
        if MatchFactors.INSTRUMENT_SIMILARITY in self.factors:
            return self.factors[MatchFactors.INSTRUMENT_SIMILARITY]

        on_deck = self._get_on_deck_trait()
        candidate = self._get_candidate_trait()
        if on_deck is None or candidate is None:
            self.factors[MatchFactors.INSTRUMENT_SIMILARITY] = 0.0
            return 0.0

        result = jsonb_cosine_similarity(
            filter_instruments(on_deck.instruments or {}),
            filter_instruments(candidate.instruments or {}),
        )
        self.factors[MatchFactors.INSTRUMENT_SIMILARITY] = result
        return result

    def __lt__(self, other):
        return (self.get_score(), self.get_similarity_score(), self.get_freshness_score()) < (
            other.get_score(),
            other.get_similarity_score(),
            other.get_freshness_score(),
        )

    def __hash__(self):
        return hash(self.metadata[TrackDBCols.FILE_NAME])
