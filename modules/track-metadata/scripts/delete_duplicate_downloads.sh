#!/usr/bin/env bash
set -euo pipefail

# Review this list before running. It removes likely duplicates from the
# Downloaded Tracks directory when you are confident they exist in High Quality.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DJTOOLS_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
CONFIG_PATH="${DJTOOLS_ROOT}/config/config.json"

DOWNLOAD_DIR="${TRACK_METADATA_DOWNLOAD_DIR:-}"
if [[ -z "${DOWNLOAD_DIR}" && -f "${CONFIG_PATH}" ]]; then
  if command -v python3 >/dev/null 2>&1; then
    DOWNLOAD_DIR="$(python3 - <<'PY'
import json
from pathlib import Path

cfg_path = Path(r"""'"${CONFIG_PATH}"'""")
cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
tm = cfg.get("TRACK_METADATA", {})
value = tm.get("DOWNLOAD_DIR", "")
print(value or "")
PY
)"
  fi
fi

if [[ -z "${DOWNLOAD_DIR}" ]]; then
  DOWNLOAD_DIR="/Volumes/Mnemosyne/Music/Downloaded Tracks"
fi

files=(
)

echo "Files that would be deleted from: $DOWNLOAD_DIR"
for f in "${files[@]}"; do
  echo " - $f"
done

read -p "Proceed with deletion? (y/N) " ans
if [[ "$ans" =~ ^[Yy]$ ]]; then
  for f in "${files[@]}"; do
    target="${DOWNLOAD_DIR}/${f}"
    if [[ -f "$target" ]]; then
      echo "Deleting $target"
      rm -- "$target"
    else
      echo "Skipping (not found): $target"
    fi
  done
else
  echo "Aborted."
fi

