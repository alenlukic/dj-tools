from ast import literal_eval
from collections import defaultdict
from datetime import datetime

from src.definitions.data_management import *
from src.definitions.harmonic_mixing import CollectionStat, TIMESTAMP_FORMAT
from src.tools.data_management.audio_file import AudioFile
from src.utils.common import get_with_fallbacks, is_empty


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

    track_md_index = {}
    for track in tracks:
        file_path = track.file_path
        track_model = AudioFile(file_path)
        track_metadata = track_model.get_metadata()
        track_tags = track_model.get_tags()
        try:
            track_comment = literal_eval(track_metadata.get(TrackDBCols.COMMENT.value, '{}'))
        except Exception:
            track_comment = {}

        # Load artists/remixers
        artist_data_sources = [track_comment, track_tags]
        artist_str = get_with_fallbacks(artist_data_sources, [ID3Tag.ARTIST] * len(artist_data_sources), '')
        remixer_str = get_with_fallbacks(artist_data_sources, [ID3Tag.REMIXER] * len(artist_data_sources), '')
        artists = [a.strip() for a in artist_str.split(',')]
        remixers = [r.strip() for r in remixer_str.split(',')]

        # Increment artist counts
        for artist in artists + remixers:
            if not is_empty(artist):
                artist_counts[artist] += 1

        def get_track_col_value(track_db_col, typ=str):
            value = get_with_fallbacks([track_metadata, track, track_comment], [track_db_col.value] * 3)
            if value is not None:
                return type(typ)(value)

            return None

        # Create track metadata dict and add to index
        title = get_track_col_value(TrackDBCols.TITLE)
        bpm = get_track_col_value(TrackDBCols.BPM, int)
        key = get_track_col_value(TrackDBCols.KEY)
        camelot_code = get_track_col_value(TrackDBCols.CAMELOT_CODE)
        label = get_track_col_value(TrackDBCols.LABEL)
        genre = get_track_col_value(TrackDBCols.GENRE)
        energy = get_track_col_value(TrackDBCols.ENERGY, int)
        date_added = get_track_col_value(TrackDBCols.DATE_ADDED)

        # Increment label count
        if not is_empty(label):
            label_counts[label] += 1

        track_md = {k: v for k, v in {
            TrackDBCols.FILE_PATH: file_path,
            TrackDBCols.TITLE: title,
            ArtistFields.ARTISTS: {artist: 0 for artist in artists},
            ArtistFields.REMIXERS: {remixer: 0 for remixer in remixers},
            TrackDBCols.BPM: bpm,
            TrackDBCols.KEY: key,
            TrackDBCols.CAMELOT_CODE: camelot_code,
            TrackDBCols.LABEL: (label, None),
            TrackDBCols.GENRE: genre,
            TrackDBCols.ENERGY: energy,
            TrackDBCols.DATE_ADDED: datetime.strptime(date_added, TIMESTAMP_FORMAT).timestamp(),
        }.items() if not is_empty(v)}
        track_md_index[file_path] = track_md

    # Add sum of counts to collection metadata counter
    collection_md[CollectionStat.LABEL_COUNTS] = sum(label_counts.values())
    collection_md[CollectionStat.ARTIST_COUNTS] = sum(artist_counts.values())

    camelot_map = defaultdict(lambda: defaultdict(list))
    for track in tracks:
        track_md = track_md_index[track.file_path]

        # Update artist, remixer, and label counts for track
        if ArtistFields.ARTISTS in track_md:
            track_md[ArtistFields.ARTISTS] = {a: artist_counts[a] for a in track_md[ArtistFields.ARTISTS]}
        if ArtistFields.REMIXERS in track_md:
            track_md[ArtistFields.REMIXERS] = {r: artist_counts[r] for r in track_md[ArtistFields.REMIXERS]}
        if TrackDBCols.LABEL in track_md:
            label = track_md[TrackDBCols.LABEL][0]
            track_md[TrackDBCols.LABEL] = (label, label_counts[label])

        # Update global timestamp extrema
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
