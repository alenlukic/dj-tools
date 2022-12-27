#!/bin/bash

cd /home/alen/Developer/dj-tools
source venv/bin/activate

python src/scripts/feature_extraction/compute_mean_mel_spectrograms.py "$@"


deactivate
source venv/bin/activate

python src/scripts/feature_extraction/create_transition_match_rows.py