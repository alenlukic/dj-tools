#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${ROOT_DIR}/.venv"

if [[ ! -f "${VENV_DIR}/bin/activate" ]]; then
  echo "[error] venv not found at ${VENV_DIR}. Run ./scripts/setup_venv.sh first." >&2
  exit 1
fi

# shellcheck disable=SC1091
source "${VENV_DIR}/bin/activate"

python -m pytest -q "${ROOT_DIR}/tests"

