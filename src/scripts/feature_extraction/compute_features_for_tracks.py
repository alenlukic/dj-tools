"""Combined script: compute traits then cosine similarities for specified tracks.

Requires at least one track ID. Runs trait extraction first (so that
descriptors/traits exist for scoring), then computes cosine similarities
for the given tracks against their harmonic-match candidates.

Usage:
    python -m src.scripts.feature_extraction.compute_features_for_tracks 42 101 200
"""

import sys

from src.db import database
from src.errors import handle
from src.scripts.feature_extraction import compute_track_traits
from src.scripts.feature_extraction import compute_cosine_similarities


def run(track_ids):
    if not track_ids:
        print("Error: at least one track ID is required.")
        sys.exit(1)

    print("=== Step 1/2: Computing traits for %d track(s) ===" % len(track_ids))
    try:
        session = database.create_session()
        compute_track_traits.run(track_ids, session)
    except Exception as exc:
        handle(exc)
        print(
            "Warning: trait computation encountered errors; continuing to cosine step."
        )

    print(
        "\n=== Step 2/2: Computing cosine similarities for %d track(s) ==="
        % len(track_ids)
    )
    try:
        session = database.create_session()
        compute_cosine_similarities.run(track_ids, session)
    except Exception as exc:
        handle(exc)
        print("Warning: cosine computation encountered errors.")

    print("\nAll steps complete.")


if __name__ == "__main__":
    _args = sys.argv
    if len(_args) < 2:
        print(
            "Usage: python -m src.scripts.feature_extraction"
            ".compute_features_for_tracks <track_id> [track_id ...]"
        )
        sys.exit(1)
    run(set(int(t) for t in _args[1:]))
