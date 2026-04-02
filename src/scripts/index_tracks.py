"""One-shot script to populate the Elasticsearch track index from PostgreSQL."""

from __future__ import annotations

import logging
import sys

from sqlalchemy import func, literal_column

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    from src.db import database
    from src.models.track import Track
    from src.api.es import bulk_index_tracks, ensure_index, get_client

    session_wrapper = database.create_session()
    session = session_wrapper.session

    tables = database.get_tables()
    artist_table = tables["artist"]
    artist_track_table = tables["artist_track"]

    artist_agg = func.string_agg(
        artist_table.c.name, literal_column("', '")
    ).label("artist_names")

    rows = (
        session.query(Track, artist_agg)
        .outerjoin(artist_track_table, artist_track_table.c.track_id == Track.id)
        .outerjoin(artist_table, artist_table.c.id == artist_track_table.c.artist_id)
        .group_by(
            Track.id, Track.file_name, Track.title, Track.bpm,
            Track.key, Track.camelot_code, Track.energy, Track.genre,
            Track.label, Track.comment,
        )
        .all()
    )

    docs = []
    for track, artist_names_str in rows:
        names = []
        if artist_names_str:
            names = [n.strip() for n in artist_names_str.split(",") if n.strip()]

        docs.append({
            "id": track.id,
            "title": track.title or "",
            "artist_names": names,
            "bpm": float(track.bpm) if track.bpm is not None else None,
            "key": track.key,
            "camelot_code": track.camelot_code,
            "genre": track.genre,
            "label": track.label,
            "energy": track.energy,
        })

    session_wrapper.close()

    logger.info("Loaded %d tracks from PostgreSQL", len(docs))

    es = get_client()
    ensure_index(es)
    indexed = bulk_index_tracks(es, docs)
    from src.api.es import INDEX_NAME
    es.indices.refresh(index=INDEX_NAME)
    logger.info("Indexed %d tracks into Elasticsearch", indexed)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        logger.exception("Indexing failed")
        sys.exit(1)
