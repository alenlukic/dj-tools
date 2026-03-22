"""Migration: create the track_descriptor table.

Run once:
    python -m src.scripts.migrations.20260321_add_track_descriptor

The track_descriptor table stores per-track compact audio descriptors (75-dim
float32 vectors packed as BYTEA) replacing the large mel-spectrogram JSON stored
in feature_value. Existing feature_value and transition_match data are preserved.
"""

import sys

from src.db import database


CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS track_descriptor (
    id                 SERIAL PRIMARY KEY,
    track_id           INTEGER NOT NULL UNIQUE REFERENCES track(id),
    global_vector      BYTEA NOT NULL,
    intro_vector       BYTEA,
    outro_vector       BYTEA,
    descriptor_version VARCHAR(32) NOT NULL,
    computed_at        TIMESTAMP NOT NULL DEFAULT NOW()
);
"""

CREATE_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS track_descriptor_track_id_idx
    ON track_descriptor (track_id);
"""


def run():
    engine = database.engine
    engine.execute(CREATE_TABLE_SQL)
    engine.execute(CREATE_INDEX_SQL)
    print("Migration complete: track_descriptor table and index created.")


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:
        print("Migration failed: %s" % exc, file=sys.stderr)
        sys.exit(1)
