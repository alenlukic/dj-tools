import logging
from math import ceil, floor

from src.definitions.common import *
from src.definitions.harmonic_mixing import *
from src.utils.file_management import *
from src.utils.harmonic_mixing import *


# Suppress annoying eyed3 logs
logging.getLogger('eyed3').setLevel(logging.ERROR)


class DJTools:
    """ Encapsulates DJ utility functions (track naming/processing, transition match finding, etc.). """

    def __init__(self, audio_dir=PROCESSED_MUSIC_DIR):
        """
        Initializes class with music directory info.

        :param audio_dir - directory containing processed (e.g. renamed) tracks.
        """

        self.audio_dir = audio_dir
        self.audio_files = get_audio_files(self.audio_dir)
        self.camelot_map = generate_camelot_map(self.audio_files)

    #############################
    # File processing functions #
    #############################

    def reload_track_data(self):
        """ Reloads track data. """
        self.audio_files = get_audio_files(self.audio_dir)
        self.camelot_map = generate_camelot_map(self.audio_files)

    def get_transition_matches(self, bpm, camelot_code):
        """
        Given bpm and camelot code, find all tracks which can be transitioned to from current track.

        :param bpm - BPM of current track
        :param camelot_code - Camelot code of current track
        """

        code_number = int(camelot_code[0:2])
        code_letter = camelot_code[-1].upper()

        # Harmonic transitions to find. Results are printed in an assigned priority, which is:
        # same key > major/minor jump > one key jump > adjacent jump > one octave jump > two key jump
        harmonic_codes = [
            # Same key
            (code_number, code_letter, 0),
            # One key jump
            ((code_number + 1) % 12, code_letter, 2),
            # Two key jump
            ((code_number + 2) % 12, code_letter, 5),
            # One octave jump
            ((code_number + 7) % 12, code_letter, 4),
            # Major/minor jump
            ((code_number + (3 if code_letter == 'A' else -3)) % 12, flip_camelot_letter(code_letter), 1),
            # Adjacent key jumps
            ((code_number + (1 if code_letter == 'B' else - 1)) % 12, flip_camelot_letter(code_letter), 3),
            (code_number, flip_camelot_letter(code_letter), 3)
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
            same_key_results.extend([(priority, sk) for sk in same_key])
            higher_key_results.extend([(priority, hk) for hk in higher_key])
            lower_key_results.extend([(priority, lk) for lk in lower_key])

        higher_key_results = [x[1] for x in sorted(list(set(higher_key_results)))]
        lower_key_results = [x[1] for x in sorted(list(set(lower_key_results)))]
        same_key_results = [x[1] for x in sorted(list(set(same_key_results)))]

        print('Higher key (step down) results:\n')
        for result in higher_key_results:
            print(result)

        print('\n\nLower key (step up) results:\n')
        for result in lower_key_results:
            print(result)

        print('\n\nSame key results:\n')
        for result in same_key_results:
            print(result)

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
