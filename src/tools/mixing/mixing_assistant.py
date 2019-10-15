import logging
from math import ceil, floor
from sys import exit

from src.definitions.harmonic_mixing import *
from src.definitions.mixing_assistant import *
from src.tools.data_management.data_manager import DataManager
from src.tools.mixing.transition_match import TransitionMatch
from src.utils.harmonic_mixing import *
from src.utils.mixing_assistant import *


# Suppress annoying eyed3 logs
logging.getLogger('eyed3').setLevel(logging.ERROR)


class MixingAssistant:
    """" CLI mixing assistant functions."""

    def __init__(self):
        """ Initializes data manager. """
        self.dm = DataManager()
        self.metadata = self.dm.load_collection_metadata()['Track Metadata']
        self.camelot_map = generate_camelot_map(self.metadata)

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

        # TODO: fix below hack
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

    def get_transition_matches(self, track_path):
        """
        Prints transition matches for given BPM and Camelot code.

        :param track_path
        """

        current_track_md = self.metadata.get(track_path)
        if current_track_md is None:
            raise Exception('%s not found in metadata.' % track_path)

        bpm = int(current_track_md['BPM'])
        camelot_code = current_track_md['Camelot Code']
        code_number = int(camelot_code[0:2])
        code_letter = camelot_code[-1].upper()

        # Harmonic transitions to find. Results are printed in an assigned priority, which is:
        # same key > major/minor jump > one key jump > adjacent jump > one octave jump > two key jump
        harmonic_codes = [
            # Same key
            (code_number, code_letter, 4),
            # One key jump
            ((code_number + 1) % 12, code_letter, 3),
            # Two key jump
            ((code_number + 2) % 12, code_letter, 0),
            # One octave jump
            ((code_number + 7) % 12, code_letter, 1),
            # Major/minor jump
            ((code_number + (3 if code_letter == 'A' else - 3)) % 12, flip_camelot_letter(code_letter), 3),
            # Adjacent key jumps
            ((code_number + (1 if code_letter == 'B' else - 1)) % 12, flip_camelot_letter(code_letter), 2),
            (code_number, flip_camelot_letter(code_letter), 2)
        ]

        # We also find matching tracks one key above and below the current key, such that if these tracks were sped up
        # or slowed down to the current track's BPM, they would be a valid haromic transition.
        # e.g. if current track is 128 BPM Am, then a 122 BPM D#m track is a valid transition - if it was sped up to
        # 128, the key would be pitched up to Em, which is a valid harmonc transition from Am.
        same_key_results = []
        higher_key_results = []
        lower_key_results = []
        for code_number, code_letter, priority in harmonic_codes:
            cc = format_camelot_number(code_number) + code_letter
            same_key, higher_key, lower_key = self._get_matches_for_code(bpm, cc, code_number, code_letter)
            same_key_results.extend([TransitionMatch(sk, current_track_md, priority) for sk in same_key])
            higher_key_results.extend([TransitionMatch(hk, current_track_md, priority) for hk in higher_key])
            lower_key_results.extend([TransitionMatch(lk, current_track_md, priority) for lk in lower_key])

        higher_key_results = [tm.format() for tm in sorted(higher_key_results, reverse=True)]
        lower_key_results = [tm.format() for tm in sorted(lower_key_results, reverse=True)]
        same_key_results = [tm.format() for tm in sorted(same_key_results, reverse=True)]

        print('Higher key (step down) results:\n')
        for result in higher_key_results:
            print(result)

        print('\n\nLower key (step up) results:\n')
        for result in lower_key_results:
            print(result)

        print('\n\nSame key results:\n')
        for result in same_key_results:
            print(result)

    def print_malformed_tracks(self):
        """ Prints malformed track names to stdout to facilitate corrections. """
        self.dm.show_malformed_tracks()

    def reload_track_data(self):
        """ Reloads tracks from the audio directory and regenerates Camelot map. """
        self.dm = DataManager()
        self.camelot_map = generate_camelot_map(self.dm.audio_files)
        print('Track data reloaded.')

    def rename_tracks(self):
        """ Rename tracks in tmp directory. """
        self.dm.rename_songs()
        print('\nSongs renamed.')

    def shutdown(self):
        """ Exits the CLI. """
        print('Goodbye.')
        exit()

    def _get_matches_for_code(self, bpm, camelot_code, code_number, code_letter):
        """
        Find matches for the given BPM and camelot code.

        :param bpm - track BPM
        :param camelot_code - full Camelot code
        :param code_number - numerical portion of the Camelot code
        :param code_letter - alphabetic portion of the Camelot code
        """

        hk_code = format_camelot_number((code_number + 7) % 12) + code_letter
        lk_code = format_camelot_number((code_number - 7) % 12) + code_letter

        same_key_results = self._get_matches(bpm, camelot_code, SAME_UPPER_BOUND, SAME_LOWER_BOUND)
        higher_key_results = self._get_matches(bpm, hk_code, DOWN_KEY_UPPER_BOUND, DOWN_KEY_LOWER_BOUND)
        lower_key_results = self._get_matches(bpm, lk_code, UP_KEY_UPPER_BOUND, UP_KEY_LOWER_BOUND)

        return same_key_results, higher_key_results, lower_key_results

    def _get_matches(self, bpm, camelot_code, upper_bound, lower_bound):
        """
        Calculate BPM ranges and find matching tracks.

        :param bpm - track BPM
        :param camelot_code - full Camelot code
        :param upper_bound - max percentage difference between current BPM and higher BPMs
        :param lower_bound - max percentage difference between current BPM and lower BPMs
        """

        upper_bpm = int(floor(get_bpm_bound(bpm, lower_bound)))
        lower_bpm = int(ceil(get_bpm_bound(bpm, upper_bound)))

        results = []
        code_map = self.camelot_map[camelot_code]
        for b in range(lower_bpm, upper_bpm + 1):
            results.extend(code_map[str(b)])

        return results


if __name__ == '__main__':
    run_assistant()
