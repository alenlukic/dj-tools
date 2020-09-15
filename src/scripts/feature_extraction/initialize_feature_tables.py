from multiprocessing import Process, Pipe
import numpy as np
import os

from src.db.database import Database
from src.db.entities.feature_value import FeatureValue
from src.db.entities.transition_match import TransitionMatch as TransitionMatchRow
from src.definitions.common import NUM_CORES
from src.definitions.feature_extraction import *
from src.definitions.harmonic_mixing import *
from src.lib.assistant.assistant import Assistant as ExternalAssistant
from src.lib.assistant.transition_match import TransitionMatch
from src.lib.feature_extraction.track_feature import SegmentedMeanMelSpectrogram
from src.utils.errors import handle_error
from src.utils.harmonic_mixing import *


SESSION_LIMIT = 10


def join_tasks(tasks):
    for task in tasks:
        task.join()


def kill_processes(pids):
    for pid in pids:
        try:
            os.kill(pid, 9)
        except Exception:
            continue


def get_transition_matches(db_row, camelot_map, sort=True):
    try:
        title = db_row.title
        bpm = float(db_row.bpm)
        camelot_code = db_row.camelot_code

        if bpm is None:
            raise Exception('Did not find a BPM for %s.' % title)
        if camelot_code is None:
            raise Exception('Did not find a Camelot code for %s.' % title)

        camelot_map_entry = camelot_map[camelot_code][bpm]
        cur_track_md = [md for md in camelot_map_entry if md.get(TrackDBCols.TITLE) == title]
        if len(cur_track_md) == 0:
            raise Exception('%s metadata not found in Camelot map.' % title)

        cur_track_md = cur_track_md[0]

        # Generate and rank matches
        harmonic_codes = _get_all_harmonic_codes(cur_track_md)
        same_key, higher_key, lower_key = _get_matches_for_code(harmonic_codes, cur_track_md, sort, camelot_map)

        return same_key, higher_key, lower_key

    except Exception as e:
        handle_error(e)


def _get_all_harmonic_codes(cur_track_md):
    """
    Get all the Camelot codes which are harmonic transitions for the given track.

    :param cur_track_md: Current track metadata.
    """

    camelot_code = cur_track_md[TrackDBCols.CAMELOT_CODE]
    code_number = int(camelot_code[0:2])
    code_letter = camelot_code[-1].upper()

    return [
        # Same key
        (code_number, code_letter, CamelotPriority.SAME_KEY.value),
        # One key jump
        ((code_number + 1) % 12, code_letter, CamelotPriority.ONE_KEY_JUMP.value),
        # Two key jump
        ((code_number + 2) % 12, code_letter, CamelotPriority.TWO_OCTAVE_JUMP.value),
        # One octave jump
        ((code_number + 7) % 12, code_letter, CamelotPriority.ONE_OCTAVE_JUMP.value),
        # Major/minor jump
        ((code_number + (3 if code_letter == 'A' else - 3)) % 12, flip_camelot_letter(code_letter),
         CamelotPriority.MAJOR_MINOR_JUMP.value),
        # Adjacent key jumps
        ((code_number + (1 if code_letter == 'B' else - 1)) % 12, flip_camelot_letter(code_letter),
         CamelotPriority.ADJACENT_JUMP.value),
        (code_number, flip_camelot_letter(code_letter), CamelotPriority.ADJACENT_JUMP.value)
    ]


def _get_matches(bpm, camelot_code, upper_bound, lower_bound, sort, camelot_map):
    upper_bpm = get_bpm_bound(bpm, lower_bound)
    lower_bpm = get_bpm_bound(bpm, upper_bound)

    results = []
    code_map = camelot_map[camelot_code]
    matching_bpms = [b for b in code_map.keys() if lower_bpm <= b <= upper_bpm]
    if sort:
        matching_bpms = sorted(matching_bpms)
    for b in matching_bpms:
        results.extend(code_map[b])

    return results


def _get_matches_for_code(harmonic_codes, cur_track_md, sort, camelot_map):
    """
    Find matches for the given track.

    :param harmonic_codes: List of harmonic Camelot codes and their respective transition priorities.
    :param cur_track_md: Current track metadata.
    """

    bpm = cur_track_md[TrackDBCols.BPM]
    same_key = []
    higher_key = []
    lower_key = []

    # Find all the matches
    for code_number, code_letter, priority in harmonic_codes:
        camelot_code = format_camelot_number(code_number) + code_letter
        hk_code = format_camelot_number((code_number + 7) % 12) + code_letter
        lk_code = format_camelot_number((code_number - 7) % 12) + code_letter

        for md in _get_matches(bpm, camelot_code, SAME_UPPER_BOUND, SAME_LOWER_BOUND, sort, camelot_map):
            match = TransitionMatch(md, cur_track_md, priority)
            same_key.append(match)
        for md in _get_matches(bpm, hk_code, UP_KEY_UPPER_BOUND, UP_KEY_LOWER_BOUND, sort, camelot_map):
            match = TransitionMatch(md, cur_track_md, priority)
            higher_key.append(match)

        for md in _get_matches(bpm, lk_code, DOWN_KEY_UPPER_BOUND, DOWN_KEY_LOWER_BOUND, sort, camelot_map):
            match = TransitionMatch(md, cur_track_md, priority)
            lower_key.append(match)

    # Rank and format results
    if sort:
        same_key = sorted(same_key, reverse=True)
        higher_key = sorted(higher_key, reverse=True)
        lower_key = sorted(lower_key, reverse=True)

    return same_key, higher_key, lower_key


# Helper function for parallelization
def init_data(track_chunk, camelot_map, dropbox):
    bpm_map = defaultdict(list)
    track_bpms = []
    transition_matches = defaultdict(dict)

    for track in track_chunk:
        bpm = track.bpm
        s_bpm = MatchDataWrapper.std_bpm(bpm)
        bpm_map[s_bpm].append(track)
        track_bpms.append(bpm)

        same_key, higher_key, lower_key = get_transition_matches(track, camelot_map, False)

        transition_matches[track.id][RelativeKey.SAME.value] = same_key
        transition_matches[track.id][RelativeKey.STEP_DOWN.value] = higher_key
        transition_matches[track.id][RelativeKey.STEP_UP.value] = lower_key

    child_pid = os.getpid()
    n = len(track_chunk)
    print('[%d]:  %d tracks processed' % (child_pid, n))

    dropbox.send((bpm_map, track_bpms, transition_matches, child_pid))


class Assistant(ExternalAssistant):
    pass


class MatchDataWrapper:
    """ Utility class. """

    def __init__(self, tracks):
        # Track collection class members
        self.all_tracks = tracks
        self.num_tracks = len(self.all_tracks)

        # Track / transition data
        self.track_map = {}
        for track in self.all_tracks:
            self.track_map[track.file_path] = track

        self.track_bpms = []
        self.bpm_map = defaultdict(list)
        self.transition_matches = defaultdict(lambda: {
            RelativeKey.SAME.value: [],
            RelativeKey.STEP_UP.value: [],
            RelativeKey.STEP_DOWN.value: []
        })

        # SMMS structures
        self.smms_map = defaultdict(dict)
        self.smms_bpms = set()

    def reset(self):
        self.smms_map = defaultdict(dict)
        self.smms_bpms = set()

    @staticmethod
    def std_bpm(bpm):
        return str(float(bpm))


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

            match_mel = smms_map[MatchDataWrapper.std_bpm(match_track.bpm)][match_id]
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
        track_std_bpm = MatchDataWrapper.std_bpm(track.bpm)
        if track_id not in smms_map[track_std_bpm]:
            smms_map[track_std_bpm][track_id] = SegmentedMeanMelSpectrogram(track)

        track_mel = smms_map[MatchDataWrapper.std_bpm(track.bpm)][track_id]
        match_rows.extend(generate_mel_scores(track_id, track_mel,
                                              mdw.transition_matches[track_id][relative_key], relative_key))

    dropbox.send((match_rows, os.getpid()))


def get_frontier_tracks(bpm_chunk_delta):
    frontier_tracks = []
    if len(bpm_chunk_delta) == 0:
        return frontier_tracks

    for bpm in bpm_chunk_delta:
        std_bpm = MatchDataWrapper.std_bpm(bpm)

        if std_bpm not in mdw.smms_map:
            mdw.smms_map[std_bpm] = {}
            mdw.smms_bpms.add(float(std_bpm))
            frontier_tracks.extend(mdw.bpm_map[std_bpm])

    return frontier_tracks


def update_smms_map(frontier_tracks, dropbox):
    smms_map_update = defaultdict(dict)
    for ft in frontier_tracks:
        smms_map_update[MatchDataWrapper.std_bpm(ft.bpm)][ft.id] = SegmentedMeanMelSpectrogram(ft)

    dropbox.send((smms_map_update, os.getpid()))


database = Database()
assistant = Assistant()
cm = assistant.camelot_map
mdw = MatchDataWrapper(assistant.tracks)

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

        m_task = Process(target=init_data, args=(m_chunk, cm, m_dropbox))
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
            mdw.bpm_map[k].extend(v)
        for k, v in partial_transition_matches.items():
            for rk, m_matches in v.items():
                mdw.transition_matches[k][rk] = m_matches

    mdw.track_bpms = sorted(list(set([tbpm for tbpm in mdw.track_bpms])))

    join_tasks(m_tasks)
    kill_processes(m_task_pids)

    # Build transition match table
    m_bounds = [
        (SAME_UPPER_BOUND, SAME_LOWER_BOUND, RelativeKey.SAME.value),
        (UP_KEY_UPPER_BOUND, UP_KEY_LOWER_BOUND, RelativeKey.STEP_DOWN.value),
        (DOWN_KEY_UPPER_BOUND, DOWN_KEY_LOWER_BOUND, RelativeKey.STEP_UP.value)
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
                        mdw.smms_bpms.remove(float(m_bpm))
                        del mdw.smms_map[m_bpm]
                        m_del_count += 1

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
                    print('Min BPM in SMMS map: %f' % min(mdw.smms_bpms))
                    print('Max BPM in SMMS map: %f' % max(mdw.smms_bpms))
                print('Deleted %d SMMS map entries' % m_del_count)

                # Create TransitionMatch rows in parallel
                tracks_to_process = mdw.bpm_map[MatchDataWrapper.std_bpm(m_track_bpm)]
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
                                    oc_bpm = MatchDataWrapper.std_bpm(
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

                            session.add(tm_row)
                            session.commit()
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
