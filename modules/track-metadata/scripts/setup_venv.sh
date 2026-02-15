#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${ROOT_DIR}/.venv"

function info() {
  printf '\033[1;34m[info]\033[0m %s\n' "$1"
}

function warn() {
  printf '\033[1;33m[warn]\033[0m %s\n' "$1"
}

function die() {
  printf '\033[1;31m[error]\033[0m %s\n' "$1" >&2
  exit 1
}

PYTHON_BIN="${TRACK_METADATA_PYTHON_BIN:-}"
INSTALL_AUDIO=0

if [[ $# -gt 0 ]]; then
  for arg in "$@"; do
    case "$arg" in
      --audio)
        INSTALL_AUDIO=1
        ;;
      --python=*)
        PYTHON_BIN="${arg#--python=}"
        ;;
      *)
        die "Unknown argument: ${arg} (supported: --audio, --python=/path/to/python3.9)"
        ;;
    esac
  done
fi

if [[ -z "${PYTHON_BIN}" ]]; then
  if command -v python3.9 >/dev/null 2>&1; then
    PYTHON_BIN="python3.9"
  elif command -v /opt/homebrew/opt/python@3.9/bin/python3.9 >/dev/null 2>&1; then
    PYTHON_BIN="/opt/homebrew/opt/python@3.9/bin/python3.9"
  else
    die "Python 3.9 not found. Install python3.9 or pass --python=/path/to/python3.9"
  fi
fi

info "Using Python: ${PYTHON_BIN}"
info "Creating venv at ${VENV_DIR}"
"${PYTHON_BIN}" -m venv "${VENV_DIR}"

# shellcheck disable=SC1091
source "${VENV_DIR}/bin/activate"

info "Upgrading pip"
python -m pip install --upgrade pip

info "Installing module dependencies"
pip install -r "${ROOT_DIR}/requirements.txt"
pip install -r "${ROOT_DIR}/requirements-dev.txt"

if [[ "${INSTALL_AUDIO}" -eq 1 ]]; then
  if [[ -f "${ROOT_DIR}/requirements-audio.txt" ]]; then
    info "Installing optional audio/DSP dependencies"
    pip install --no-build-isolation -r "${ROOT_DIR}/requirements-audio.txt"
  else
    warn "requirements-audio.txt not found; skipping audio deps"
  fi
else
  warn "Skipping audio/DSP deps (pass --audio to install madmom/Cython)"
fi

info "Done. Activate with: source \"${VENV_DIR}/bin/activate\""

