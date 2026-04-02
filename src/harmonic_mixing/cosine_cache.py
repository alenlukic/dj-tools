import logging
import threading
from collections import OrderedDict
from typing import Optional, Tuple

from src.db import database
from src.feature_extraction.config import DESCRIPTOR_VERSION
from src.models.track_cosine_similarity import TrackCosineSimilarity

logger = logging.getLogger(__name__)

_MAX_ENTRIES = 500_000


class CosineCache:
    """Thread-safe LRU cache for pairwise cosine similarity scores.

    Keys are canonical ordered pairs ``(min(id1, id2), max(id1, id2))``
    so that lookup order does not matter.
    """

    def __init__(self, max_entries: int = _MAX_ENTRIES):
        self._max_entries = max_entries
        self._lock = threading.Lock()
        self._store = OrderedDict()  # type: OrderedDict[Tuple[int, int], float]

    @staticmethod
    def _key(id1: int, id2: int) -> Tuple[int, int]:
        return (min(id1, id2), max(id1, id2))

    def get(self, id1: int, id2: int) -> Optional[float]:
        key = self._key(id1, id2)
        with self._lock:
            if key in self._store:
                self._store.move_to_end(key)
                return self._store[key]
        return None

    def put(self, id1: int, id2: int, value: float) -> None:
        key = self._key(id1, id2)
        with self._lock:
            if key in self._store:
                self._store.move_to_end(key)
                self._store[key] = value
            else:
                self._store[key] = value
                if len(self._store) > self._max_entries:
                    self._store.popitem(last=False)

    def size(self) -> int:
        with self._lock:
            return len(self._store)

    def warm_from_db(self, track_id: int) -> None:
        """BFS-warm the cache from ``track_cosine_similarity`` rows.

        Depth 1: rows where ``id1 == track_id``; cache each pair.
        Depth 2: for every depth-1 neighbor *n*, rows where ``id1 == n``;
                 cache those pairs.

        Creates its own DB session so it never shares a session across threads.
        """
        session = database.create_session()
        try:
            depth1_rows = (
                session.query(TrackCosineSimilarity)
                .filter_by(id1=track_id, descriptor_version=DESCRIPTOR_VERSION)
                .all()
            )

            depth1_neighbors = []
            for row in depth1_rows:
                self.put(row.id1, row.id2, row.cosine_similarity)
                depth1_neighbors.append(row.id2)

            for neighbor_id in depth1_neighbors:
                depth2_rows = (
                    session.query(TrackCosineSimilarity)
                    .filter_by(id1=neighbor_id, descriptor_version=DESCRIPTOR_VERSION)
                    .all()
                )
                for row in depth2_rows:
                    self.put(row.id1, row.id2, row.cosine_similarity)

        except Exception:
            logger.exception("Error warming cosine cache for track %s", track_id)
        finally:
            session.close()
