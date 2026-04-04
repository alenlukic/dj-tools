"""Migration: create the scoring_weight_override table.

Run once:
    python -m src.scripts.migrations.20260404_create_scoring_weight_override

Single-row table (keyed by ``scope``) that persists user-modified scoring
weights as JSON so they survive process restarts.  The current implementation
uses ``scope='global'`` exclusively.
"""

import sys

from src.db import database


CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS scoring_weight_override (
    id              SERIAL PRIMARY KEY,
    scope           VARCHAR(32) NOT NULL UNIQUE DEFAULT 'global',
    weights_json    TEXT NOT NULL,
    updated_at      TIMESTAMP NOT NULL DEFAULT NOW()
);
"""


def run():
    engine = database.engine
    engine.execute(CREATE_TABLE_SQL)
    print("Migration complete: scoring_weight_override table created.")


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:
        print("Migration failed: %s" % exc, file=sys.stderr)
        sys.exit(1)
