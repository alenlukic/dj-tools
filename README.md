# dj-tools

## Overview

A toolkit for DJs that manages a music collection database, runs a multi-source track ingestion pipeline, computes audio-similarity features, and provides a live CLI assistant for finding harmonically compatible transition matches.

---

## Setup

### Prerequisites

- Python ≥ 3 (tested on 3.9)
- PostgreSQL (database name `music_collection` by default)
- ffmpeg (required for lossless-to-AIFF conversion)
- Google API credentials (optional; required only for backup/restore)

### Installation

```bash
git clone https://github.com/alenlukic/dj-tools
cd dj-tools

pip install -r requirements.txt
# or install as a package:
pip install -e .
```

Create the PostgreSQL database:

```bash
createdb music_collection
```

### Configuration

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

**Env vars:**

| Variable | Description |
|---|---|
| `DATA_ROOT` | Root directory for all data files |
| `DATA_BACKUP_RESTORE_MUSIC_DIR` | Subdirectory for restored backup files |
| `DATA_FILE_STAGING_DIR` | Temporary staging area for audio files |
| `DB_NAME` | PostgreSQL database name (default: `music_collection`) |
| `DB_USER` | PostgreSQL user |
| `DB_PASSWORD` | PostgreSQL password |
| `DB_HOST` | PostgreSQL host (default: `localhost`) |
| `DB_PORT` | PostgreSQL port (default: `5432`) |
| `FEATURE_EXTRACTION_SMMS_CACHE_SIZE` | *(deprecated)* LRU cache size for SMMS feature values (default: `4096`) |
| `HM_WEIGHT_SMMS_SCORE` | *(deprecated)* Harmonic mixing weight — SMMS spectral similarity (default: `0.24`) |
| `HM_WEIGHT_CAMELOT` | Harmonic mixing weight — Camelot key compatibility (default: `0.19`) |
| `HM_WEIGHT_BPM` | Harmonic mixing weight — BPM proximity (default: `0.17`) |
| `HM_WEIGHT_FRESHNESS` | Harmonic mixing weight — track recency (default: `0.14`) |
| `HM_WEIGHT_LABEL` | Harmonic mixing weight — same-label bonus (default: `0.12`) |
| `HM_WEIGHT_GENRE` | Harmonic mixing weight — genre match (default: `0.08`) |
| `HM_WEIGHT_ARTIST` | Harmonic mixing weight — shared artist (default: `0.04`) |
| `HM_WEIGHT_ENERGY` | Harmonic mixing weight — energy level proximity (default: `0.02`) |
| `HM_3_SD_SMMS` | *(deprecated)* 3-sigma SMMS distance threshold (default: `525.294`) |
| `HM_MAX_RESULTS` | Max transition match candidates to return (default: `50`) |
| `HM_SCORE_THRESHOLD` | Minimum composite score to include a candidate (default: `25`) |
| `HM_RESULT_THRESHOLD` | Min result count before score threshold is enforced (default: `20`) |
| `INGESTION_PIPELINE_ROOT` | Root directory for ingestion pipeline data |
| `INGESTION_PIPELINE_UNPROCESSED` | Subdir for incoming tracks (default: `unprocessed`) |
| `INGESTION_PIPELINE_PROCESSING` | Subdir for in-progress tracks (default: `processing`) |
| `INGESTION_PIPELINE_FINALIZED` | Subdir for finalized tracks (default: `finalized`) |
| `INGESTION_PIPELINE_REKORDBOX_TAG_FILE` | Rekordbox exported tag filename (default: `rekordbox_tags.txt`) |
| `INGESTION_PIPELINE_PROCESSED_MUSIC_DIR` | Final destination for processed music files |
| `TRACK_METADATA_DOWNLOAD_DIR` | Input directory for track metadata enrichment |
| `TRACK_METADATA_PROCESSING_DIR` | Working directory for track-metadata (default: `processing`) |
| `TRACK_METADATA_AUGMENTED_DIR` | Output directory for enriched tracks (default: `augmented`) |
| `TRACK_METADATA_LOG_DIR` | Log directory for track-metadata (default: `logs`) |
| `LOG_LOCATION` | Global log file path (default: `logs/logs.txt`) |
| `NUM_CORES` | CPU parallelism override (default: system CPU count) |

---

## Usage

### Mixing Assistant

**Purpose:** Interactive REPL that finds harmonically compatible transition candidates for the track currently on deck.

**When to use:** During a live set to quickly discover what to play next based on key and BPM compatibility.

**Invocation:**
```bash
python -m src.scripts.launch_assistant
```

**Commands at the prompt:**
```
match <track_title>   Find transition matches for the given track
reload                Reload track data from the database
exit                  Quit
```

**Output:** Ranked transition candidates grouped by key relationship (same key / step up / step down), scored across weighted factors (Camelot, BPM, freshness, label, genre, artist, energy, and compact audio descriptor similarity).

---

### Ingestion Pipeline

**Purpose:** Processes new audio files through a 4-step pipeline, reconciling BPM and key from Mixed In Key, Rekordbox, and raw ID3 tags into a canonical DB record, then renames and copies the final file.

**When to use:** When adding new tracks to the collection after tagging them in Mixed In Key and Rekordbox.

**Invocation (full pipeline, interactive):**
```bash
python -m src.scripts.ingestion_pipeline.run_ingestion_pipeline
```

Type `next` at each prompt to advance to the next step, or `cancel` to abort.

**Invocation (individual steps):**
```bash
python -m src.scripts.ingestion_pipeline.load_initial_tag_records       # Step 0
python -m src.scripts.ingestion_pipeline.load_post_mik_tag_records      # Step 1
python -m src.scripts.ingestion_pipeline.load_post_rekordbox_tag_records # Step 2
python -m src.scripts.ingestion_pipeline.load_final_tag_records          # Step 3
```

**Output:**
- Step 0: Track rows in DB; files copied to processing directory
- Step 1: PostMIK tag records in DB (BPM/key from Mixed In Key comment field)
- Step 2: PostRekordbox tag records in DB (BPM/key from exported Rekordbox tag file)
- Step 3: Final tag records in DB; ID3 tags written to files; files renamed and copied to `INGESTION_PIPELINE_PROCESSED_MUSIC_DIR`

---

### Compute Compact Descriptors

**Purpose:** Computes compact CQT-based audio descriptor vectors for tracks and stores them in the database. Used for audio-similarity scoring during transition matching.

**When to use:** After new tracks are ingested and before generating transition match rows.

**Invocation:**
```bash
# All tracks
python -m src.scripts.feature_extraction.compute_compact_descriptors

# Specific track IDs
python -m src.scripts.feature_extraction.compute_compact_descriptors <id1> <id2> ...
```

**Output:** `TrackDescriptor` rows written to DB. Computation is parallelized across `NUM_CORES`.

---

### Create Transition Match Rows

**Purpose:** Precomputes pairwise transition match scores for all harmonically compatible track pairs and writes them to the database.

**When to use:** After computing compact descriptors for new tracks, to make them searchable by the mixing assistant.

**Invocation:**
```bash
python -m src.scripts.feature_extraction.create_transition_match_rows
```

**Output:** `TransitionMatch` rows written to DB.

---

### Compute SMMS Features *(deprecated)*

> **Deprecated.** SMMS feature extraction has been superseded by compact descriptor computation
> above. Scripts remain under `src/scripts/feature_extraction/deprecated/` for reference.

**Invocation:**
```bash
python -m src.scripts.feature_extraction.deprecated.compute_mean_mel_spectrograms
```

---

### Sync Tags

**Purpose:** Syncs ID3 tags on disk with the corresponding DB track records.

**When to use:** After manually editing ID3 tags outside the pipeline, to bring DB records in sync.

**Invocation:**
```bash
python -m src.scripts.sync_tags
```

---

### Sync Fields

**Purpose:** Syncs DB track fields from current on-disk ID3 metadata (reverse direction of sync_tags).

**Invocation:**
```bash
python -m src.scripts.sync_fields
```

---

### Convert Lossless to AIFF

**Purpose:** Converts FLAC and WAV files to AIFF format using ffmpeg.

**When to use:** Before ingesting lossless files into the pipeline, which expects AIFF or MP3.

**Invocation:**
```bash
python -m src.scripts.convert_all_lossless_to_aiff <input_dir>
```

**Output:** AIFF files written to the same directory as the source files.

---

### Restore Backup

**Purpose:** Restores audio file backups from Google Drive by revision date.

**Invocation:**
```bash
python -m src.scripts.restore_backup <date>
```

**Output:** Files downloaded to `DATA_BACKUP_RESTORE_MUSIC_DIR`; progress tracked in `backup_progress.json`.

---

### Delete Tracks

**Purpose:** Removes track records from the database by ID.

**Invocation:**
```bash
# Individual IDs
python -m src.scripts.delete_tracks <id1> <id2> ...

# Range
python -m src.scripts.delete_tracks <start>...<end>
```

---

### Metadata Enrichment

**Purpose:** Enriches ID3 tags for audio files using MusicBrainz, Discogs, AcoustID, and an
OpenAI LLM. Writes enriched metadata back to file tags.

**Location:** `src/track_metadata/`

**Entry point:** `src/track_metadata/metadata_agent.py`
