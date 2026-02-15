#!/usr/bin/env bash
set -euo pipefail

# Review this list before running. It removes likely duplicates from the
# Downloaded Tracks directory when you are confident they exist in High Quality.

DOWNLOAD_DIR="/Volumes/Mnemosyne/Music/Downloaded Tracks"

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

