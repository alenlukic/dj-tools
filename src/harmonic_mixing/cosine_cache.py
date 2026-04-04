import logging
import threading
import time
from collections import OrderedDict, deque
from typing import Dict, Optional, Set, Tuple

from src.db import database
from src.feature_extraction.config import DESCRIPTOR_VERSION
from src.models.track_cosine_similarity import TrackCosineSimilarity

logger = logging.getLogger(__name__)

_MAX_ENTRIES = 500_000
_RECENT_EVENT_LIMIT = 10


class CosineCache:
    """Thread-safe LRU cache for pairwise cosine similarity scores.

    Keys are canonical ordered pairs ``(min(id1, id2), max(id1, id2))``
    so that lookup order does not matter.

    Tracks hit/miss counts and recent entry/exit events for admin
    dashboard instrumentation.
    """

    def __init__(self, max_entries: int = _MAX_ENTRIES):
        self._max_entries = max_entries
        self._lock = threading.Lock()
        self._store: OrderedDict[Tuple[int, int], float] = OrderedDict()

        self._hits = 0
        self._misses = 0
        self._recent_entries: deque = deque(maxlen=_RECENT_EVENT_LIMIT)
        self._recent_exits: deque = deque(maxlen=_RECENT_EVENT_LIMIT)

    @staticmethod
    def _key(id1: int, id2: int) -> Tuple[int, int]:
        return (min(id1, id2), max(id1, id2))

    def get(self, id1: int, id2: int) -> Optional[float]:
        key = self._key(id1, id2)
        with self._lock:
            if key in self._store:
                self._store.move_to_end(key)
                self._hits += 1
                return self._store[key]
            self._misses += 1
        return None

    def put(self, id1: int, id2: int, value: float) -> None:
        key = self._key(id1, id2)
        now = time.time()
        with self._lock:
            if key in self._store:
                self._store.move_to_end(key)
                self._store[key] = value
            else:
                self._store[key] = value
                self._recent_entries.append({"pair": key, "timestamp": now})
                if len(self._store) > self._max_entries:
                    evicted_key, _ = self._store.popitem(last=False)
                    self._recent_exits.append({
                        "pair": evicted_key,
                        "timestamp": now,
                        "reason": "lru_eviction",
                    })

    def size(self) -> int:
        with self._lock:
            return len(self._store)

    def get_cached_track_ids(self) -> Set[int]:
        with self._lock:
            ids: Set[int] = set()
            for id1, id2 in self._store:
                ids.add(id1)
                ids.add(id2)
            return ids

    def get_stats(self) -> Dict:
        """Return admin-facing cache statistics.

        All counters are process-lifetime values.  Recent entry/exit
        lists are capped at ``_RECENT_EVENT_LIMIT`` and ordered
        newest-first.
        """
        with self._lock:
            used = len(self._store)
            capacity = self._max_entries
            hits = self._hits
            misses = self._misses
            recent_entries = list(reversed(self._recent_entries))
            recent_exits = list(reversed(self._recent_exits))

        total = hits + misses
        hit_rate = hits / total if total > 0 else 0.0

        return {
            "used": used,
            "capacity": capacity,
            "usage_ratio": round(used / capacity, 6) if capacity > 0 else 0.0,
            "hits": hits,
            "misses": misses,
            "hit_rate": round(hit_rate, 6),
            "hit_rate_numerator": hits,
            "hit_rate_denominator": total,
            "hit_rate_basis": "process_lifetime",
            "recent_entries": recent_entries,
            "recent_exits": recent_exits,
        }

    def warm_from_db(self, track_id: int) -> None:
        """BFS-warm the cache from ``track_cosine_similarity`` rows.

        Depth 1: all rows incident to *track_id* (in either id1 or id2).
        Depth 2: for every depth-1 neighbor *n*, all rows incident to *n*.

        Rows are stored in canonical order (id1 < id2), so a track can
        appear in either column; both must be checked.

        Creates its own DB session so it never shares a session across threads.
        """
        session = database.create_session()
        try:
            depth1_rows = (
                session.query(TrackCosineSimilarity)
                .filter(
                    (TrackCosineSimilarity.id1 == track_id)
                    | (TrackCosineSimilarity.id2 == track_id),
                    TrackCosineSimilarity.descriptor_version == DESCRIPTOR_VERSION,
                )
                .all()
            )

            depth1_neighbors = []
            for row in depth1_rows:
                self.put(row.id1, row.id2, row.cosine_similarity)
                neighbor_id = row.id2 if row.id1 == track_id else row.id1
                depth1_neighbors.append(neighbor_id)

            for neighbor_id in depth1_neighbors:
                depth2_rows = (
                    session.query(TrackCosineSimilarity)
                    .filter(
                        (TrackCosineSimilarity.id1 == neighbor_id)
                        | (TrackCosineSimilarity.id2 == neighbor_id),
                        TrackCosineSimilarity.descriptor_version == DESCRIPTOR_VERSION,
                    )
                    .all()
                )
                for row in depth2_rows:
                    self.put(row.id1, row.id2, row.cosine_similarity)

        except Exception:
            logger.exception("Error warming cosine cache for track %s", track_id)
        finally:
            session.close()
