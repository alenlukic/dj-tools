from src.definitions.data_management import *


def print_malformed_tracks(track_paths):
    """
    Prints any malformed track names to stdout.

    :param track_paths - list of full qualified paths to audio files
    """

    malformed = []
    for track in track_paths:
        track_md = re.findall(MD_FORMAT_REGEX, track)

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
