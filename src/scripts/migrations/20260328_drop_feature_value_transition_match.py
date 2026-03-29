"""Migration: drop feature_value and transition_match tables.

Run once after verifying no application code depends on these tables:
    python -m src.scripts.migrations.20260328_drop_feature_value_transition_match

The feature_value table stored large mel-spectrogram JSON blobs for the
deprecated SMMS feature extractor. The transition_match table stored
pre-computed SMMS Euclidean distance scores. Both are superseded by
compact descriptors stored in track_descriptor and cosine similarity
computed at query time.
"""

import sys

from src.db import database


DELETE_FEATURE_VALUE_SQL = "DELETE FROM feature_value;"
DELETE_TRANSITION_MATCH_SQL = "DELETE FROM transition_match;"
DROP_FEATURE_VALUE_SQL = "DROP TABLE IF EXISTS feature_value;"
DROP_TRANSITION_MATCH_SQL = "DROP TABLE IF EXISTS transition_match;"


def run():
    with database.engine.begin() as conn:
        conn.execute(DELETE_TRANSITION_MATCH_SQL)
        conn.execute(DELETE_FEATURE_VALUE_SQL)
        conn.execute(DROP_TRANSITION_MATCH_SQL)
        conn.execute(DROP_FEATURE_VALUE_SQL)
    print("Migration complete: feature_value and transition_match tables dropped.")


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:
        print("Migration failed: %s" % exc, file=sys.stderr)
        sys.exit(1)
