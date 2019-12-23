from ast import literal_eval
from collections import defaultdict
from datetime import datetime
from math import ceil

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

    collection_md = {'Newest Timestamp': -1, 'Oldest Timestamp': float('inf')}
    label_counts = defaultdict(int)
    artist_counts = defaultdict(int)

    track_md_index = {}
    for track in tracks:
        try:
            comment = literal_eval(track.comment)
        except Exception:
            comment = {}

        # Generate artist and label counts
        artists = comment.get('Artists', [])
        remixers = comment.get('Remixers', [])
        for artist in artists + remixers:
            if not is_empty(artist):
                artist_counts[artist] += 1

        label = track.label
        if not is_empty(label):
            label_counts[label] += 1

        # Create track metadata dict and add to index
        track_md = {k: v for k, v in {
            'Path': track.file_path,
            'Title': track.title,
            'Artists': {artist: 0 for artist in artists},
            'Remixers': {remixer: 0 for remixer in remixers},
            'BPM': track.bpm,
            'Key': track.key,
            'Camelot Code': track.camelot_code,
            'Label': (label, None),
            'Genre': track.genre,
            'Energy': track.energy,
            'Date Added': datetime.strptime(track.date_added, TIMESTAMP_FORMAT).timestamp(),
        }.items() if not is_empty(v)}
        track_md_index[track.file_path] = track_md

    # Add sum of counts to collection metadata counter
    collection_md['Label Counts'] = sum(label_counts.values())
    collection_md['Artist Counts'] = sum(artist_counts.values())

    camelot_map = defaultdict(lambda: defaultdict(list))
    for track in tracks:
        track_md = track_md_index[track.file_path]

        # Update artist, remixer, and label counts for track
        if 'Artists' in track_md:
            track_md['Artists'] = {artist: artist_counts[artist] for artist in track_md['Artists']}
        if 'Remixers' in track_md:
            track_md['Remixers'] = {remixer: artist_counts[remixer] for remixer in track_md['Remixers']}
        if 'Label' in track_md:
            label = track_md['Label'][0]
            track_md['Label'] = (label, label_counts[label])

        # Update global timestamp extrema
        date_added = track_md['Date Added']
        if date_added > collection_md['Newest Timestamp']:
            collection_md['Newest Timestamp'] = date_added
        if date_added < collection_md['Oldest Timestamp']:
            collection_md['Oldest Timestamp'] = date_added

        # Add track metadata to Camelot map
        camelot_code = track_md['Camelot Code']
        bpm = track_md['BPM']
        camelot_map[camelot_code][bpm].append(track_md)

    collection_md['Time Range'] = collection_md['Newest Timestamp'] - collection_md['Oldest Timestamp']

    return camelot_map, track_md_index, collection_md


def get_bpm_bound(bpm, bound):
    """
    Get BPM bound.

    :param bpm - track BPM.
    :param bound - percentage difference between current BPM and higher/lower BPMs.
    """
    return bpm / (1 + bound)
