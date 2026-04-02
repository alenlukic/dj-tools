"""Migration: create the track_cosine_similarity table.

Run once:
    python -m src.scripts.migrations.20260401_create_track_cosine_similarity

Stores precomputed cosine similarities between compact descriptor vectors for
harmonically matched track pairs. Each pair is stored once with id1 < id2.
"""

import sys

from src.db import database


CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS track_cosine_similarity (
    id1                 INTEGER NOT NULL REFERENCES track(id),
    id2                 INTEGER NOT NULL REFERENCES track(id),
    cosine_similarity   DOUBLE PRECISION NOT NULL,
    descriptor_version  VARCHAR(32) NOT NULL,
    computed_at         TIMESTAMP NOT NULL DEFAULT NOW(),
    PRIMARY KEY (id1, id2),
    CONSTRAINT ck_track_cosine_similarity_id_order CHECK (id1 < id2)
);
"""

CREATE_INDICES_SQL = [
    "CREATE INDEX IF NOT EXISTS track_cosine_similarity_id1_idx ON track_cosine_similarity (id1);",
    "CREATE INDEX IF NOT EXISTS track_cosine_similarity_id2_idx ON track_cosine_similarity (id2);",
]


def run():
    engine = database.engine
    engine.execute(CREATE_TABLE_SQL)
    for sql in CREATE_INDICES_SQL:
        engine.execute(sql)
    print("Migration complete: track_cosine_similarity table and indices created.")


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:
        print("Migration failed: %s" % exc, file=sys.stderr)
        sys.exit(1)
