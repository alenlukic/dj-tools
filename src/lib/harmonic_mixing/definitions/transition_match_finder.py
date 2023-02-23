from src.db import database
from src.db.entities.track import Track
from src.definitions.harmonic_mixing import *
from src.definitions.assistant import *
from src.lib.data_management.service import load_tracks
from src.lib.harmonic_mixing.definitions.transition_match import TransitionMatch
from src.lib.error_management.service import handle
from src.utils.harmonic_mixing import *


class TransitionMatchFinder:
    """ Encapsulates functionality for finding transition matches. """
    def __init__(self, session=None):
        self.tracks = load_tracks()
        self.camelot_map, self.collection_metadata = generate_camelot_map(self.tracks)
        self.session = session if session is not None else database.create_session()
        self.max_results = get_config_value(['HARMONIC_MIXING', 'MAX_RESULTS'])
        self.cutoff_threshold_score = get_config_value(['HARMONIC_MIXING', 'SCORE_THRESHOLD'])
        self.result_threshold = get_config_value(['HARMONIC_MIXING', 'RESULT_THRESHOLD'])

        TransitionMatch.db_session = self.session
        TransitionMatch.collection_metadata = self.collection_metadata

    def reload_track_data(self):
        self.tracks = load_tracks()
        self.camelot_map, self.collection_metadata = generate_camelot_map(self.tracks)
        TransitionMatch.collection_metadata = self.collection_metadata

    def get_transition_matches(self, track, sort_results=True):
        try:
            db_row = track if isinstance(track, Track) else self.session.query(Track).filter_by(title=track).first()
            title_mismatch_message = ''

            if db_row is None:
                db_row = self.session.query(Track).filter(Track.file_name.like('%{}%'.format(track))).first()

                if db_row is not None:
                    file_name = db_row.file_name
                    title_mismatch_message = '\n\nWarning: found %s in file name %s (but not title)' % (track, file_name)
                else:
                    raise Exception('%s not found in database.' % track)

            # Validate BPM and Camelot code exist and are well-formatted
            title = db_row.title
            bpm = float(db_row.bpm)
            camelot_code = db_row.camelot_code
            if bpm is None:
                raise Exception('Did not find a BPM for %s.' % title)
            if camelot_code is None:
                raise Exception('Did not find a Camelot code for %s.' % title)

            camelot_map_entry = self.camelot_map[camelot_code][bpm]
            cur_track_md = [md for md in camelot_map_entry if md.get(TrackDBCols.TITLE) == title]
            if len(cur_track_md) == 0:
                raise Exception('%s metadata not found in Camelot map.' % title)

            cur_track_md = cur_track_md[0]

            # Generate and rank matches
            harmonic_codes = TransitionMatchFinder._get_all_harmonic_codes(cur_track_md)
            same_key, higher_key, lower_key = self._get_matches_for_code(harmonic_codes, cur_track_md, sort_results)

            return (same_key, higher_key, lower_key), title_mismatch_message

        except Exception as e:
            handle(e)

    def print_transition_matches(self, track):
        (same_key, higher_key, lower_key), title_mismatch_message = self.get_transition_matches(track)

        self._print_transition_ranks('Higher key (step down)', higher_key)
        self._print_transition_ranks('Lower key (step up)', lower_key)
        self._print_transition_ranks('Same key', same_key, 1)
        print(title_mismatch_message)

    @staticmethod
    def _get_all_harmonic_codes(cur_track_md):
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

    def _get_matches(self, bpm, camelot_code, upper_bound, lower_bound):
        upper_bpm = get_bpm_bound(bpm, lower_bound)
        lower_bpm = get_bpm_bound(bpm, upper_bound)

        results = []
        code_map = self.camelot_map[camelot_code]
        matching_bpms = sorted([b for b in code_map.keys() if lower_bpm <= b <= upper_bpm])
        for b in matching_bpms:
            results.extend(code_map[b])

        return results

    def _get_matches_for_code(self, harmonic_codes, cur_track_md, sort_results):
        bpm = cur_track_md[TrackDBCols.BPM]
        same_key = []
        higher_key = []
        lower_key = []

        for code_number, code_letter, priority in harmonic_codes:
            camelot_code = format_camelot_number(code_number) + code_letter
            hk_code = format_camelot_number((code_number + 7) % 12) + code_letter
            lk_code = format_camelot_number((code_number - 7) % 12) + code_letter

            for md in self._get_matches(bpm, camelot_code, SAME_UPPER_BOUND, SAME_LOWER_BOUND):
                match = TransitionMatch(md, cur_track_md, priority)
                same_key.append(match)

            for md in self._get_matches(bpm, hk_code, DOWN_KEY_UPPER_BOUND, DOWN_KEY_LOWER_BOUND):
                match = TransitionMatch(md, cur_track_md, priority)
                higher_key.append(match)

            for md in self._get_matches(bpm, lk_code, UP_KEY_UPPER_BOUND, UP_KEY_LOWER_BOUND):
                match = TransitionMatch(md, cur_track_md, priority)
                lower_key.append(match)

        if sort_results:
            same_key = sorted(same_key, reverse=True)
            higher_key = sorted(higher_key, reverse=True)
            lower_key = sorted(lower_key, reverse=True)

        return same_key, higher_key, lower_key

    def _print_transition_ranks(self, result_type, results, start_index=0):
        print('\n\n\n%s results:\n\n\n' % result_type)
        print(DASHED_LINE)
        print(TransitionMatch.result_column_header)
        print(DASHED_LINE)

        num_results = len(results)
        if num_results == 0:
            return

        for i, result in enumerate(results[start_index:]):
            if i == self.max_results:
                break

            if num_results >= self.result_threshold and result.get_score() < self.cutoff_threshold_score:
                break

            print(result.format())
            if (i + 1) % 5 == 0:
                print()
