from collections import defaultdict


def flip_camelot_letter(camelot_letter):
    """
    Flip Camelot letter, i.e. A -> B and vice-versa.

    :param camelot_letter - the alphabetic portion of the Camelot code to format.
    """
    return 'A' if camelot_letter == 'B' else 'B'


def format_camelot_number(camelot_number):
    """
    Convert 0 to 12, and add leading 0 if needed, to the Camelot code number.

    :param camelot_number - the numerical portion of the Camelot code to format.
    """
    camelot_number = 12 if camelot_number == 0 else camelot_number
    return str(camelot_number) if camelot_number >= 10 else '0' + str(camelot_number)


def generate_camelot_map(metadata):
    """
    Generate double-nested map of camelot code -> BPM -> set of tracks.

    :param metadata - full qualified paths of all audio files in user's audio directory.
    """

    cm = defaultdict(lambda: defaultdict(list))
    for title, track_md in metadata.items():
        camelot_code = track_md['Camelot Code']
        bpm = track_md['BPM']
        cm[camelot_code][bpm].append(track_md)

    # for track in track_paths:
    #     try:
    #         triad = track[track.find('['): track.find(']') + 1].replace('[', '').replace(']', '')
    #         camelot_code, _, bpm = tuple([x.strip() for x in triad.split('-')])
    #         cm[camelot_code][bpm].append(track)
    #     except Exception as e:
    #         print('%s (offending track: %s)' % (e, track))
    #         continue

    return cm


def get_bpm_bound(bpm, bound):
    """
    Get BPM bound.

    :param bpm - track BPM.
    :param bound - percentage difference between current BPM and higher/lower BPMs.
    """
    return bpm / (1 + bound)
