from ast import literal_eval
from collections import defaultdict
from datetime import datetime

from src.definitions.harmonic_mixing import TIMESTAMP_FORMAT
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
    Generate and return map of camelot code -> BPM -> set of tracks, along with collection metadata.

    :param tracks - set of all tracks in the DB.
    """

    collection_md = {'Newest Timestamp': -1}

    # Generate label counts
    label_counts = defaultdict(int)
    for track in tracks:
        if track.label is not None:
            label_counts[track.label] += 1
    collection_md['Label Counts'] = sum(label_counts.values())

    track_md_index = {}
    camelot_map = defaultdict(lambda: defaultdict(list))
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
            'Date Added': datetime.strptime(track.date_added, TIMESTAMP_FORMAT).timestamp(),
        }.items() if not is_empty(v)}
        track_md_index[track.file_path] = track_md

        if track_md['Date Added'] > collection_md['Newest Timestamp']:
            collection_md['Newest Timestamp'] = track_md['Date Added']

        camelot_code = track_md['Camelot Code']
        bpm = track_md['BPM']
        camelot_map[camelot_code][bpm].append(track_md)

    return camelot_map, track_md_index, collection_md


def get_bpm_bound(bpm, bound):
    """
    Get BPM bound.

    :param bpm - track BPM.
    :param bound - percentage difference between current BPM and higher/lower BPMs.
    """
    return bpm / (1 + bound)
