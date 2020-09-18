from multiprocessing import Process, Pipe
import numpy as np
import os

from src.db.database import Database
from src.db.entities.feature_value import FeatureValue
from src.db.entities.transition_match import TransitionMatch as TransitionMatchRow
from src.definitions.common import NUM_CORES
from src.definitions.feature_extraction import *
from src.definitions.harmonic_mixing import *
from src.lib.harmonic_mixing.transition_match import TransitionMatch
from src.lib.harmonic_mixing.transition_match_finder import TransitionMatchFinder
from src.lib.feature_extraction.track_feature import SegmentedMeanMelSpectrogram
from src.utils.errors import handle_error
from src.utils.harmonic_mixing import *


SESSION_LIMIT = 10


class SMMSData:
    """ Utility class encapsulating data structures used when running the script. """

    def __init__(self):
        self.transition_match_finder = TransitionMatchFinder()

        # Track collection class members
        self.all_tracks = self.transition_match_finder.tracks
        self.num_tracks = len(self.all_tracks)

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
    return str(float(bpm))


def join_tasks(tasks):
    """ Join the provided parallel tasks. """
    for task in tasks:
        task.join()


def kill_processes(pids):
    """ Kill all processes corresponding to provided process IDs, if they're still running. """

    for pid in pids:
        try:
            os.kill(pid, 9)
        except Exception:
            continue


def init_data(track_chunk, dropbox):
    """ """

    bpm_map = defaultdict(list)
    track_bpms = []
    transition_matches = defaultdict(dict)

    for track in track_chunk:
        bpm = track.bpm
        track_bpms.append(bpm)
        formatted_bpm = format_bpm(bpm)
        bpm_map[formatted_bpm].append(track)

        (same_key, higher_key, lower_key), _ = mdw.transition_match_finder.get_transition_matches(track, False)

        transition_matches[track.id][RelativeKey.SAME.value] = same_key
        transition_matches[track.id][RelativeKey.STEP_DOWN.value] = higher_key
        transition_matches[track.id][RelativeKey.STEP_UP.value] = lower_key

    child_pid = os.getpid()
    n = len(track_chunk)
    print('[%d]:  %d tracks processed' % (child_pid, n))

    dropbox.send((bpm_map, track_bpms, transition_matches, child_pid))


def generate_mel_scores(track_id, track_mel, matches, relative_key):
    smms_map = mdw.smms_map
    track_map = mdw.track_map
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

            match_row = {'on_deck_id': track_id, 'candidate_id': match_id,
                         'match_factors': {track_mel.feature_name: mel_score}, 'relative_key': relative_key}
            tm_rows.append(TransitionMatchRow(**match_row))

        except Exception as e:
            handle_error(e)
            continue

    return tm_rows


def compute_feature_values(tracks, relative_key, dropbox):
    smms_map = mdw.smms_map

    match_rows = []
    for track in tracks:
        track_id = track.id
        track_std_bpm = format_bpm(track.bpm)
        if track_id not in smms_map[track_std_bpm]:
            smms_map[track_std_bpm][track_id] = SegmentedMeanMelSpectrogram(track)

        track_mel = smms_map[format_bpm(track.bpm)][track_id]
        match_rows.extend(generate_mel_scores(track_id, track_mel,
                                              mdw.transition_matches[track_id][relative_key], relative_key))

    dropbox.send((match_rows, os.getpid()))


def get_frontier_tracks(bpm_chunk_delta):
    frontier_tracks = []
    if len(bpm_chunk_delta) == 0:
        return frontier_tracks

    for bpm in bpm_chunk_delta:
        std_bpm = format_bpm(bpm)

        if std_bpm not in mdw.smms_map:
            mdw.smms_map[std_bpm] = {}
            mdw.bpm_vals_in_smms_map.add(float(std_bpm))
            frontier_tracks.extend(mdw.bpm_to_tracks[std_bpm])

    return frontier_tracks


def update_smms_map(frontier_tracks, dropbox):
    smms_map_update = defaultdict(dict)
    for ft in frontier_tracks:
        smms_map_update[format_bpm(ft.bpm)][ft.id] = SegmentedMeanMelSpectrogram(ft)

    dropbox.send((smms_map_update, os.getpid()))


database = Database()
mdw = SMMSData()

fv_sesh = database.create_session()
fv_set = set([fv.track_id for fv in fv_sesh.query(FeatureValue).all()])
fv_sesh.close()

tm_set = set()

if __name__ == '__main__':
    # Initialize MDW structs / preprocess tracks
    m_chunks = np.array_split(mdw.all_tracks, NUM_CORES)
    m_tasks = []
    m_parcels = []
    for m_chunk in m_chunks:
        m_mailbox, m_dropbox = Pipe()
        m_parcels.append(m_mailbox)

        m_task = Process(target=init_data, args=(m_chunk, m_dropbox))
        m_task.daemon = True
        m_tasks.append(m_task)
        m_task.start()

    m_results = [m_parcel.recv() for m_parcel in m_parcels]
    m_task_pids = []
    for m_res in m_results:
        (partial_bpm_map, partial_track_bpms, partial_transition_matches, m_pid) = m_res

        m_task_pids.append(m_pid)
        mdw.track_bpms.extend(partial_track_bpms)
        for k, v in partial_bpm_map.items():
            mdw.bpm_to_tracks[k].extend(v)
        for k, v in partial_transition_matches.items():
            for rk, m_matches in v.items():
                mdw.transition_matches[k][rk] = m_matches

    mdw.track_bpms = sorted(list(set([tbpm for tbpm in mdw.track_bpms])))

    join_tasks(m_tasks)
    kill_processes(m_task_pids)

    # Build transition match table
    m_bounds = [
        # (SAME_UPPER_BOUND, SAME_LOWER_BOUND, RelativeKey.SAME.value),
        (UP_KEY_UPPER_BOUND, UP_KEY_LOWER_BOUND, RelativeKey.STEP_UP.value),
        (DOWN_KEY_UPPER_BOUND, DOWN_KEY_LOWER_BOUND, RelativeKey.STEP_DOWN.value)
    ]
    try:
        for (m_upper, m_lower, m_relative_key) in m_bounds:
            m_frontier_index = 0
            for i, m_track_bpm in enumerate(mdw.track_bpms):
                m_upper_bound = get_bpm_bound(float(m_track_bpm), m_lower)
                m_lower_bound = get_bpm_bound(float(m_track_bpm), m_upper)

                # Find new max BPM
                m_bpm_chunk_delta = []
                m_frontier = mdw.track_bpms[m_frontier_index:]
                for j, m_next_bpm in enumerate(m_frontier):
                    if m_next_bpm < m_lower_bound:
                        frontier_index = j + 1
                        continue
                    if m_next_bpm > m_upper_bound:
                        break
                    m_bpm_chunk_delta.append(m_next_bpm)

                print('Iteration: %d   Current bpm: %f   Lower bound: %f   Upper bound: %f' %
                      (i, m_track_bpm, m_lower_bound, m_upper_bound))

                # Prune then expand SMMS map
                m_smms_map_keys = list(mdw.smms_map.keys())
                m_del_count = 0
                for m_bpm in m_smms_map_keys:
                    if not (m_lower_bound <= float(m_bpm) <= m_upper_bound):
                        mdw.bpm_vals_in_smms_map.remove(float(m_bpm))
                        m_del_count += len(mdw.smms_map[m_bpm])
                        del mdw.smms_map[m_bpm]

                # Expand track frontier
                m_frontier_tracks = get_frontier_tracks(m_bpm_chunk_delta)

                # Update SMMS cache
                m_chunks = np.array_split(m_frontier_tracks, NUM_CORES)
                m_tasks = []
                m_parcels = []
                for m_chunk in m_chunks:
                    m_mailbox, m_dropbox = Pipe()
                    m_parcels.append(m_mailbox)

                    m_task = Process(target=update_smms_map, args=(m_chunk, m_dropbox))
                    m_task.daemon = True
                    m_tasks.append(m_task)
                    m_task.start()

                m_results = [m_parcel.recv() for m_parcel in m_parcels]
                m_task_pids = []

                new_sesh = database.create_session()
                try:
                    counter = 0
                    for m_result in m_results:
                        (m_smms_map_update, m_pid) = m_result
                        m_task_pids.append(m_pid)

                        for t_bpm, smms_dict in m_smms_map_update.items():
                            for t_id, t_smms in smms_dict.items():
                                mdw.smms_map[t_bpm][t_id] = t_smms

                                if t_id not in fv_set:
                                    if counter == SESSION_LIMIT:
                                        new_sesh.close()
                                        new_sesh = database.create_session()
                                        counter = 0

                                    fv_set.add(t_id)
                                    fv_row = {
                                        'track_id': t_id,
                                        'features': {
                                            Feature.SMMS.value: t_smms.preprocess(t_smms.feature_value)
                                        }
                                    }
                                    new_sesh.add(FeatureValue(**fv_row))
                                    new_sesh.commit()
                                    counter += 1

                finally:
                    new_sesh.close()

                join_tasks(m_tasks)
                kill_processes(m_task_pids)

                m_smms_size = sum([len(v) for v in mdw.smms_map.values()])
                print('----')
                print('SMMS size: %d' % m_smms_size)
                if m_smms_size > 0:
                    print('Min BPM in SMMS map: %f' % min(mdw.bpm_vals_in_smms_map))
                    print('Max BPM in SMMS map: %f' % max(mdw.bpm_vals_in_smms_map))
                print('Deleted %d SMMS map entries' % m_del_count)

                # Create TransitionMatch rows in parallel
                tracks_to_process = mdw.bpm_to_tracks[format_bpm(m_track_bpm)]
                m_chunks = np.array_split(tracks_to_process, NUM_CORES)
                m_tasks = []
                m_parcels = []
                for m_chunk in m_chunks:
                    m_mailbox, m_dropbox = Pipe()
                    m_parcels.append(m_mailbox)

                    m_task = Process(target=compute_feature_values, args=(m_chunk, m_relative_key, m_dropbox))
                    m_task.daemon = True
                    m_tasks.append(m_task)
                    m_task.start()

                m_results = [m_parcel.recv() for m_parcel in m_parcels]
                m_task_pids = []
                m_match_rows = []
                for m_result in m_results:
                    (partial_match_rows, m_pid) = m_result
                    m_match_rows.extend(partial_match_rows)
                    m_task_pids.append(m_pid)

                join_tasks(m_tasks)
                kill_processes(m_task_pids)

                print('---\n')

                session = database.create_session()
                try:
                    counter = 0
                    for tm_row in m_match_rows:
                        if (tm_row.on_deck_id, tm_row.candidate_id) in tm_set:
                            continue
                        try:
                            if counter == SESSION_LIMIT:
                                session.close()
                                session = database.create_session()
                                counter = 0

                            for oc_id in [tm_row.on_deck_id, tm_row.candidate_id]:
                                if oc_id not in fv_set:
                                    oc_bpm = format_bpm(
                                        [octr.bpm for octr in mdw.all_tracks if octr.id == oc_id][0])
                                    oc_smms = mdw.smms_map[oc_bpm][oc_id]
                                    fv_set.add(oc_id)
                                    fv_row = {
                                        'track_id': oc_id,
                                        'features': {
                                            Feature.SMMS.value: oc_smms.preprocess(oc_smms.feature_value)
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

                            tm_set.add((tm_row.on_deck_id, tm_row.candidate_id))
                            counter += 1
                        except Exception as ex:
                            handle_error(ex)
                            continue

                finally:
                    session.close()

            # Reset
            for k, v in mdw.transition_matches.items():
                if m_relative_key in v:
                    del v[m_relative_key]
            mdw.reset()

    finally:
        database.close_all_sessions()
