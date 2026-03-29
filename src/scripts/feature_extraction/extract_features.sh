#!/bin/bash

cd /home/alen/Developer/dj-tools

source venv/bin/activate
python src/scripts/feature_extraction/compute_compact_descriptors.py "$@"
python src/scripts/feature_extraction/compute_track_traits.py "$@"
