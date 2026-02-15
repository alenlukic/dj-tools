#!/usr/bin/env bash
set -euo pipefail

# Review this list before running. It removes likely duplicates from the
# Downloaded Tracks directory when you are confident they exist in High Quality.

DOWNLOAD_DIR="/Volumes/Mnemosyne/Music/Downloaded Tracks"

files=(
  "The Groovaholic's - Wake Up The Funk (Ragel Mood Remix).aiff"
  "Silent Space - Miracle (Original Long Trance Mix).aiff"
  "POETRY - Picking Up The Pace (Extended Version).aiff"
  "DAFT PUNK - AROUND THE WORLD (WESTEND EDIT).aiff"
  "M83 - Midnight City (Versaro & Landau Remix).aiff"
  "Silent Space - Miracle (Hard Trance Remix).aiff"
  "Akon - Beautiful (Klein Rietje - remix).aiff"
  "SWART - did ya think this was a salsa.aiff"
  "CIS - New Phone (Extended Version).aiff"
  "Lucas Boston - Hazard 2 Society.aiff"
  "Music Sounds Better With Groove (Loatz edit).mp3"
  "Die Antwoord - I Fink U Freeky  (HUMAN404 Edit) 24_44.1.aiff"
  "Funk Assault - Sacred Arsenal.aiff"
  "JBox - HOT PEOPLE IN MY HOUSE.aiff"
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

