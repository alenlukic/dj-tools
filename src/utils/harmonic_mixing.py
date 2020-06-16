from collections import defaultdict
from datetime import datetime

from src.definitions.data_management import *
from src.definitions.harmonic_mixing import CollectionStat, TIMESTAMP_FORMAT
from src.tools.data_management.audio_file import AudioFile
from src.utils.common import is_empty
from src.utils.data_management import load_comment


def flip_camelot_letter(camelot_letter):
    """
    Flip Camelot letter, i.e. A -> B and vice-versa.

    :param camelot_letter: The alphabetic portion of the Camelot code to format.
    """
    return 'A' if camelot_letter == 'B' else 'B'


def format_camelot_number(camelot_number):
    """
    Convert 0 to 12, and add leading 0 if needed, to the Camelot code number.

    :param camelot_number: The numerical portion of the Camelot code to format.
    """
    camelot_number = 12 if camelot_number == 0 else camelot_number
    return str(camelot_number) if camelot_number >= 10 else '0' + str(camelot_number)


def generate_camelot_map(tracks):
    """
    Generate and return map of camelot code -> BPM -> set of tracks, along with collection metadata.

    :param tracks: Set of all tracks in the DB.
    """

    collection_md = {CollectionStat.NEWEST: -1, CollectionStat.OLDEST: float('inf')}
    label_counts = defaultdict(int)
    artist_counts = defaultdict(int)

    track_mds = []
    for track in tracks:
        file_path = track.file_path
        track_comment = track.comment

        # A failsafe - if comment not in DB, try to generate it
        if track_comment is None:
            try:
                track_model = AudioFile(file_path)
                track_metadata = track_model.get_metadata()
                track_comment = track_metadata.get(TrackDBCols.COMMENT.value, '{}')
            except Exception:
                track_comment = '{}'

        track_comment = load_comment(track_comment)

        # Increment artist/remixer counts
        artist_str = track_comment.get(ArtistFields.ARTISTS.value, '')
        remixer_str = track_comment.get(ArtistFields.REMIXERS.value, '')
        artists = [a.strip() for a in artist_str.split(',')]
        remixers = [r.strip() for r in remixer_str.split(',')]
        for artist in artists + remixers:
            if not is_empty(artist):
                artist_counts[artist] += 1

        # Create track metadata dict and add to index
        title = track_comment.get(TrackDBCols.TITLE.value)
        bpm = track_comment.get(TrackDBCols.BPM.value)
        key = track_comment.get(TrackDBCols.KEY.value)
        camelot_code = track_comment.get(TrackDBCols.CAMELOT_CODE.value)
        label = track_comment.get(TrackDBCols.LABEL.value)
        genre = track_comment.get(TrackDBCols.GENRE.value)
        energy = track_comment.get(TrackDBCols.ENERGY.value)
        date_added = track_comment.get(TrackDBCols.DATE_ADDED.value)

        # Increment label count
        if not is_empty(label):
            label_counts[label] += 1

        track_md = {k: v for k, v in {
            TrackDBCols.FILE_PATH: file_path,
            TrackDBCols.TITLE: title,
            ArtistFields.ARTISTS: {artist: 0 for artist in artists},
            ArtistFields.REMIXERS: {remixer: 0 for remixer in remixers},
            TrackDBCols.BPM: None if bpm is None else int(bpm),
            TrackDBCols.KEY: key,
            TrackDBCols.CAMELOT_CODE: camelot_code,
            TrackDBCols.LABEL: (label, 0),
            TrackDBCols.GENRE: genre,
            TrackDBCols.ENERGY: None if energy is None else int(energy),
            TrackDBCols.DATE_ADDED: (None if date_added is None else
                                     datetime.strptime(date_added, TIMESTAMP_FORMAT).timestamp())
        }.items() if not is_empty(v)}

        track_mds.append(track_md)

    # Add sum of counts to collection metadata counter
    collection_md[CollectionStat.LABEL_COUNTS] = sum(label_counts.values())
    collection_md[CollectionStat.ARTIST_COUNTS] = sum(artist_counts.values())

    camelot_map = defaultdict(lambda: defaultdict(list))
    for track_md in track_mds:
        # Update artist, remixer, and label counts for track
        if ArtistFields.ARTISTS in track_md:
            track_md[ArtistFields.ARTISTS] = {a: artist_counts[a] for a in track_md[ArtistFields.ARTISTS]}
        if ArtistFields.REMIXERS in track_md:
            track_md[ArtistFields.REMIXERS] = {r: artist_counts[r] for r in track_md[ArtistFields.REMIXERS]}
        if TrackDBCols.LABEL in track_md:
            label = track_md[TrackDBCols.LABEL][0]
            track_md[TrackDBCols.LABEL] = (label, label_counts[label])

        # Update global timestamp extrema

        if TrackDBCols.DATE_ADDED in track_md:
            date_added = track_md[TrackDBCols.DATE_ADDED]
            if date_added > collection_md[CollectionStat.NEWEST]:
                collection_md[CollectionStat.NEWEST] = date_added
            if date_added < collection_md[CollectionStat.OLDEST]:
                collection_md[CollectionStat.OLDEST] = date_added

        # Add track metadata to Camelot map
        camelot_code = track_md[TrackDBCols.CAMELOT_CODE]
        bpm = track_md[TrackDBCols.BPM]
        camelot_map[camelot_code][bpm].append(track_md)

    time_range = collection_md[CollectionStat.NEWEST] - collection_md[CollectionStat.OLDEST]
    collection_md[CollectionStat.TIME_RANGE] = time_range

    return camelot_map, collection_md


def get_bpm_bound(bpm, bound):
    """
    Get BPM bound.

    :param bpm: Track BPM.
    :param bound: Percentage difference between current BPM and higher/lower BPMs.
    """
    return bpm / (1 + bound)
