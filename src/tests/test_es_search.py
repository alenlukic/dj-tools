"""Tests for Elasticsearch track search and indexing logic.

These tests run against a real Elasticsearch instance (http://localhost:9200)
using a dedicated test index. They are skipped if ES is unavailable.
"""

from __future__ import annotations

import pytest

try:
    from elasticsearch import Elasticsearch

    _es = Elasticsearch("http://localhost:9200")
    _es.info()
    ES_AVAILABLE = True
except Exception:
    ES_AVAILABLE = False

skip_no_es = pytest.mark.skipif(not ES_AVAILABLE, reason="Elasticsearch not available")

TEST_INDEX = "dj_tracks_test"

SAMPLE_TRACKS = [
    {
        "id": 1,
        "title": "Lethal Industry",
        "artist_names": ["Tiësto"],
        "bpm": 138.0,
        "key": "Am",
        "camelot_code": "08A",
        "genre": "Trance",
        "label": "Nettwerk",
        "energy": 8,
    },
    {
        "id": 2,
        "title": "Adagio for Strings",
        "artist_names": ["Tiësto"],
        "bpm": 136.0,
        "key": "Dm",
        "camelot_code": "07A",
        "genre": "Trance",
        "label": "Nettwerk",
        "energy": 9,
    },
    {
        "id": 3,
        "title": "Gecko",
        "artist_names": ["Oliver Heldens"],
        "bpm": 125.0,
        "key": "Gm",
        "camelot_code": "06A",
        "genre": "Deep House",
        "label": "Heldeep",
        "energy": 7,
    },
    {
        "id": 4,
        "title": "Industry Baby",
        "artist_names": ["Lil Nas X"],
        "bpm": 150.0,
        "key": "Cm",
        "camelot_code": "05A",
        "genre": "Pop",
        "label": "Columbia",
        "energy": 8,
    },
    {
        "id": 5,
        "title": "Animals",
        "artist_names": ["Martin Garrix"],
        "bpm": 128.0,
        "key": "F#m",
        "camelot_code": "11A",
        "genre": "Big Room",
        "label": "Spinnin",
        "energy": 10,
    },
]


@pytest.fixture(autouse=True)
def _es_test_index():
    """Create a fresh test index before each test and clean up after."""
    import os
    os.environ["ES_TRACK_INDEX"] = TEST_INDEX

    import src.api.es as es_mod
    es_mod.INDEX_NAME = TEST_INDEX

    es = Elasticsearch("http://localhost:9200")
    if es.indices.exists(index=TEST_INDEX):
        es.indices.delete(index=TEST_INDEX)
    es_mod.ensure_index(es)

    yield es

    if es.indices.exists(index=TEST_INDEX):
        es.indices.delete(index=TEST_INDEX)


@skip_no_es
class TestEsIndexing:
    def test_ensure_index_creates_index(self, _es_test_index):
        es = _es_test_index
        assert es.indices.exists(index=TEST_INDEX)

    def test_bulk_index_tracks(self, _es_test_index):
        from src.api.es import bulk_index_tracks

        es = _es_test_index
        count = bulk_index_tracks(es, SAMPLE_TRACKS)
        assert count == len(SAMPLE_TRACKS)

        es.indices.refresh(index=TEST_INDEX)
        resp = es.count(index=TEST_INDEX)
        assert resp["count"] == len(SAMPLE_TRACKS)

    def test_index_single_track(self, _es_test_index):
        from src.api.es import index_track

        es = _es_test_index
        index_track(es, SAMPLE_TRACKS[0])
        es.indices.refresh(index=TEST_INDEX)
        resp = es.count(index=TEST_INDEX)
        assert resp["count"] == 1


@skip_no_es
class TestEsSearch:
    @pytest.fixture(autouse=True)
    def _populate(self, _es_test_index):
        from src.api.es import bulk_index_tracks

        es = _es_test_index
        bulk_index_tracks(es, SAMPLE_TRACKS)
        es.indices.refresh(index=TEST_INDEX)

    def test_title_search_returns_results(self, _es_test_index):
        from src.api.es import search

        es = _es_test_index
        results = search("Lethal Industry", limit=5, client=es)
        assert len(results) > 0
        assert results[0]["title"] == "Lethal Industry"

    def test_title_search_prioritizes_exact_title(self, _es_test_index):
        from src.api.es import search

        es = _es_test_index
        results = search("Industry", limit=10, client=es)
        titles = [r["title"] for r in results]
        assert "Lethal Industry" in titles
        assert "Industry Baby" in titles

    def test_artist_search(self, _es_test_index):
        from src.api.es import search

        es = _es_test_index
        results = search("Tiësto", limit=10, client=es)
        assert len(results) >= 2
        ids = {r["id"] for r in results}
        assert 1 in ids
        assert 2 in ids

    def test_genre_search(self, _es_test_index):
        from src.api.es import search

        es = _es_test_index
        results = search("Trance", limit=10, client=es)
        assert len(results) >= 2

    def test_camelot_search(self, _es_test_index):
        from src.api.es import search

        es = _es_test_index
        results = search("08A", limit=10, client=es)
        found_ids = {r["id"] for r in results}
        assert 1 in found_ids

    def test_empty_query_returns_empty(self, _es_test_index):
        from src.api.es import search

        es = _es_test_index
        results = search("xyznonexistent", limit=10, client=es)
        assert len(results) == 0

    def test_search_limit(self, _es_test_index):
        from src.api.es import search

        es = _es_test_index
        results = search("a", limit=2, client=es)
        assert len(results) <= 2

    def test_result_contains_required_fields(self, _es_test_index):
        from src.api.es import search

        es = _es_test_index
        results = search("Gecko", limit=5, client=es)
        assert len(results) > 0
        hit = results[0]
        assert "id" in hit
        assert "title" in hit
        assert "artist_names" in hit
        assert "bpm" in hit
        assert "key" in hit
        assert "camelot_code" in hit
