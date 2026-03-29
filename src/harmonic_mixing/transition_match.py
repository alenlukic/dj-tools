import numpy as np

from src.models.track_descriptor import TrackDescriptor
from src.models.track_trait import TrackTrait
from src.data_management.config import TrackDBCols
from src.feature_extraction.config import DESCRIPTOR_VERSION, TRAIT_VERSION
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
from src.feature_extraction.compact_descriptor import cosine_similarity, unpack_vector
from src.utils.common import log2smooth


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
    # Class-level caches: one query per on-deck track and one per candidate per session.
    # Call clear_descriptor_caches() at the start of each new track query.
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
            if self.cur_track_md[TrackDBCols.TITLE] == self.metadata[TrackDBCols.TITLE]:
                self.score = 100
            else:
                score_weights = [
                    (
                        self.get_camelot_priority_score(),
                        MATCH_WEIGHTS[MatchFactors.CAMELOT.name],
                    ),
                    (self.get_bpm_score(), MATCH_WEIGHTS[MatchFactors.BPM.name]),
                    (
                        self.get_similarity_score(),
                        MATCH_WEIGHTS[MatchFactors.SIMILARITY.name],
                    ),
                    (
                        self.get_freshness_score(),
                        MATCH_WEIGHTS[MatchFactors.FRESHNESS.name],
                    ),
                    (self.get_energy_score(), MATCH_WEIGHTS[MatchFactors.ENERGY.name]),
                    (
                        self.get_genre_similarity_score(),
                        MATCH_WEIGHTS[MatchFactors.GENRE_SIMILARITY.name],
                    ),
                    (
                        self.get_mood_continuity_score(),
                        MATCH_WEIGHTS[MatchFactors.MOOD_CONTINUITY.name],
                    ),
                    (
                        self.get_vocal_clash_score(),
                        MATCH_WEIGHTS[MatchFactors.VOCAL_CLASH.name],
                    ),
                    (
                        self.get_danceability_score(),
                        MATCH_WEIGHTS[MatchFactors.DANCEABILITY.name],
                    ),
                    (
                        self.get_timbre_score(),
                        MATCH_WEIGHTS[MatchFactors.TIMBRE.name],
                    ),
                    (
                        self.get_instrument_similarity_score(),
                        MATCH_WEIGHTS[MatchFactors.INSTRUMENT_SIMILARITY.name],
                    ),
                ]
                self.score = 100 * sum(
                    [score * weight for score, weight in score_weights]
                )

        return self.score

    # ------------------------------------------------------------------ #
    # Low-level feature scorers                                            #
    # ------------------------------------------------------------------ #

    def get_bpm_score(self):
        def _get_bpm_score():
            bpm = self.metadata.get(TrackDBCols.BPM)
            cur_track_bpm = self.cur_track_md.get(TrackDBCols.BPM)
            if bpm is None or cur_track_bpm is None:
                return 0.0

            absolute_diff = cur_track_bpm - bpm
            if absolute_diff == 0:
                return 1.0

            relative_diff = abs(absolute_diff) / float(cur_track_bpm)
            if absolute_diff < 0:
                if relative_diff <= SAME_UPPER_BOUND:
                    score = float(SAME_UPPER_BOUND - relative_diff) / SAME_UPPER_BOUND
                    self.factors[MatchFactors.BPM] = score
                    return score

                if relative_diff <= UP_KEY_UPPER_BOUND:
                    midpoint = (UP_KEY_LOWER_BOUND + UP_KEY_UPPER_BOUND) / 2
                    return float(midpoint - abs(midpoint - relative_diff)) / midpoint

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

            return score * discount

        if MatchFactors.BPM not in self.factors:
            self.factors[MatchFactors.BPM] = _get_bpm_score()
        return self.factors[MatchFactors.BPM]

    def get_camelot_priority_score(self):
        def _get_camelot_priority_score():
            if self.camelot_priority == CamelotPriority.ONE_OCTAVE_JUMP:
                self.factors[MatchFactors.CAMELOT] = 0.1
                return 0.1
            if self.camelot_priority == CamelotPriority.ADJACENT_JUMP:
                self.factors[MatchFactors.CAMELOT] = 0.25
                return 0.25
            if self.camelot_priority == CamelotPriority.MAJOR_MINOR_JUMP:
                self.factors[MatchFactors.CAMELOT] = 0.9
                return 0.9

            return float(self.camelot_priority / CamelotPriority.SAME_KEY.value)

        if MatchFactors.CAMELOT not in self.factors:
            self.factors[MatchFactors.CAMELOT] = _get_camelot_priority_score()
        return self.factors[MatchFactors.CAMELOT]

    def get_energy_score(self):
        def _get_energy_score():
            energy = self.metadata.get(TrackDBCols.ENERGY)
            cur_track_energy = self.cur_track_md.get(TrackDBCols.ENERGY)
            if energy is None or cur_track_energy is None:
                return 0.0

            return 1.0 - (abs(energy - cur_track_energy) / 10.0)

        if MatchFactors.ENERGY not in self.factors:
            self.factors[MatchFactors.ENERGY] = _get_energy_score()
        return self.factors[MatchFactors.ENERGY]

    def get_freshness_score(self):
        def _get_freshness_score():
            date_added = self.metadata.get(TrackDBCols.DATE_ADDED)
            if date_added is None:
                return 0.5

            return (
                date_added - self.collection_metadata[CollectionStat.OLDEST]
            ) / self.collection_metadata[CollectionStat.TIME_RANGE]

        if MatchFactors.FRESHNESS not in self.factors:
            self.factors[MatchFactors.FRESHNESS] = _get_freshness_score()
        return self.factors[MatchFactors.FRESHNESS]

    def get_similarity_score(self):
        def _get_similarity_score():
            on_deck_id = self.cur_track_md.get(TrackDBCols.ID)
            candidate_id = self.metadata.get(TrackDBCols.ID)

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
                return cosine_similarity(v1, v2)

            return 0.0

        if MatchFactors.SIMILARITY not in self.factors:
            self.factors[MatchFactors.SIMILARITY] = _get_similarity_score()
        return self.factors[MatchFactors.SIMILARITY]

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
        def _score():
            on_deck = self._get_on_deck_trait()
            candidate = self._get_candidate_trait()
            if on_deck is None or candidate is None:
                return 0.0
            return jsonb_cosine_similarity(
                on_deck.genre or {}, candidate.genre or {}
            )

        if MatchFactors.GENRE_SIMILARITY not in self.factors:
            self.factors[MatchFactors.GENRE_SIMILARITY] = _score()
        return self.factors[MatchFactors.GENRE_SIMILARITY]

    def get_mood_continuity_score(self):
        def _score():
            on_deck = self._get_on_deck_trait()
            candidate = self._get_candidate_trait()
            if on_deck is None or candidate is None:
                return 0.0
            return jsonb_cosine_similarity(
                on_deck.mood_theme or {}, candidate.mood_theme or {}
            )

        if MatchFactors.MOOD_CONTINUITY not in self.factors:
            self.factors[MatchFactors.MOOD_CONTINUITY] = _score()
        return self.factors[MatchFactors.MOOD_CONTINUITY]

    def get_vocal_clash_score(self):
        """Penalty when both tracks carry vocals.

        Score = 1.0 - min(on_deck.voice_instrumental, candidate.voice_instrumental).
        Two instrumentals → 1.0. Vocal into vocal → ~0.0.
        """
        def _score():
            on_deck = self._get_on_deck_trait()
            candidate = self._get_candidate_trait()
            if on_deck is None or candidate is None:
                return 0.0
            vi_on_deck = on_deck.voice_instrumental if on_deck.voice_instrumental is not None else 0.0
            vi_candidate = candidate.voice_instrumental if candidate.voice_instrumental is not None else 0.0
            return 1.0 - min(vi_on_deck, vi_candidate)

        if MatchFactors.VOCAL_CLASH not in self.factors:
            self.factors[MatchFactors.VOCAL_CLASH] = _score()
        return self.factors[MatchFactors.VOCAL_CLASH]

    def get_danceability_score(self):
        """Reward similar or gently building danceability.

        Base score = 1.0 - abs(diff). Small bonus when candidate is higher
        (building energy on the floor).
        """
        def _score():
            on_deck = self._get_on_deck_trait()
            candidate = self._get_candidate_trait()
            if on_deck is None or candidate is None:
                return 0.0
            d_on = on_deck.danceability if on_deck.danceability is not None else 0.5
            d_cand = candidate.danceability if candidate.danceability is not None else 0.5
            diff = d_cand - d_on
            base = 1.0 - abs(diff)
            # Small bonus (up to 0.1) when candidate is slightly more danceable
            build_bonus = max(0.0, min(0.1, diff))
            return min(1.0, base + build_bonus)

        if MatchFactors.DANCEABILITY not in self.factors:
            self.factors[MatchFactors.DANCEABILITY] = _score()
        return self.factors[MatchFactors.DANCEABILITY]

    def get_timbre_score(self):
        """Reward timbral continuity via bright_dark proximity."""
        def _score():
            on_deck = self._get_on_deck_trait()
            candidate = self._get_candidate_trait()
            if on_deck is None or candidate is None:
                return 0.0
            t_on = on_deck.bright_dark if on_deck.bright_dark is not None else 0.5
            t_cand = candidate.bright_dark if candidate.bright_dark is not None else 0.5
            return 1.0 - abs(t_on - t_cand)

        if MatchFactors.TIMBRE not in self.factors:
            self.factors[MatchFactors.TIMBRE] = _score()
        return self.factors[MatchFactors.TIMBRE]

    def get_instrument_similarity_score(self):
        def _score():
            on_deck = self._get_on_deck_trait()
            candidate = self._get_candidate_trait()
            if on_deck is None or candidate is None:
                return 0.0
            return jsonb_cosine_similarity(
                on_deck.instruments or {}, candidate.instruments or {}
            )

        if MatchFactors.INSTRUMENT_SIMILARITY not in self.factors:
            self.factors[MatchFactors.INSTRUMENT_SIMILARITY] = _score()
        return self.factors[MatchFactors.INSTRUMENT_SIMILARITY]

    def __lt__(self, other):
        return (self.get_score(), self.get_similarity_score(), self.get_freshness_score()) < (
            other.get_score(),
            other.get_similarity_score(),
            other.get_freshness_score(),
        )

    def __hash__(self):
        return hash(self.metadata[TrackDBCols.FILE_NAME])
