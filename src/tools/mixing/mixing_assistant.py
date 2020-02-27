from math import ceil, floor
from sys import exit

from src.db import database
from src.db.entities.track import Track
from src.definitions.harmonic_mixing import *
from src.definitions.mixing_assistant import *
from src.scripts.rename_songs import rename_songs
from src.tools.data_management.data_manager import DataManager
from src.tools.mixing.command import CommandParsingException
from src.tools.mixing.transition_match import TransitionMatch
from src.utils.errors import handle_error
from src.utils.harmonic_mixing import *
from src.utils.mixing_assistant import *


class MixingAssistant:
    """" CLI mixing assistant functions."""

    def __init__(self):
        """ Initializes data manager. """
        self.dm = DataManager()
        self.tracks = self.dm.load_tracks()
        self.camelot_map, self.collection_md = generate_camelot_map(self.tracks)
        TransitionMatch.collection_md = self.collection_md

    def execute(self, user_input):
        """
        Parses and validates user input and executes corresponding command.

        :param user_input: Raw user input.
        """

        # Validate command
        segments = user_input.split()
        cmd_alias = segments[0].lower()
        if cmd_alias not in ALL_ALIASES:
            raise CommandParsingException('%s is not a valid command.' % cmd_alias)

        # Validate arguments
        cmd_name = ALIAS_MAPPING.get(cmd_alias, cmd_alias)
        command = COMMANDS[cmd_name]

        # TODO: fix this hack
        args = [' '.join(segments[1:])] if cmd_name == MATCH else segments[1:]

        expected_args = command.get_arguments()
        num_args = len(args)
        num_expected_args = len(expected_args)
        if num_args != num_expected_args:
            formatted_args = '' if num_args == 0 else ' - got: %s' % ' '.join(args)
            raise CommandParsingException('%s expects %d arguments%s.' % (cmd_name, num_expected_args, formatted_args))

        # Execute command
        cmd_function = command.get_function()
        cmd_args = {expected_args[i].get_name(): args[i] for i in range(num_args)}
        return getattr(self, cmd_function)(**cmd_args)

    def print_malformed_tracks(self):
        """ Prints malformed track names to stdout to facilitate corrections. """
        self.dm.show_malformed_tracks()

    def reload_track_data(self):
        """ Reloads tracks from the audio directory and regenerates Camelot map and metadata. """

        self.dm = DataManager()
        self.tracks = self.dm.load_tracks()
        self.camelot_map, self.collection_md = generate_camelot_map(self.tracks)
        TransitionMatch.collection_md = self.collection_md
        print('Track data reloaded.')

    def rename_tracks(self, upsert):
        """
        Rename tracks in tmp directories.

        :param upsert: Indicates whether to attempt upserting existing DB entries using track metadata.
        """

        upsert_lower = upsert.lower()
        upsert_lower = True if upsert_lower == 'true' else False
        rename_songs(self.dm, upsert_lower)
        print('\nSongs renamed.')

    def shutdown(self):
        """ Exits the CLI. """
        print('Goodbye.')
        exit()

    def get_transition_matches(self, track_path):
        """
        Prints transition matches for the given track.

        :param track_path: Full qualified path to the track.
        """

        try:
            # Validate metadata exists
            session = database.create_session()
            db_row = session.query(Track).filter_by(file_path=track_path).first()
            if db_row is None:
                raise MixingException('%s not found in database.' % track_path)

            # Validate BPM and Camelot code exist and are well-formatted
            bpm = db_row.bpm
            camelot_code = db_row.camelot_code
            if bpm is None:
                raise MixingException('Did not find a BPM for %s.' % track_path)
            if camelot_code is None:
                raise MixingException('Did not find a Camelot code for %s.' % track_path)

            camelot_map_entry = self.camelot_map[camelot_code][bpm]
            cur_track_md = [md for md in camelot_map_entry if md.get(TrackDBCols.FILE_PATH) == track_path]
            if len(cur_track_md) == 0:
                raise MixingException('%s metadata not found in Camelot map.' % track_path)
            cur_track_md = cur_track_md[0]

            # Generate and rank matches
            harmonic_codes = self._get_all_harmonic_codes(cur_track_md)
            same_key, higher_key, lower_key = self._get_matches_for_code(harmonic_codes, cur_track_md)

            # Print matches
            self._print_transition_ranks('Higher key (step down)', higher_key)
            self._print_transition_ranks('Lower key (step up)', lower_key)
            self._print_transition_ranks('Same key', same_key, 1)
        except Exception as e:
            handle_error(e)

    def _get_all_harmonic_codes(self, cur_track_md):
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

    def _get_matches(self, bpm, camelot_code, upper_bound, lower_bound):
        """
        Calculate BPM ranges and find matching tracks.

        :param bpm: Track BPM
        :param camelot_code: Full Camelot code
        :param upper_bound: Max percentage difference between current BPM and higher BPMs
        :param lower_bound: Max percentage difference between current BPM and lower BPMs
        """

        upper_bpm = int(floor(get_bpm_bound(bpm, lower_bound)))
        lower_bpm = int(ceil(get_bpm_bound(bpm, upper_bound)))

        results = []
        code_map = self.camelot_map[camelot_code]
        for b in range(lower_bpm, upper_bpm + 1):
            results.extend(code_map[b])

        return results

    def _get_matches_for_code(self, harmonic_codes, cur_track_md):
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

            same_key.extend(TransitionMatch(md, cur_track_md, priority) for md in
                            self._get_matches(bpm, camelot_code, SAME_UPPER_BOUND, SAME_LOWER_BOUND))
            higher_key.extend(TransitionMatch(md, cur_track_md, priority) for md in
                              self._get_matches(bpm, hk_code, DOWN_KEY_UPPER_BOUND, DOWN_KEY_LOWER_BOUND))
            lower_key.extend(TransitionMatch(md, cur_track_md, priority) for md in
                             self._get_matches(bpm, lk_code, UP_KEY_UPPER_BOUND, UP_KEY_LOWER_BOUND))

        # Rank and format results
        same_key = sorted(same_key, reverse=True)
        higher_key = sorted(higher_key, reverse=True)
        lower_key = sorted(lower_key, reverse=True)

        return same_key, higher_key, lower_key

    def _print_transition_ranks(self, result_type, results, start_index=0):
        """
        Prints ranked transition results.

        :param result_type: The type of result (same key, higher key, or lower key).
        :param results: Ranked, formatted results.
        """

        dashed_line = ''.join(['-'] * 148)

        print('\n\n\n%s results:\n\n\n' % result_type)
        print(dashed_line)
        print('\t\t\t'.join(['Score', 'Track']))
        print(dashed_line)

        for result in results[start_index:]:
            print(result.format())


class MixingException(Exception):
    pass
