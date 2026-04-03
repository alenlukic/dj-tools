"""Elasticsearch client, index management, and search for track autocomplete."""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

from elasticsearch import Elasticsearch, helpers

logger = logging.getLogger(__name__)

INDEX_NAME = os.getenv("ES_TRACK_INDEX", "dj_tracks")
ES_URL = os.getenv("ES_URL", "http://localhost:9200")

INDEX_SETTINGS = {
    "settings": {
        "analysis": {
            "analyzer": {
                "autocomplete": {
                    "type": "custom",
                    "tokenizer": "standard",
                    "filter": ["lowercase", "edge_ngram_filter"],
                },
                "autocomplete_search": {
                    "type": "custom",
                    "tokenizer": "standard",
                    "filter": ["lowercase"],
                },
            },
            "filter": {
                "edge_ngram_filter": {
                    "type": "edge_ngram",
                    "min_gram": 2,
                    "max_gram": 20,
                },
            },
        },
    },
    "mappings": {
        "properties": {
            "title": {
                "type": "text",
                "analyzer": "autocomplete",
                "search_analyzer": "autocomplete_search",
                "fields": {
                    "exact": {"type": "keyword"},
                },
            },
            "artist_names": {
                "type": "text",
                "analyzer": "autocomplete",
                "search_analyzer": "autocomplete_search",
            },
            "genre": {"type": "text"},
            "label": {"type": "text"},
            "camelot_code": {"type": "keyword"},
            "bpm": {"type": "float"},
            "key": {"type": "keyword"},
            "energy": {"type": "integer"},
        },
    },
}

TITLE_BOOST = 5.0
ARTIST_BOOST = 2.0


def get_client() -> Elasticsearch:
    return Elasticsearch(ES_URL)


def ensure_index(client: Optional[Elasticsearch] = None) -> None:
    es = client or get_client()
    if not es.indices.exists(index=INDEX_NAME):
        es.indices.create(index=INDEX_NAME, body=INDEX_SETTINGS)
        logger.info("Created Elasticsearch index '%s'", INDEX_NAME)


def delete_index(client: Optional[Elasticsearch] = None) -> None:
    es = client or get_client()
    if es.indices.exists(index=INDEX_NAME):
        es.indices.delete(index=INDEX_NAME)
        logger.info("Deleted Elasticsearch index '%s'", INDEX_NAME)


def index_track(client: Elasticsearch, track_doc: Dict[str, Any]) -> None:
    """Index a single track document. `track_doc` must include an `id` key."""
    client.index(index=INDEX_NAME, id=str(track_doc["id"]), body=track_doc)


def bulk_index_tracks(client: Elasticsearch, track_docs: List[Dict[str, Any]]) -> int:
    """Bulk-index a list of track documents. Returns the count of indexed docs."""
    actions = [
        {
            "_index": INDEX_NAME,
            "_id": str(doc["id"]),
            "_source": doc,
        }
        for doc in track_docs
    ]
    success, _ = helpers.bulk(client, actions, raise_on_error=True)
    return success


def search(query: str, limit: int = 10, client: Optional[Elasticsearch] = None) -> List[Dict[str, Any]]:
    """Search tracks with title-weighted multi-field matching and BPM support."""
    es = client or get_client()

    should: List[Dict[str, Any]] = [
        {"match": {"title": {"query": query, "boost": TITLE_BOOST}}},
        {"match": {"title.exact": {"query": query, "boost": TITLE_BOOST * 2}}},
        {"match": {"artist_names": {"query": query, "boost": ARTIST_BOOST}}},
        {"match": {"genre": {"query": query, "boost": 0.5}}},
        {"match": {"label": {"query": query, "boost": 0.5}}},
        {"term": {"camelot_code": {"value": query.upper(), "boost": 1.0}}},
    ]

    try:
        bpm_val = float(query)
        should.append({"term": {"bpm": {"value": bpm_val, "boost": 1.5}}})
    except ValueError:
        pass

    body = {
        "size": limit,
        "query": {
            "bool": {
                "should": should,
                "minimum_should_match": 1,
            },
        },
    }

    resp = es.search(index=INDEX_NAME, body=body)
    hits = resp.get("hits", {}).get("hits", [])
    return [hit["_source"] for hit in hits]
