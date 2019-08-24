import logging
from math import ceil, floor
from os import chmod, remove
from os.path import basename
from shutil import copyfile
import stat

from src.definitions.harmonic_mixing import *
from src.utils.file_processing import *
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

    def rename_songs(self, input_dir=TMP_MUSIC_DIR, target_dir=None):
        """
        Standardizes song names and copy them to library.

        :param input_dir - directory containing audio files to rename.
        :param target_dir - directory where updated audio files should be saved
        """

        target_dir = target_dir or self.audio_dir
        input_files = get_audio_files(input_dir)
        for f in input_files:
            old_name = join(input_dir, f)
            old_base_name = basename(old_name)
            id3_data = extract_id3_data(old_name)

            if id3_data is None or not REQUIRED_ID3_TAGS.issubset(set(id3_data.keys())):
                # All non-mp3 audio files (and some mp3 files) won't have requisite ID3 metadata for automatic renaming
                # - user will need to enter new name manually.
                print('Can\'t automatically rename this track: %s' % old_base_name)
                print('Enter the new name here:')
                new_name = join(target_dir, input())
                copyfile(old_name, new_name)
            else:
                # Extract ID3 metadata
                title = id3_data[ID3_MAP[ID3Tag.TITLE]]
                artist = id3_data[ID3_MAP[ID3Tag.ARTIST]]
                key = id3_data[ID3_MAP[ID3Tag.KEY]]
                bpm = id3_data[ID3_MAP[ID3Tag.BPM]]

                # Generate new formatted file name
                formatted_title, featured = format_title(title)
                formatted_artists = format_artists(artist.split(', '), [] if featured is None else [featured])
                formatted_key = CANONICAL_KEY_MAP[key.lower()]
                camelot_prefix = ' - '.join(
                    ['[' + CAMELOT_MAP[formatted_key], formatted_key.capitalize(), str(bpm) + ']'])
                artist_midfix = formatted_artists + (' ft. ' + featured if featured is not None else '')
                formatted_name = camelot_prefix + ' ' + artist_midfix + ' - ' + formatted_title
                new_name = ''.join([join(target_dir, formatted_name).strip(), '.', old_name.split('.')[-1].strip()])

                # Copy formatted track to user audio directory
                copyfile(old_name, new_name)
                new_track = load(new_name).tag
                new_track.title = formatted_name
                new_track.save()

            new_base_name = basename(new_name)
            try:
                print('\nRenaming:\t%s\nto:\t\t%s' % (old_base_name, new_base_name))
            except Exception as e:
                print('Could not rename %s to %s (exception: %s)' % (old_base_name, new_base_name, str(e)))

    def set_audio_file_permissions(self):
        """ Makes all audio files in user's music directory readable and writable. """
        permissions = stat.S_IREAD | stat.S_IROTH | stat.S_IWRITE | stat.S_IWOTH
        for file in self.audio_files:
            chmod(join(self.audio_dir, file), permissions)

    @staticmethod
    def separate_low_and_high_quality(source_dir, lq_dir, hq_dir):
        """
        Takes all files in source_dir and moves the low quality ones to low_quality_dir and the high quality ones to
        high_quality_dir. This is useful for cleaning up directories containing audio files or varying quality.
        N.B.: this will delete all files in the original directory.

        :param source_dir - directory containing all audio files
        :param lq_dir - directory to save low quality files to
        :param hq_dir - directory to save high quality files to
        """

        for f in get_audio_files(source_dir):
            track_path = join(source_dir, f)
            track_name = basename(f)

            # Determine destination based on file quality estimate
            destination = hq_dir if is_high_quality(track_path) else lq_dir
            new_name = join(destination, track_name)
            print('Moving:\t%s\nto:\t\t%s' % (track_name, destination))

            # Move file to destination and delete from source
            copyfile(f, new_name)
            remove(f)

    #############################
    # Harmonic mixing functions #
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
        code_letter = camelot_code[-1]

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
