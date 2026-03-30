"""Migration: create the track_trait table.

Run once:
    python -m src.scripts.migrations.20260329_create_track_trait

The track_trait table stores per-track semantic traits derived from ONNX
embedding models (Discogs-EffNet, MAEST) and librosa, replacing the coarse
binary GENRE/ARTIST/LABEL match factors with continuous probability vectors.
"""

import sys

from src.db import database


CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS track_trait (
    id                  SERIAL PRIMARY KEY,
    track_id            INTEGER NOT NULL UNIQUE REFERENCES track(id),

    voice_instrumental  FLOAT,
    danceability        FLOAT,
    bright_dark         FLOAT,
    acoustic_electronic FLOAT,
    tonal_atonal        FLOAT,
    reverb              FLOAT,

    onset_density       FLOAT,
    spectral_flatness   FLOAT,

    mood_theme          JSONB,
    genre               JSONB,
    instruments         JSONB,

    audio_events        JSONB,
    vocal_energy_ratio  FLOAT,

    trait_version       VARCHAR(32) NOT NULL,
    computed_at         TIMESTAMP NOT NULL DEFAULT NOW()
);
"""

CREATE_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS track_trait_track_id_idx
    ON track_trait (track_id);
"""


def run():
    engine = database.engine
    engine.execute(CREATE_TABLE_SQL)
    engine.execute(CREATE_INDEX_SQL)
    print("Migration complete: track_trait table and index created.")


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:
        print("Migration failed: %s" % exc, file=sys.stderr)
        sys.exit(1)
