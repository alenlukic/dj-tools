from multiprocessing import Process, Pipe
import numpy as np
import os
import sys

from src.db import database
from src.db.entities.feature_value import FeatureValue
from src.db.entities.transition_match import TransitionMatch as TransitionMatchRow
from src.definitions.common import NUM_CORES
from src.definitions.feature_extraction import *
from src.definitions.harmonic_mixing import *
from src.lib.harmonic_mixing.transition_match_finder import TransitionMatchFinder
from src.lib.feature_extraction.track_feature import SegmentedMeanMelSpectrogram
from src.utils.errors import handle_error
from src.utils.harmonic_mixing import *


class ScriptData:
    """ Utility class encapsulating data structures used when running this script. """

    SESSION_LIMIT = 10

    def __init__(self, track_ids):
        self.transition_match_finder = TransitionMatchFinder()

        # Track collection class members
        self.all_tracks = self.transition_match_finder.tracks
        self.tracks_to_process = set(list(filter(lambda t: t.id in track_ids, self.all_tracks)))
        self.num_tracks = len(self.tracks_to_process)

        # Track / transition data
        self.track_map = {track.file_path: track for track in self.all_tracks}
        self.track_bpms = []
        self.bpm_to_tracks = defaultdict(list)
        self.transition_matches = defaultdict(lambda: {
            RelativeKey.SAME.value: [],
            RelativeKey.STEP_UP.value: [],
            RelativeKey.STEP_DOWN.value: []
        })

        # SMMS structures
        self.smms_map = defaultdict(dict)
        self.bpm_vals_in_smms_map = set()

    def reset(self):
        self.smms_map = defaultdict(dict)
        self.bpm_vals_in_smms_map = set()


def format_bpm(bpm):
    """ Format BPM as a string. """
    return str(float(bpm))


def join_tasks(tasks, task_ids):
    """ Join the provided parallel tasks. """

    for task in tasks:
        task.join()

    kill_processes(task_ids)


def kill_processes(pids):
    """ Kill all processes corresponding to provided process IDs, if they're still running. """

    for pid in pids:
        try:
            os.kill(pid, 9)
        except Exception:
            continue


def init_data(track_chunk, dropbox):
    """
    Helper function to initialize data structures needed for script.

    :param track_chunk: Chunk of tracks to process
    :param dropbox: Async data recepticle
    """

    bpm_map = defaultdict(list)
    track_bpms = []
    transition_matches = defaultdict(dict)

    for track in track_chunk:
        bpm = track.bpm
        track_bpms.append(bpm)
        formatted_bpm = format_bpm(bpm)
        bpm_map[formatted_bpm].append(track)

        (same_key, higher_key, lower_key), _ = script_data.transition_match_finder.get_transition_matches(track, False)
        for tm in same_key + higher_key + lower_key:
            match_bpm = tm.metadata[TrackDBCols.BPM]
            track_bpms.append(match_bpm)
            formatted_match_bpm = format_bpm(match_bpm)
            match_file_path = tm.metadata[TrackDBCols.FILE_PATH]
            bpm_map[formatted_match_bpm].append(script_data.track_map[match_file_path])

        transition_matches[track.id][RelativeKey.SAME.value] = same_key
        transition_matches[track.id][RelativeKey.STEP_DOWN.value] = higher_key
        transition_matches[track.id][RelativeKey.STEP_UP.value] = lower_key

    child_pid = os.getpid()
    n = len(track_chunk)
    print('[%d]:  %d tracks processed' % (child_pid, n))

    dropbox.send((bpm_map, track_bpms, transition_matches, child_pid))


def update_smms_map(frontier_tracks, dropbox):
    """
    Update SMMS map values with frontier tracks.

    :param frontier_tracks: Tracks with which to update the SMMS map
    :param dropbox: Async data recepticle
    """

    smms_map_update = defaultdict(dict)
    for ft in frontier_tracks:
        smms_map_update[format_bpm(ft.bpm)][ft.id] = SegmentedMeanMelSpectrogram(ft)

    dropbox.send((smms_map_update, os.getpid()))


def generate_match_smms_values(track_id, track_mel, matches, relative_key):
    """
    Generate SMMS scores for track's transition matches.

    :param track_id: Database ID of track
    :param track_mel: SMMS structure for track
    :param matches: Track's transition matches
    :param relative_key: Relative transition key
    """

    smms_map = script_data.smms_map
    track_map = script_data.track_map
    track_smms = track_mel.feature_value
    tm_rows = []
    for match in matches:
        try:
            match_track = track_map[match.metadata[TrackDBCols.FILE_PATH]]
            match_id = match_track.id

            if match_id == track_id:
                continue

            match_mel = smms_map[format_bpm(match_track.bpm)][match_id]
            match_smms = match_mel.feature_value
            mel_score = np.linalg.norm(track_smms - match_smms)
            match_row = {
                'on_deck_id': track_id,
                'candidate_id': match_id,
                'match_factors': {track_mel.feature_name: mel_score},
                'relative_key': relative_key
            }
            tm_rows.append(TransitionMatchRow(**match_row))

        except Exception as e:
            handle_error(e)
            continue

    return tm_rows


def generate_smms_values(tracks, relative_key, dropbox):
    """
    Helper function for computing current frontier tracks' SMMS scores.
    :param tracks: Tracks for which to compute SMMS scores
    :param relative_key: Relative transition key
    :param dropbox: Async data recepticle
    :return:
    """

    smms_map = script_data.smms_map
    match_rows = []
    for track in tracks:
        track_id = track.id
        track_std_bpm = format_bpm(track.bpm)
        if track_id not in smms_map[track_std_bpm]:
            smms_map[track_std_bpm][track_id] = SegmentedMeanMelSpectrogram(track)

        track_mel = smms_map[format_bpm(track.bpm)][track_id]
        track_matches = script_data.transition_matches[track_id][relative_key]
        match_rows.extend(generate_match_smms_values(track_id, track_mel, track_matches, relative_key))

    dropbox.send((match_rows, os.getpid()))


def get_frontier_tracks(bpm_chunk_delta):
    """
    Get frontier tracks to include in transition match results.

    :param bpm_chunk_delta: New BPM range to add
    """

    frontier_tracks = []
    if len(bpm_chunk_delta) == 0:
        return frontier_tracks

    for bpm in bpm_chunk_delta:
        std_bpm = format_bpm(bpm)

        if std_bpm not in script_data.smms_map:
            script_data.smms_map[std_bpm] = {}
            script_data.bpm_vals_in_smms_map.add(float(std_bpm))
            frontier_tracks.extend(script_data.bpm_to_tracks[std_bpm])

    return frontier_tracks


if __name__ == '__main__':
    # Initialize structs / preprocess tracks
    track_ids_to_process = set(sys.argv[1].split(','))
    script_data = ScriptData(track_ids_to_process)
    session = database.create_session()
    fv_id_set = set([fv.track_id for fv in session.query(FeatureValue).all()])

    init_data_chunks = np.array_split(script_data.tracks_to_process, NUM_CORES)
    init_data_tasks = []
    init_data_parcels = []
    for init_data_chunk in init_data_chunks:
        idc_mailbox, idc_dropbox = Pipe()
        init_data_parcels.append(idc_mailbox)

        init_data_task = Process(target=init_data, args=(init_data_chunk, idc_dropbox))
        init_data_task.daemon = True
        init_data_tasks.append(init_data_task)
        init_data_task.start()

    init_data_results = [m_parcel.recv() for m_parcel in init_data_parcels]
    init_data_task_pids = []
    for init_data_res in init_data_results:
        (partial_bpm_map, partial_track_bpms, partial_transition_matches, id_task_pid) = init_data_res
        init_data_task_pids.append(id_task_pid)
        script_data.track_bpms.extend(partial_track_bpms)
        for tm_bpm, tm_bpm_track_matches in partial_bpm_map.items():
            script_data.bpm_to_tracks[tm_bpm].extend(tm_bpm_track_matches)
        for init_data_track_id, init_data_rk_map in partial_transition_matches.items():
            for rk, rk_matches in init_data_rk_map.items():
                script_data.transition_matches[tm_bpm][rk] = rk_matches

    script_data.track_bpms = sorted(list(set([tbpm for tbpm in script_data.track_bpms])))
    join_tasks(init_data_tasks, init_data_task_pids)

    # Generate transition matches
    tm_bound_tuples = [
        (SAME_UPPER_BOUND, SAME_LOWER_BOUND, RelativeKey.SAME.value),
        (UP_KEY_UPPER_BOUND, UP_KEY_LOWER_BOUND, RelativeKey.STEP_UP.value),
        (DOWN_KEY_UPPER_BOUND, DOWN_KEY_LOWER_BOUND, RelativeKey.STEP_DOWN.value)
    ]
    try:
        for (upper_perc, lower_perc, cur_relative_key) in tm_bound_tuples:

            cur_frontier_index = 0
            for i, cur_track_bpm in enumerate(script_data.track_bpms):
                cur_upper_bound = get_bpm_bound(float(cur_track_bpm), lower_perc)
                cur_lower_bound = get_bpm_bound(float(cur_track_bpm), upper_perc)

                # Find new max BPM
                cur_bpm_chunk_delta = []
                track_frontier = script_data.track_bpms[cur_frontier_index:]
                for j, frontier_bpm in enumerate(track_frontier):
                    if frontier_bpm < cur_lower_bound:
                        frontier_index = j + 1
                        continue
                    if frontier_bpm > cur_upper_bound:
                        break
                    cur_bpm_chunk_delta.append(frontier_bpm)

                print('Iteration: %d   Current bpm: %f   Lower bound: %f   Upper bound: %f' %
                      (i, cur_track_bpm, cur_lower_bound, cur_upper_bound))

                # Prune then expand SMMS map
                prev_smms_map_keys = list(script_data.smms_map.keys())
                smms_del_count = 0
                for smms_bpm in prev_smms_map_keys:
                    if not (cur_lower_bound <= float(smms_bpm) <= cur_upper_bound):
                        script_data.bpm_vals_in_smms_map.remove(float(smms_bpm))
                        smms_del_count += len(script_data.smms_map[smms_bpm])
                        del script_data.smms_map[smms_bpm]

                # Expand track frontier
                new_frontier_tracks = get_frontier_tracks(cur_bpm_chunk_delta)

                # Update SMMS cache
                update_smms_chunks = np.array_split(new_frontier_tracks, NUM_CORES)
                update_smms_tasks = []
                update_smms_parcels = []
                for update_smms_chunk in update_smms_chunks:
                    us_mailbox, us_dropbox = Pipe()
                    update_smms_parcels.append(us_mailbox)

                    update_smms_task = Process(target=update_smms_map, args=(update_smms_chunk, us_dropbox))
                    update_smms_task.daemon = True
                    update_smms_tasks.append(update_smms_task)
                    update_smms_task.start()

                update_smms_results = [us_parcel.recv() for us_parcel in update_smms_parcels]
                update_smms_task_pids = []

                session.close()
                session = database.create_session()
                try:
                    sesh_counter = 0
                    for update_smms_result in update_smms_results:
                        (partial_smms_update, task_pid) = update_smms_result
                        update_smms_task_pids.append(task_pid)

                        for smms_bpm, smms_dict in partial_smms_update.items():
                            for smms_track_id, smms_fv in smms_dict.items():
                                script_data.smms_map[smms_bpm][smms_track_id] = smms_fv

                                if smms_track_id not in fv_id_set:
                                    if sesh_counter == ScriptData.SESSION_LIMIT:
                                        session.close()
                                        session = database.create_session()
                                        sesh_counter = 0

                                    fv_id_set.add(smms_track_id)
                                    fv_row = {
                                        'track_id': smms_track_id,
                                        'features': {
                                            Feature.SMMS.value: smms_fv.preprocess(smms_fv.feature_value)
                                        }
                                    }
                                    session.add(FeatureValue(**fv_row))
                                    session.commit()
                                    sesh_counter += 1

                finally:
                    session.close()

                join_tasks(init_data_tasks, init_data_task_pids)

                new_smms_map_size = sum([len(v) for v in script_data.smms_map.values()])
                print('----')
                print('Deleted %d SMMS map entries' % smms_del_count)
                print('New SMMS size: %d' % new_smms_map_size)
                if new_smms_map_size > 0:
                    print('Min BPM in SMMS map: %f' % min(script_data.bpm_vals_in_smms_map))
                    print('Max BPM in SMMS map: %f' % max(script_data.bpm_vals_in_smms_map))
                print('---\n')

                # Create TransitionMatch rows in parallel
                tracks_to_process = script_data.bpm_to_tracks[format_bpm(cur_track_bpm)]
                cfv_chunks = np.array_split(tracks_to_process, NUM_CORES)
                cfv_tasks = []
                cfv_parcels = []
                for cfv_chunk in cfv_chunks:
                    cfv_mailbox, cfv_dropbox = Pipe()
                    cfv_parcels.append(cfv_mailbox)

                    cfv_task = Process(target=generate_smms_values, args=(cfv_chunk, cur_relative_key, cfv_dropbox))
                    cfv_task.daemon = True
                    cfv_tasks.append(cfv_task)
                    cfv_task.start()

                cfv_results = [cfv_parcel.recv() for cfv_parcel in cfv_parcels]
                cfv_task_pids = []
                transition_match_rows = []
                for cfv_result in cfv_results:
                    (partial_match_rows, task_pid) = cfv_result
                    transition_match_rows.extend(partial_match_rows)
                    cfv_task_pids.append(task_pid)

                join_tasks(cfv_tasks, cfv_task_pids)

                # Add TransitionMatch records to DB
                session = database.create_session()
                try:
                    sesh_counter = 0
                    for tm_row in transition_match_rows:
                        try:
                            if sesh_counter == ScriptData.SESSION_LIMIT:
                                session.close()
                                session = database.create_session()
                                sesh_counter = 0

                            # Create FeatureValue entry if needed
                            for tm_track_id in [tm_row.on_deck_id, tm_row.candidate_id]:
                                if tm_track_id not in fv_id_set:
                                    tm_track_bpm = format_bpm(
                                        [tmt.bpm for tmt in script_data.tracks_to_process if tmt.id == tm_track_id][0])
                                    tm_track_smms = script_data.smms_map[tm_track_bpm][tm_track_id]
                                    fv_id_set.add(tm_track_id)
                                    fv_row = {
                                        'track_id': tm_track_id,
                                        'features': {
                                            Feature.SMMS.value: tm_track_smms.preprocess(tm_track_smms.feature_value)
                                        }
                                    }
                                    session.add(FeatureValue(**fv_row))
                                    session.commit()

                            try:
                                session.add(tm_row)
                                session.commit()
                            except Exception:
                                session.rollback()
                                continue

                            sesh_counter += 1
                        except Exception as ex:
                            handle_error(ex)
                            continue

                finally:
                    session.close()

            # Reset
            for tm_bpm, tm_bpm_track_matches in script_data.transition_matches.items():
                if cur_relative_key in tm_bpm_track_matches:
                    del tm_bpm_track_matches[cur_relative_key]
            script_data.reset()

    finally:
        database.close_all_sessions()
