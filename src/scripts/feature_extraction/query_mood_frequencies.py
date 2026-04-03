"""One-off script: aggregate mood_theme label frequencies across all TrackTrait rows.

Expands each JSONB key (a mood label that cleared the probability threshold) and
counts how many tracks it appears in, returning results in reverse frequency order.

Usage:
    python -m src.scripts.feature_extraction.query_mood_frequencies
"""

from sqlalchemy import text

from src.db import database


def main() -> None:
    engine = database.get_engine()

    sql = text(
        """
        SELECT
            mood,
            COUNT(*) AS track_count
        FROM
            track_trait,
            jsonb_object_keys(mood_theme) AS mood
        WHERE
            mood_theme IS NOT NULL
        GROUP BY
            mood
        ORDER BY
            track_count DESC,
            mood ASC
        """
    )

    with engine.connect() as conn:
        rows = conn.execute(sql).fetchall()

    if not rows:
        print("No mood_theme data found.")
        return

    col_width = max(len(r[0]) for r in rows)
    print(f"{'Mood':<{col_width}}  {'Tracks':>7}")
    print("-" * (col_width + 10))
    for mood, count in rows:
        print(f"{mood:<{col_width}}  {count:>7}")


if __name__ == "__main__":
    main()
