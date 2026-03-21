# track-metadata

## Overview

Enriches audio file metadata by querying MusicBrainz, Discogs, and AcoustID, resolving any remaining gaps with an OpenAI LLM, and writing the final tags back to the file.

---

## Setup

### Prerequisites

- Python 3.9
- ffmpeg (audio decoding; install instructions below)
- Homebrew (macOS, for Essentia — only needed if you want audio BPM/key estimation)
- A `.env` file at the dj-tools repo root (see [Configuration](#configuration))

### Installation

**1. Create the Python 3.9 virtual environment:**

```bash
cd modules/track-metadata

# Standard setup (no audio analysis):
./scripts/setup_venv.sh

# With BPM/key audio analysis (installs madmom + Cython):
./scripts/setup_venv.sh --audio

source .venv/bin/activate
```

**2. Install ffmpeg:**

```bash
./scripts/install_cli_dependencies.sh
```

This runs `brew install ffmpeg` on macOS or uses apt/dnf/pacman on Linux.

**3. (macOS only, optional) Install Essentia for audio analysis:**

Essentia provides beat and key estimation. Skip this if you don't need audio-based BPM/key resolution.

```bash
brew tap mtg/essentia
brew install --HEAD mtg/essentia/essentia
```

Link Essentia's bindings into the virtual environment:

```bash
echo '/opt/homebrew/opt/essentia/lib/python3.9/site-packages' \
  > .venv/lib/python3.9/site-packages/essentia-homebrew.pth
```

Verify:

```bash
python -c "import essentia; print(essentia.__version__)"
```

> If `brew install` fails, update macOS Command Line Tools: `xcode-select --install`.

---

### Configuration

Configuration is loaded from the `.env` file at the dj-tools repo root. Copy `.env.example` to `.env` if you haven't already:

```bash
cp ../../.env.example ../../.env
```

**Env vars:**

| Variable | Required | Description |
|---|---|---|
| `TRACK_METADATA_DOWNLOAD_DIR` | Yes | Directory where new audio files are placed for processing |
| `TRACK_METADATA_PROCESSING_DIR` | No | Working directory for in-progress files (default: `processing`) |
| `TRACK_METADATA_AUGMENTED_DIR` | No | Output directory for enriched files (default: `augmented`) |
| `TRACK_METADATA_LOG_DIR` | No | Log directory (default: `logs`) |
| `TRACK_METADATA_RUN_START` | No | Override run timestamp used in log file naming |
| `DISCOGS_TOKEN` | No | Discogs personal access token — enables Discogs label/genre lookups |
| `ACOUSTID_API_KEY` | No | AcoustID API key — enables audio fingerprint identification |
| `OPENAI_API_KEY` | No | OpenAI API key — enables LLM resolution of remaining missing fields |
| `OPENAI_METADATA_MODEL` | No | OpenAI model to use (default: `gpt-4o-mini`) |
| `MUSIC_METADATA_USER_AGENT` | No | User-Agent header for MusicBrainz/Discogs HTTP requests |

The module works without any API keys. MusicBrainz is queried without authentication. Each optional service adds a layer of metadata coverage.

---

## Usage

### Metadata Agent

**Purpose:** Discovers new audio files, enriches their metadata from external sources, writes final ID3 tags, and deposits renamed files into the augmented directory.

**When to use:** After downloading new tracks and placing them in `TRACK_METADATA_DOWNLOAD_DIR`, before ingesting them into the main dj-tools pipeline.

**Invocation:**
```bash
cd modules/track-metadata
source .venv/bin/activate
python -m metadata_agent
```

**What it does, step by step:**

1. Creates `processing/`, `augmented/`, and `logs/` directories if missing
2. Removes any files in `augmented/` that have no readable title tag
3. Clears the `processing/` directory
4. Scans `TRACK_METADATA_DOWNLOAD_DIR` for `.mp3` and `.aiff` files not already present in `augmented/`
5. For each file:
   - Copies it to `processing/`
   - Reads existing ID3 tags
   - Queries AcoustID (if configured) to identify the recording by audio fingerprint
   - Queries MusicBrainz to fill title, artist, album, label, genre, year
   - Queries Discogs (if configured) to supplement label and genre
   - If fields are still missing, calls the OpenAI LLM with all candidate results to resolve them
   - Runs madmom BPM/key estimation (if installed) for any still-missing BPM or key
   - Writes final tags back to the file
   - Renames the file to `Artist - Title.ext`
   - Copies the renamed file to `TRACK_METADATA_AUGMENTED_DIR`

**Output:**

- Enriched, renamed audio files in `TRACK_METADATA_AUGMENTED_DIR`
- Structured JSON log in `TRACK_METADATA_LOG_DIR/{timestamp}.log` containing per-file metadata decisions and raw API responses

---

### Run Tests

**Purpose:** Runs the full test suite for this module.

**Invocation:**
```bash
./scripts/run_tests.sh
```

Or directly:
```bash
source .venv/bin/activate
pytest -q tests/
```

**Output:** Test results for 103 tests covering file utilities, ID3 tag read/write, audio feature analysis, and metadata hydration (with mocked network calls).

---

### Lint and Format

**Purpose:** Checks code quality with Ruff.

**Invocation:**
```bash
source .venv/bin/activate
ruff check .
ruff format .
```

---

## Notes

- madmom requires Python 3.9 and `--no-build-isolation` during installation (handled automatically by `setup_venv.sh --audio`).
- LangChain is not used. Metadata resolution uses the OpenAI structured outputs API directly.
- All API services are optional and degrade gracefully; the agent will use whatever sources are configured.
- Files already present in `augmented/` are skipped on subsequent runs.
