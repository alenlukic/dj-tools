import json
import numpy as np
from sqlalchemy import Integer, JSON

from src.db.column import DBColumn
from src.db.database import Database
from src.db.entities.feature_value import FeatureValue
from src.db.entities.track import Track
from src.db.entities.transition_match import TransitionMatch as TransitionMatchRow
from src.db.table import DBTable
from src.definitions.data_management import TrackDBCols
from src.definitions.feature_extraction import *
from src.lib.assistant.assistant import Assistant
from src.lib.feature_extraction.track_feature import SegmentedMeanMelSpectrogram
from src.utils.errors import handle_error


def create_tables():
    metadata = database.get_metadata()

    # feature_value table
    fv = 'feature_value'
    fv_columns = [
        DBColumn('id', Integer).as_index().as_primary_key().as_unique().create(metadata, fv),
        DBColumn('track_id', Integer).as_index().as_primary_key().as_foreign_key('track.id').as_unique().create(
            metadata, fv),
        DBColumn('features', JSON).create(metadata, fv)
    ]
    DBTable(fv, metadata, fv_columns)
    metadata.create_all()

    tm = 'transition_match'
    tm_columns = [
        DBColumn('id', Integer).as_index().as_primary_key().as_unique().create(metadata, tm),
        DBColumn('on_deck_id', Integer).as_index().as_primary_key().as_foreign_key(
            'feature_value.track_id').as_unique().create(metadata, tm),
        DBColumn('candidate_id', Integer).as_index().as_primary_key().as_foreign_key(
            'feature_value.track_id').as_unique().create(metadata, tm),
        DBColumn('match_factors', JSON).create(metadata, tm)
    ]
    DBTable(tm, metadata, tm_columns)
    metadata.create_all()


def create_feature_row(track, track_mel):
    feature_row = {'track_id': track.id, 'features': {track_mel.feature_name: track_mel.feature_value}}
    print(str(feature_row))
    session.add(FeatureValue(**feature_row))
    # session.commit()


def generate_mel_scores(track_id, track_mel, matches, relative_key, mel_scores):
    track_smms = track_mel.feature_value
    for match in matches:
        try:
            match_track = track_map[match.metadata[TrackDBCols.FILE_PATH]]
            match_id = match_track.id

            if (track_id, match_id) in mel_scores:
                continue
            mel_scores.add((track_id, match_id))

            match_mel = SegmentedMeanMelSpectrogram(match_track)
            match_smms = match_mel.feature_value
            mel_score = np.linalg.norm(track_smms - match_smms)

            tm_row = {'on_deck_id': track_id, 'candidate_id': match_id,
                      'match_factors': {track_mel.feature_name: mel_score}, 'relative_key': relative_key.value}
            print(str(tm_row))
            session.add(TransitionMatchRow(**tm_row))
            # session.commit()
        except Exception as e:
            handle_error(e)
            continue


def compute_feature_values():
    mel_scores = set()
    for track in tracks:

        try:
            track_mel = SegmentedMeanMelSpectrogram(track)
            create_feature_row(track, track_mel)
        except Exception as e:
            handle_error(e)
            continue

        track_id = track.id
        same_key, higher_key, lower_key = assistant.get_transition_matches(track.title)
        generate_mel_scores(track_id, track_mel, same_key, RelativeKey.SAME, mel_scores)
        generate_mel_scores(track_id, track_mel, higher_key, RelativeKey.STEP_DOWN, mel_scores)
        generate_mel_scores(track_id, track_mel, lower_key, RelativeKey.STEP_UP, mel_scores)


if __name__ == '__main__':
    database = Database()
    session = database.create_session()
    assistant = Assistant()
    tracks = assistant.tracks
    track_map = {track.file_path: track for track in tracks}
    compute_feature_values()
    # session.commit()
