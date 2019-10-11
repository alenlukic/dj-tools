from collections import defaultdict
from os import listdir
from os.path import isfile, join

from eyed3 import id3 as metadata, load

from src.definitions.file_processing import *


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
    keys = list(filter(lambda k: k in ALL_ID3_TAGS, id3.keys()))

    return defaultdict(str, {k: id3[k] for k in keys})


def format_artists(artists, featured):
    """
    Formats artist string.

    :param artists - comma-separated string of artist names.
    :param featured - a "featured" artist, if any.
    """

    featured_set = set() if featured is None else set(featured)
    filtered_artists = list(filter(lambda artist: artist not in featured_set, artists.split(', ')))
    # If any artist names contain "&" then we want to use "and" to separate artist names in the title, for clarity.
    separator = ' and ' if any('&' in artist for artist in filtered_artists) else ' & '

    return separator.join(filtered_artists)


def format_bpm(bpm):
    """
    Formats BPM string.

    :param bpm - original BPM.
    """

    return ''.join([str(0) for i in range(max(3 - len(bpm), 0))]) + bpm


def format_title(title):
    """
    Formats track title.

    :param title - raw, unformatted track title.
    """

    if title is None:
        return None, None

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


def format_track_name(title, artists, featured, bpm, key):
    """
    Formats track name.

    :param title - formatted track title.
    :param artists - formatted artists.
    :param featured - "featured" artist, if any.
    :param bpm - formatted track BPM.
    :param key - canonical track key.
    """

    camelot_prefix = ' - '.join(
        ['[' + CAMELOT_MAP[key], key.capitalize(), bpm + ']'])
    artist_midfix = artists + (' ft. ' + featured if featured is not None else '')
    return camelot_prefix + ' ' + artist_midfix + ' - ' + title


def get_audio_files(input_dir):
    """
    Gets all the audio files in the given directory.

    :param input_dir - directory to inspect for audio files.
    """
    files = list(filter(lambda f: isfile(join(input_dir, f)), listdir(input_dir)))
    return list(filter(lambda f: f.split('.')[-1].lower() in AUDIO_TYPES, files))


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
    return False if md is None else any(frame.id == BEATPORT_ID3_TAG for frame in md.tag.frameiter())


def print_malformed_tracks(track_paths):
    """
    Prints any malformed track names to stdout.

    :param track_paths - list of full qualified paths to audio files
    """

    malformed = []
    for track in track_paths:
        track_md = re.findall(FORMAT_REGEX, track)

        # Metadata missing or malformed
        if len(track_md) != 1 or len(track_md[0]) != 3:
            malformed.append((track, 'Malformed metadata'))
            continue

        camelot_code, key, bpm = track_md[0]
        key = key.lower()
        canonical_key = CANONICAL_KEY_MAP.get(key)

        # Key is missing or malformed
        if canonical_key is None or key != canonical_key:
            malformed.append((track, 'Invalid key'))
            continue

        canonical_cc = CAMELOT_MAP.get(canonical_key)

        # Camelot code/key mismatch
        if camelot_code != canonical_cc:
            malformed.append((track, 'Camelot code/key mismatch'))
            continue

        # BPM is malformed
        if len(bpm) != 3 or not bpm.isnumeric():
            malformed.append((track, 'Malformed BPM'))

    malformed = sorted(malformed)
    for track, error in malformed:
        print('Track: %s\nError: %s\n\n' % (track, error))
