"""Migration: enable pg_trgm extension and create trigram index on track.title.

Run once:
    python -m src.scripts.migrations.enable_pg_trgm_track_title

Enables fuzzy autocomplete search via pg_trgm similarity on track titles.
"""

import sys

from src.db import database


ENABLE_EXTENSION_SQL = "CREATE EXTENSION IF NOT EXISTS pg_trgm;"

CREATE_INDEX_SQL = (
    "CREATE INDEX IF NOT EXISTS track_title_trgm_idx "
    "ON track USING gin (title gin_trgm_ops);"
)


def run():
    engine = database.engine
    engine.execute(ENABLE_EXTENSION_SQL)
    engine.execute(CREATE_INDEX_SQL)
    print("Migration complete: pg_trgm enabled, GIN index on track.title created.")


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:
        print("Migration failed: %s" % exc, file=sys.stderr)
        sys.exit(1)
