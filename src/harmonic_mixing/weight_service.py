"""Mutable scoring-weight service with raw/effective semantics.

Weights are stored internally on a 0–1 scale (matching
``MATCH_WEIGHTS`` from config).  The API surface presents them on a
0–100 scale for UI consumption.

Scope: **global** (single set of weights for the whole process).
Persistence: ``scoring_weight_override`` table via SQLAlchemy.
"""

import json
import logging
import threading
from typing import Dict, Optional

from src.harmonic_mixing.config import MATCH_WEIGHTS, MatchFactors

logger = logging.getLogger(__name__)

_TARGET_SUM = 100

_FUSION_WEIGHT_DEFAULTS = {
    'FUSION_HARMONIC': 0.30,
    'FUSION_RHYTHM': 0.25,
    'FUSION_TIMBRE': 0.30,
    'FUSION_ENERGY': 0.15,
}
_FUSION_KEYS = frozenset(_FUSION_WEIGHT_DEFAULTS)


class WeightService:
    _instance: Optional["WeightService"] = None
    _init_lock = threading.Lock()

    def __init__(self):
        self._lock = threading.Lock()
        self._raw_weights: Dict[str, float] = dict(MATCH_WEIGHTS)
        self._fusion_weights: Dict[str, float] = dict(_FUSION_WEIGHT_DEFAULTS)
        self._load_from_db()

    @classmethod
    def instance(cls) -> "WeightService":
        if cls._instance is None:
            with cls._init_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Drop the singleton (for tests)."""
        cls._instance = None

    def _load_from_db(self) -> None:
        try:
            from src.db import database
            from src.models.scoring_weight_override import ScoringWeightOverride

            session = database.create_session()
            try:
                row = (
                    session.query(ScoringWeightOverride)
                    .filter_by(scope="global")
                    .first()
                )
                if row is not None:
                    saved: Dict[str, float] = json.loads(row.weights_json)
                    stale_keys = []
                    for k, v in saved.items():
                        if k in _FUSION_KEYS:
                            self._fusion_weights[k] = v
                        elif k in self._raw_weights:
                            self._raw_weights[k] = v
                        else:
                            stale_keys.append(k)
                    if stale_keys:
                        logger.warning(
                            "DB weight record contained stale factor(s) %s that are no longer "
                            "in MatchFactors or fusion keys; ignoring them.",
                            stale_keys,
                        )
            finally:
                session.close()
        except Exception:
            logger.debug("Could not load weight overrides from DB; using config defaults")

    def _persist_to_db(self) -> None:
        try:
            from src.db import database
            from src.models.scoring_weight_override import ScoringWeightOverride

            session = database.create_session()
            try:
                row = (
                    session.query(ScoringWeightOverride)
                    .filter_by(scope="global")
                    .first()
                )
                payload = json.dumps({**self._raw_weights, **self._fusion_weights})
                if row is not None:
                    row.weights_json = payload
                    session.commit()
                else:
                    new_row = ScoringWeightOverride(
                        scope="global",
                        weights_json=payload,
                    )
                    session.add(new_row)
                    session.commit()
            except Exception:
                session.rollback()
                logger.exception("Failed to persist weight overrides")
            finally:
                session.close()
        except Exception:
            logger.debug("DB unavailable for weight persistence")

    def get_weights(self) -> Dict:
        with self._lock:
            main_100 = {k: round(v * 100, 4) for k, v in self._raw_weights.items()}
            fusion_100 = {k: round(v * 100, 4) for k, v in self._fusion_weights.items()}

            raw_sum = round(sum(main_100.values()), 4)
            is_valid = abs(raw_sum - _TARGET_SUM) < 0.01

            effective = self._compute_effective()
            eff_100 = {k: round(v * 100, 4) for k, v in effective.items()}

            message = None
            if not is_valid:
                message = (
                    f"Weights sum to {raw_sum}; target is {_TARGET_SUM}. "
                    "Effective weights are normalized for scoring."
                )

            return {
                "raw_weights": {**main_100, **fusion_100},
                "effective_weights": eff_100,
                "raw_sum": raw_sum,
                "target_sum": _TARGET_SUM,
                "is_sum_valid": is_valid,
                "message": message,
            }

    def update_weights(self, new_weights: Dict[str, float]) -> Dict:
        """Accept weights on the 0-100 scale, persist, and return canonical state."""
        valid_main_keys = {f.name for f in MatchFactors}
        with self._lock:
            for k, v in new_weights.items():
                if k in _FUSION_KEYS:
                    self._fusion_weights[k] = v / 100.0
                elif k in valid_main_keys:
                    self._raw_weights[k] = v / 100.0
        self._persist_to_db()
        return self.get_weights()

    def get_fusion_weights(self) -> Dict[str, float]:
        """Return fusion weights on 0-1 scale."""
        with self._lock:
            return dict(self._fusion_weights)

    def get_effective_weights_for_scoring(self) -> Dict[str, float]:
        """Return effective weights on 0-1 scale, summing to 1.0, for use by the scoring path."""
        with self._lock:
            return self._compute_effective()

    def _compute_effective(self) -> Dict[str, float]:
        total = sum(self._raw_weights.values())
        if total == 0:
            n = len(self._raw_weights)
            return {k: 1.0 / n for k in self._raw_weights}
        return {k: v / total for k, v in self._raw_weights.items()}
