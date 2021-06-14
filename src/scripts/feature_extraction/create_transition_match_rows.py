from functools import lru_cache
import numpy as np

from src.db import database
from src.db.entities.transition_match import TransitionMatch as TransitionMatchRow
from src.definitions.feature_extraction import *
from src.lib.harmonic_mixing.transition_match_finder import TransitionMatchFinder
from src.lib.feature_extraction.track_feature import SegmentedMeanMelSpectrogram
from src.lib.error_management.reporting_handler import handle
from src.utils.harmonic_mixing import *


def get_existing_tm_id_pairs():
    return set([(tm.on_deck_id, tm.candidate_id) for tm in session.query(TransitionMatchRow).all()])


def generate_tm_id_pairs_to_create():
    def _generate_pairs(matches, relative_key):
        for match in matches:
            match_track = track_file_path_map[match.metadata[TrackDBCols.FILE_PATH]]
            match_id = match_track.id
            if (track_id, match_id) not in existing_id_pairs:
                pairs_to_create.add((track_id, match_id, relative_key))

    for track in tracks:
        track_id = track.id
        (same_key, higher_key, lower_key), _ = tm_finder.get_transition_matches(track, False)

        _generate_pairs(same_key, RelativeKey.SAME.value)
        _generate_pairs(higher_key, RelativeKey.STEP_DOWN.value)
        _generate_pairs(lower_key, RelativeKey.STEP_UP.value)


@lru_cache(1024)
def get_smms_value(track_id, db_session):
    smms = SegmentedMeanMelSpectrogram(track_id_map[track_id], db_session)
    smms.load()
    return smms


def create_transition_match_smms_rows():
    db_session = session
    rows_created = 0

    try:
        for (on_deck_id, candidate_id, relative_key) in pairs_to_create:
            on_deck_smms = get_smms_value(on_deck_id, db_session).get_feature()
            match_smms = get_smms_value(candidate_id, db_session).get_feature()
            mel_score = np.linalg.norm(on_deck_smms - match_smms)
            match_row = {
                'on_deck_id': on_deck_id,
                'candidate_id': candidate_id,
                'match_factors': {Feature.SMMS.value: mel_score},
                'relative_key': relative_key
            }

            if rows_created % 100 == 0:
                print('%d rows created' % rows_created)
                print('Cache info: %s\n' % str(get_smms_value.cache_info()))

            db_session = database.recreate_session_contingent(db_session)
            if db_session.guarded_add(TransitionMatchRow(**match_row)):
                rows_created += 1

    except Exception as e:
        handle(e)

    finally:
        db_session.close()


if __name__ == '__main__':
    # Load session data
    session = database.create_session()
    tm_finder = TransitionMatchFinder()

    # Load track data
    tracks = tm_finder.tracks
    track_id_map = {track.id: track for track in tracks}
    track_file_path_map = {track.file_path: track for track in tracks}

    # Generate pair IDs to create
    existing_id_pairs = get_existing_tm_id_pairs()
    pairs_to_create = set()
    generate_tm_id_pairs_to_create()
    pairs_to_create = sorted(list(pairs_to_create), key=lambda x: x[0], reverse=True)
    print('%d entries to create' % len(pairs_to_create))

    # Create DB rows
    create_transition_match_smms_rows()
