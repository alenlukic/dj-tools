"""Migration: mark existing trait rows as needing re-extraction.

Sets trait_version to 'outdated' for any row not at the current version,
signalling the backfill script to recompute them with raw-score storage
(version 4+). The backfill re-runs the ONNX pipeline and stores unfiltered
outputs; display-layer filtering is applied at read time.

Run once:
    python -m src.scripts.migrations.20260403_update_genre_mood_filtering

Safe to re-run — only touches rows whose trait_version is not current.
"""

import sys

from src.db import database
from src.feature_extraction.config import TRAIT_VERSION


UPDATE_SQL = """
UPDATE track_trait
SET trait_version = 'outdated'
WHERE trait_version != '%s';
"""


def run():
    engine = database.engine
    result = engine.execute(UPDATE_SQL % TRAIT_VERSION)
    count = result.rowcount
    print(
        "Migration complete: %d row(s) marked as outdated." % count
    )


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:
        print("Migration failed: %s" % exc, file=sys.stderr)
        sys.exit(1)
