# Track Metadata Agent – Setup Guide

This project now targets **Python 3.9** so that all DSP libraries (Essentia, madmom) and the LangChain agent run in the same runtime. Follow the steps below to reproduce the working environment that was validated on macOS (Apple Silicon) with Homebrew.

## 1. Install Essentia via Homebrew

```bash
brew tap mtg/essentia
brew install --HEAD mtg/essentia/essentia
```

> The Essentia tap builds from source. Homebrew will install a large dependency stack (gcc, ffmpeg@2.8, python@3.9, etc.). Make sure you have the latest macOS Command Line Tools; otherwise the build can fail.

Essentia’s Python bindings are published under Homebrew’s `python@3.9`. We will link them into the project virtual environment in a later step.

## 2. Create a Python 3.9 virtual environment

```bash
cd /Users/alen/Dev/dj-tools/modules/track-metadata
./scripts/setup_venv.sh
source .venv/bin/activate
```

Upgrade pip in the fresh environment:

```bash
pip install --upgrade pip
```

## Quick commands

Run module tests:

```bash
./scripts/run_tests.sh
```

## Configuration (uses dj-tools `config/config.json`)

This module reads its directories from `dj-tools/config/config.json` under the `TRACK_METADATA` key:

- `TRACK_METADATA.DOWNLOAD_DIR`
- `TRACK_METADATA.PROCESSING_DIR`
- `TRACK_METADATA.AUGMENTED_DIR`
- `TRACK_METADATA.LOG_DIR`

You can still override these with environment variables (`TRACK_METADATA_DOWNLOAD_DIR`, etc.), but the config file is the default.

## Editor setup (Cursor / VS Code)

BasedPyright only auto-loads `pyrightconfig.json` from **workspace roots**. If you opened `/Users/alen/Dev` (or some parent folder) as the workspace, the module-level `pyrightconfig.json` will not be applied.

Recommended: open the multi-root workspace file:

```bash
cd /Users/alen/Dev/dj-tools
code dj-tools.code-workspace
```

Or in Cursor/VS Code: **File → Open Workspace from File…** and select `dj-tools/dj-tools.code-workspace`.

## 3. Make Essentia importable inside the venv

Append Essentia’s site-packages directory to the virtualenv so the bindings installed by Homebrew are visible:

```bash
echo '/opt/homebrew/opt/essentia/lib/python3.9/site-packages' \
  > .venv/lib/python3.9/site-packages/essentia-homebrew.pth
```

You can verify with:

```bash
python -c "import essentia; print(essentia.__version__)"
```

## 4. Pre-install binary build prerequisites

madmom’s wheel build expects `numpy` and `Cython` to be present in the active environment. Install them first:

```bash
pip install numpy==2.0.2 Cython==3.1.6
```

## 5. Install madmom (without build isolation)

The default isolated build fails because it cannot see the pre-installed `Cython`. Installing without isolation reuses the environment packages:

```bash
pip install --no-build-isolation madmom
```

## 6. Install the remaining Python dependencies

```bash
pip install -r requirements.txt
```

This will pull in LangChain, requests, psycopg2-binary, rich, and the other runtime libraries.

## 7. Linting and formatting (Ruff)

Ruff is configured in `pyproject.toml` for linting and formatting.

Install (if not yet installed in the venv):

```bash
pip install -r requirements-dev.txt
```

Run checks and formatting:

```bash
ruff check .
ruff format .
```

## 8. Optional verification

```bash
python -c "import essentia, madmom; print('Essentia', essentia.__version__)"
python -m metadata_agent  # or run the agent entry point you use
```

## Notes & Troubleshooting

- If `brew install --HEAD mtg/essentia/essentia` complains about missing Command Line Tools, update them via System Settings or reinstall with `xcode-select --install`.
- The installation process assumes a clean virtual environment. If you change Python versions or reinstall dependencies, start from Step 2.
- LangChain requires Python ≥3.10 for the 1.x line; the project pins the 0.3.x series, which remains compatible with Python 3.9.
- When automating setup, run these commands in the same order to avoid build failures for `madmom`.

With these steps complete, the metadata agent runs entirely within the Python 3.9 virtual environment and can access Essentia, madmom, and the LangChain tools it orchestrates.

