"""Migration: create artist_mapping, genre_mapping, and label_mapping tables.

Run once after verifying a DB backup exists:
    python -m src.scripts.migrations.20260328_add_mapping_tables

Creates three canonicalization tables and seeds them with the data that was
previously hard-coded in src/data_management/config.py (GENRE_CANON, LABEL_CANON)
and src/data_management/utils.py (transform_artist, transform_label rules).
"""

import sys

from src.db import database


CREATE_GENRE_MAPPING_SQL = """
CREATE TABLE IF NOT EXISTS genre_mapping (
    id              SERIAL PRIMARY KEY,
    raw_genre       VARCHAR(255) NOT NULL UNIQUE,
    canonical_genre VARCHAR(255) NOT NULL
);
CREATE INDEX IF NOT EXISTS genre_mapping_raw_idx ON genre_mapping (raw_genre);
"""

CREATE_LABEL_MAPPING_SQL = """
CREATE TABLE IF NOT EXISTS label_mapping (
    id              SERIAL PRIMARY KEY,
    raw_label       VARCHAR(255) NOT NULL UNIQUE,
    canonical_label VARCHAR(255) NOT NULL,
    match_type      VARCHAR(32)  NOT NULL,
    exclude_pattern VARCHAR(255)
);
CREATE INDEX IF NOT EXISTS label_mapping_raw_idx ON label_mapping (raw_label);
"""

CREATE_ARTIST_MAPPING_SQL = """
CREATE TABLE IF NOT EXISTS artist_mapping (
    id               SERIAL PRIMARY KEY,
    raw_artist       VARCHAR(255) NOT NULL UNIQUE,
    canonical_artist VARCHAR(255) NOT NULL,
    match_type       VARCHAR(32)  NOT NULL
);
CREATE INDEX IF NOT EXISTS artist_mapping_raw_idx ON artist_mapping (raw_artist);
"""

# Seed data: formerly GENRE_CANON in src/data_management/config.py
SEED_GENRE_SQL = """
INSERT INTO genre_mapping (raw_genre, canonical_genre) VALUES
    ('Psy-Trance', 'Psytrance')
ON CONFLICT (raw_genre) DO NOTHING;
"""

# Seed data: word-token entries formerly in LABEL_CANON (config.py),
# parent-strip rules and substring rules formerly in transform_label (utils.py).
SEED_LABEL_SQL = """
INSERT INTO label_mapping (raw_label, canonical_label, match_type, exclude_pattern) VALUES
    -- word-token normalisations (LABEL_CANON)
    ('joof',         'JOOF',              'word', NULL),
    ('shinemusic',   'Shine Music',       'word', NULL),
    ('vii',          'VII',               'word', NULL),
    ('rfr',          'RFR',               'word', NULL),
    ('cdr',          'CDR',               'word', NULL),
    ('knm',          'KNM',               'word', NULL),
    ('umc',          'UMC',               'word', NULL),
    ('uv',           'UV',                'word', NULL),
    ('nx1',          'NX1',               'word', NULL),
    ('srx',          'SRX',               'word', NULL),
    ('kgg',          'KGG',               'word', NULL),
    ('dpe',          'DPE',               'word', NULL),
    ('kmx',          'KMX',               'word', NULL),
    ('dbx',          'DBX',               'word', NULL),
    ('x7m',          'X7M',               'word', NULL),
    ('cr2',          'CR2',               'word', NULL),
    ('dfc',          'DFC',               'word', NULL),
    ('kd',           'KD',                'word', NULL),
    ('tk',           'TK',                'word', NULL),
    ('uk',           'UK',                'word', NULL),
    ('l.i.e.s.',     'L.I.E.S.',          'word', NULL),
    ('n.a.m.e',      'N.A.M.E',           'word', NULL),
    ('d.o.c.',       'D.O.C.',            'word', NULL),
    -- parent-label strip rules (formerly parent_label_parens in transform_label)
    ('(Armada)',       '',  'strip_suffix', NULL),
    ('(Armada Music)', '',  'strip_suffix', NULL),
    ('(Spinnin)',      '',  'strip_suffix', NULL),
    -- substring replacement rules (formerly if-blocks in transform_label)
    ('hommega',      'HOMmega Productions',   'substring', NULL),
    ('pure trance',  'Pure Trance Recordings','substring', 'pure trance progressive')
ON CONFLICT (raw_label) DO NOTHING;
"""

# Seed data: artist normalisation rules formerly in transform_artist (utils.py).
SEED_ARTIST_SQL = """
INSERT INTO artist_mapping (raw_artist, canonical_artist, match_type) VALUES
    ('Tiësto',    'Tiesto', 'exact'),
    ('DJ Tiësto', 'Tiesto', 'exact'),
    ('DJ Tiesto', 'Tiesto', 'exact'),
    ('Kamaya Painters', 'Kamaya Painters', 'contains')
ON CONFLICT (raw_artist) DO NOTHING;
"""


def run():
    with database.engine.begin() as conn:
        conn.execute(CREATE_GENRE_MAPPING_SQL)
        conn.execute(CREATE_LABEL_MAPPING_SQL)
        conn.execute(CREATE_ARTIST_MAPPING_SQL)
        conn.execute(SEED_GENRE_SQL)
        conn.execute(SEED_LABEL_SQL)
        conn.execute(SEED_ARTIST_SQL)
    print("Migration complete: genre_mapping, label_mapping, artist_mapping created and seeded.")


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:
        print("Migration failed: %s" % exc, file=sys.stderr)
        sys.exit(1)
