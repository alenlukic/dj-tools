from collections import defaultdict
from enum import Enum
import json
import logging
from math import ceil, floor
from os import chmod, listdir, remove
from os.path import basename, isfile, join
from shutil import copyfile
import stat

from eyed3 import id3 as metadata, load


CONFIG = json.load(open('config.json', 'r'))
PROCESSED_MUSIC_DIR = CONFIG['PROCESSED_MUSIC_DIR']
TMP_MUSIC_DIR = CONFIG['TMP_MUSIC_DIR']

AUDIO_TYPES = {'mp3', 'wav', 'flac', 'ogg', 'aif', 'aiff', 'm3u'}
LOSSLESS = {'wav', 'flac', 'aif', 'aiff'}

SAME_UPPER_BOUND = 0.0275
SAME_LOWER_BOUND = -0.025

UP_KEY_LOWER_BOUND = 0.03
UP_KEY_UPPER_BOUND = 0.09

DOWN_KEY_LOWER_BOUND = -0.08
DOWN_KEY_UPPER_BOUND = -0.03

ALL_TAGS = {'TIT2', 'TPE1', 'TPE4', 'TBPM', 'TKEY'}
REQUIRED_TAGS = {'TIT2', 'TPE1', 'TBPM', 'TKEY'}
BEATPORT_TAG = 'TENC'


class ID3Tag(Enum):
    TITLE = 1
    ARTIST = 2
    BPM = 3
    KEY = 4


ID3_MAP = {
    ID3Tag.TITLE: 'TIT2',
    ID3Tag.ARTIST: 'TPE1',
    ID3Tag.BPM: 'TBPM',
    ID3Tag.KEY: 'TKEY'
}

CANONICAL_KEY_MAP = {
    k.lower(): v.lower() for k, v in {
        # A keys
        'A': 'A',
        'Amaj': 'A',
        'Am': 'Am',
        'Amin': 'Am',
        'Ab': 'Ab',
        'Abmaj': 'Ab',
        'A#': 'Bb',
        'A#maj': 'Bb',
        'Abm': 'Abm',
        'Abmin': 'Abm',
        'A#m': 'Bbm',
        'A#min': 'Bbm',
        # B keys
        'B': 'B',
        'Bmaj': 'B',
        'Bm': 'Bm',
        'Bmin': 'Bm',
        'Bb': 'Bb',
        'Bbmaj': 'Bb',
        'Bbm': 'Bbm',
        'Bbmin': 'Bbm',
        # C keys
        'C': 'C',
        'Cmaj': 'C',
        'Cm': 'Cm',
        'Cmin': 'Cm',
        'C#': 'Db',
        'C#maj': 'Db',
        'C#m': 'C#m',
        'C#min': 'C#m',
        # D keys
        'D': 'D',
        'Dmaj': 'D',
        'Dm': 'Dm',
        'Dmin': 'Dm',
        'Db': 'Db',
        'Dbmaj': 'Db',
        'D#': 'Eb',
        'D#maj': 'Eb',
        'Dbm': 'C#m',
        'Dbmin': 'C#m',
        'D#m': 'Ebm',
        'D#min': 'Ebm',
        # E keys
        'E': 'E',
        'Emaj': 'E',
        'Em': 'Em',
        'Emin': 'Em',
        'Eb': 'Eb',
        'Ebmaj': 'Eb',
        'Ebm': 'Ebm',
        'Ebmin': 'Ebm',
        # F keys
        'F': 'F',
        'Fmaj': 'F',
        'Fm': 'Fm',
        'Fmin': 'Fm',
        'F#': 'F#',
        'F#maj': 'F#',
        'F#min': 'F#m',
        # G keys
        'G': 'G',
        'Gmaj': 'G',
        'Gm': 'Gm',
        'Gmin': 'Gm',
        'Gb': 'F#',
        'Gbmaj': 'F#',
        'G#': 'Ab',
        'G#maj': 'Ab',
        'Gbm': 'F#m',
        'Gbmin': 'F#m',
        'G#m': 'Abm',
        'G#min': 'Abm'
    }.items()
}

CAMELOT_MAP = {
    'abm': '01A',
    'b': '01B',
    'ebm': '02A',
    'f#': '02B',
    'bbm': '03A',
    'db': '03B',
    'fm': '04A',
    'ab': '04B',
    'cm': '05A',
    'eb': '05B',
    'gm': '06A',
    'bb': '06B',
    'dm': '07A',
    'f': '07B',
    'am': '08A',
    'c': '08B',
    'em': '09A',
    'g': '09B',
    'bm': '10A',
    'd': '10B',
    'f#m': '11A',
    'a': '11B',
    'c#m': '12A',
    'e': '12B'
}


# Suppress annoying eyed3 logs
logging.getLogger('eyed3').setLevel(logging.ERROR)


def extract_id3_data(track_path):
    """
    Extracts mp3 metadata needed to automatically rename songs using the eyed3 lib.

    :param track_path - full qualified path to audio file.
    """

    md = load(track_path)
    if md is None:
        return None

    text_frame = metadata.frames.TextFrame
    track_frames = md.tag.frameiter()
    id3 = {frame.id.decode('utf-8'): frame.text for frame in filter(lambda t: type(t) == text_frame, track_frames)}
    keys = list(filter(lambda k: k in ALL_TAGS, id3.keys()))

    return defaultdict(str, {k: id3[k] for k in keys})


def flip_camelot_letter(camelot_letter):
    """
    Flip Camelot letter, i.e. A -> B and vice-versa.

    :param camelot_letter - the alphabetic portion of the Camelot code to format.
    """
    return 'A' if camelot_letter == 'B' else 'B'


def format_artists(artists, featured):
    """
    Formats artist string.

    :param artists - list of artist names.
    :param featured - a "featured" artist, if any.
    """

    filtered_artists = list(filter(lambda artist: artist not in featured, artists))
    # If any artist names contain "&" then we want to use "and" to separate artist names in the title, for clarity.
    separator = ' and ' if any('&' in artist for artist in filtered_artists) else ' & '

    return separator.join(filtered_artists)


def format_camelot_number(camelot_number):
    """
    Convert 0 to 12, and add leading 0 if needed, to the Camelot code number.

    :param camelot_number - the numerical portion of the Camelot code to format.
    """
    camelot_number = 12 if camelot_number == 0 else camelot_number
    return str(camelot_number) if camelot_number >= 10 else '0' + str(camelot_number)


def format_title(title):
    """
    Formats track title.

    :param title - raw, unformatted track title.
    """

    featured = None
    segments = title.split(' ')
    filtered_segments = []

    i = 0
    n = len(segments)
    open_paren_found = False
    while i < n:
        segment = segments[i]

        if '(' in segment:
            open_paren_found = True

        # Replace all instances of 'feat.' with 'ft.' inside the parenthetical phrase indicating mix type.
        # e.g. "(Hydroid feat. Santiago Nino Mix)" becomes "(Hydroid ft. Santiago Nino Mix)"
        if segment.lower() == 'feat.':
            if open_paren_found:
                filtered_segments.append('ft.')
                i += 1
            else:
                # If we haven't seen an open parentheses yet, then the featured artist's name is composed of all
                # words occuring before the parentheses. This heuristic works for MP3 files purchased on Beatport.
                featured = []
                for j in range(i + 1, n):
                    next_part = segments[j]
                    if '(' in next_part:
                        break
                    featured.append(next_part)
                featured = ' '.join(featured)
                i = j
        else:
            filtered_segments.append(segment.strip())
            i += 1

    # Get rid of "(Original Mix)" and "(Extended Mix)" as these are redundant phrases that unnecessarily lengthen
    # the file name.
    formatted_title = ' '.join(filtered_segments).replace('(Original Mix)', '').replace('(Extended Mix)', '')

    return formatted_title, featured


def generate_camelot_map(track_paths):
    """
    Generate double-nested map of camelot code -> BPM -> set of tracks.

    :param track_paths - full qualified paths of all audio files in user's audio directory.
    """

    cm = defaultdict(lambda: defaultdict(list))
    for track in track_paths:
        try:
            triad = track[track.find('['): track.find(']') + 1].replace('[', '').replace(']', '')
            camelot_code, _, bpm = tuple([x.strip() for x in triad.split('-')])
            cm[camelot_code][bpm].append(track)
        except Exception as e:
            print('%s (offending track: %s)' % (e, track))
            continue

    return cm


def get_audio_files(input_dir):
    """
    Gets all the audio files in the given directory.

    :param input_dir - directory to inspect for audio files.
    """
    files = list(filter(lambda f: isfile(join(input_dir, f)), listdir(input_dir)))
    return list(filter(lambda f: f.split('.')[-1].lower() in AUDIO_TYPES, files))


def get_bpm_bound(bpm, bound):
    """
    Get BPM bound.

    :param bpm - track BPM.
    :param bound - percentage difference between current BPM and higher/lower BPMs.
    """
    return bpm / (1 + bound)


def is_high_quality(track_path):
    """
    Determine if a track is high quality. Note: this may not work on true 320 kbps MP3 files that are obtained from
    somewhere other than Beatport (e.g. promos, free downloads).

    :param track_path - full qualified path to audio file
    """

    # Lossless files are high quality
    extension = track_path.split('.')[-1]
    if extension in LOSSLESS:
        return True

    # Beatport mp3 files are high quality too
    md = load(track_path)
    return False if md is None else any(frame.id == BEATPORT_TAG for frame in md.tag.frameiter())


class DJTools:
    """ Encapsulates DJ utility functions (track naming/processing, transition match finding, etc.). """

    def __init__(self, audio_dir=PROCESSED_MUSIC_DIR):
        """
        Initializes class with music directory info.

        :param audio_dir - directory containing processed (e.g. renamed) tracks.
        """

        self.audio_dir = audio_dir
        self.audio_files = get_audio_files(audio_dir)

        # Double nested map: camelot code -> bpm -> set of tracks
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

            if id3_data is None or not REQUIRED_TAGS.issubset(set(id3_data.keys())):
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

        orig_files = get_audio_files(source_dir)

        # Find high/low quality files
        high_quality = []
        low_quality = []
        for f in orig_files:
            track_path = join(source_dir, f)
            if is_high_quality(track_path):
                high_quality.append(track_path)
            else:
                low_quality.append(track_path)

        # Write them to their respective directories and delete files in source directory
        for f in high_quality:
            new_name = join(hq_dir, basename(f))
            print('Moving ' + f + ' to ' + new_name)
            copyfile(f, new_name)
            remove(f)

        for f in low_quality:
            new_name = join(lq_dir, basename(f))
            print('Moving ' + f + ' to ' + new_name)
            copyfile(f, new_name)
            remove(f)

    #############################
    # Harmonic mixing functions #
    #############################

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
