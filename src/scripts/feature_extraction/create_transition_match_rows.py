import argparse
from functools import lru_cache
import numpy as np

from src.db import database
from src.db.entities.transition_match import TransitionMatch as TransitionMatchRow
from src.definitions.feature_extraction import *
from src.lib.harmonic_mixing.definitions.transition_match_finder import TransitionMatchFinder
from src.lib.feature_extraction.track_feature import SegmentedMeanMelSpectrogram
from src.lib.error_management.service import handle
from src.utils.file_operations import stage_tracks
from src.utils.harmonic_mixing import *


cache_session = database.create_session()


def get_existing_match_pairs():
    return set([(tm.on_deck_id, tm.candidate_id) for tm in session.query(TransitionMatchRow).all()])


def generate_track_pairs(track_id, matches, relative_key):
    for match in matches:
        match_track = track_file_path_map[match.metadata[TrackDBCols.FILE_PATH]]
        match_id = match_track.id

        if (track_id, match_id) not in existing_pairs:
            pairs_to_create.add((track_id, match_id, relative_key))
            stage_queue[match_id] = match_track


def generate_match_pairs():
    for track in tracks:
        track_id = track.id
        (same_key, higher_key, lower_key), _ = tm_finder.get_transition_matches(track, False)

        generate_track_pairs(track_id, same_key, RelativeKey.SAME.value)
        generate_track_pairs(track_id, higher_key, RelativeKey.STEP_DOWN.value)
        generate_track_pairs(track_id, lower_key, RelativeKey.STEP_UP.value)

        stage_queue[track_id] = track


@lru_cache(get_config_value(['FEATURE_EXTRACTION', 'SMMS_CACHE_SIZE']))
def get_smms_value(track_id):
    smms = SegmentedMeanMelSpectrogram(track_id_map[track_id])
    smms.load(cache_session)
    return smms


def create_transition_match_smms_rows(sesh, compute_missing):
    db_session = sesh
    num_to_create = len(pairs_to_create)
    rows_created = 0

    try:
        for i, (on_deck_id, candidate_id, relative_key) in enumerate(pairs_to_create):
            try:
                on_deck_smms = get_smms_value(on_deck_id).get_feature(compute_missing)
                if on_deck_smms is None:
                    continue

                match_smms = get_smms_value(candidate_id).get_feature(compute_missing)
                if match_smms is None:
                    continue

                mel_score = np.linalg.norm(on_deck_smms - match_smms)
                match_row = {
                    'on_deck_id': on_deck_id,
                    'candidate_id': candidate_id,
                    'match_factors': {Feature.SMMS.value: mel_score},
                    'relative_key': relative_key
                }

                if i % 100 == 0:
                    print('%d of %d pairs processed' % (i, num_to_create))
                    print('%d rows created' % rows_created)
                    print('Cache info: %s\n' % str(get_smms_value.cache_info()))

                # noinspection PyShadowingNames, PyUnboundLocalVariable
                db_session = database.recreate_session_contingent(db_session)
                db_session.guarded_add(TransitionMatchRow(**match_row))
                rows_created += 1

            except Exception as e:
                handle(e)
                continue

    except Exception as e:
        handle(e)

    finally:
        db_session.close()
        cache_session.close()


def get_args():
    parser = argparse.ArgumentParser(description='Compute mean Mel spectrogram features.')
    parser.add_argument('--compute-missing', '-c', action='store_true', dest='compute_missing', default=False,
                        help='Attempt to compute missing feature values')

    return parser.parse_args()


if __name__ == '__main__':
    args = get_args()

    # Load session data
    session = database.create_session()
    tm_finder = TransitionMatchFinder()

    # Load track data
    tracks = tm_finder.tracks
    track_id_map = {track.id: track for track in tracks}
    track_file_path_map = {track.file_path: track for track in tracks}
    existing_pairs = get_existing_match_pairs()

    # Generate pair IDs to create
    pairs_to_create = set()
    stage_queue = {}
    generate_match_pairs()

    # Stage tracks
    stage_tracks(stage_queue.values())

    # Create DB rows
    pairs_to_create = sorted(list(pairs_to_create), key=lambda x: x[0], reverse=True)
    create_transition_match_smms_rows(session, args.compute_missing)
