from ast import literal_eval
from collections import defaultdict

from src.utils.common import is_empty


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


def generate_camelot_map(tracks):
    """
    Generate double-nested map of camelot code -> BPM -> set of tracks.

    :param tracks - set of all tracks in the DB.
    """

    label_counts = defaultdict(int)
    for track in tracks:
        if track.label is not None:
            label_counts[track.label] += 1

    track_md_index = {}
    cm = defaultdict(lambda: defaultdict(list))
    for track in tracks:
        try:
            comment = literal_eval(track.comment)
        except Exception:
            comment = {}
        track_md = {k: v for k, v in {
            'Path': track.file_path,
            'Title': track.title,
            'Artists': comment.get('Artists'),
            'Remixers': comment.get('Remixers'),
            'BPM': track.bpm,
            'Key': track.key,
            'Camelot Code': track.camelot_code,
            'Label': track.label,
            'Label Count': label_counts[track.label],
            'Genre': track.genre,
            'Energy': track.energy,
            'Date Added': track.date_added
        }.items() if not is_empty(v)}
        track_md_index[track.file_path] = track_md

        camelot_code = track_md['Camelot Code']
        bpm = track_md['BPM']
        cm[camelot_code][bpm].append(track_md)

    return cm, track_md_index


def get_bpm_bound(bpm, bound):
    """
    Get BPM bound.

    :param bpm - track BPM.
    :param bound - percentage difference between current BPM and higher/lower BPMs.
    """
    return bpm / (1 + bound)
