from collections import defaultdict

from src.definitions.data_management import *
from src.definitions.harmonic_mixing import CollectionStat
from src.lib.data_management.definitions.audio_file import AudioFile
from src.utils.common import *
from src.utils.data_management import load_comment, split_artist_string


def flip_camelot_letter(camelot_letter):
    return "A" if camelot_letter == "B" else "B"


def format_camelot_number(camelot_number):
    camelot_number = 12 if camelot_number == 0 else camelot_number
    return str(camelot_number) if camelot_number >= 10 else "0" + str(camelot_number)


def generate_artist_counts(artist_counts, track_md_dict):
    result = {}
    for a in track_md_dict:
        result[a] = artist_counts[a]
    return result


def generate_camelot_map(tracks):
    collection_md = {
        CollectionStat.NEWEST: -1,
        CollectionStat.OLDEST: float("inf"),
        CollectionStat.SMMS_MAX: get_max_smms(),
    }
    label_counts = defaultdict(int)
    artist_counts = defaultdict(int)
    camelot_map = defaultdict(lambda: defaultdict(list))

    track_mds = []
    for track in tracks:
        file_name = track.file_name
        comment = track.comment
        track_comment = load_comment(
            comment
            or AudioFile(file_name).get_metadata().get(TrackDBCols.COMMENT.value)
        )

        # Increment artist/remixer counts
        artists = split_artist_string(track_comment.get(ArtistFields.ARTISTS.value, ""))
        remixers = split_artist_string(
            track_comment.get(ArtistFields.REMIXERS.value, "")
        )
        for artist in artists + remixers:
            artist_counts[artist] += 1

        # Increment label count
        if not is_empty(track.label):
            label_counts[track.label] += 1

        # Create track metadata dict and add to index
        track_mds.append(
            {
                k: v
                for k, v in {
                    TrackDBCols.ID: track.id,
                    TrackDBCols.FILE_NAME: file_name,
                    TrackDBCols.TITLE: track.title,
                    TrackDBCols.BPM: get_or_default(track, "bpm", float_transform),
                    TrackDBCols.KEY: track.key,
                    TrackDBCols.CAMELOT_CODE: track.camelot_code,
                    TrackDBCols.LABEL: track.label,
                    TrackDBCols.GENRE: track.genre,
                    TrackDBCols.ENERGY: get_or_default(track, "energy", int_transform),
                    TrackDBCols.DATE_ADDED: get_or_default(
                        track, "date_added", datetime_transform
                    ),
                    ArtistFields.ARTISTS: {artist: 0 for artist in artists},
                    ArtistFields.REMIXERS: {remixer: 0 for remixer in remixers},
                }.items()
                if not is_empty(v)
            }
        )

    # Add sum of counts to collection metadata counter
    collection_md[CollectionStat.LABEL_COUNTS] = sum(label_counts.values())
    collection_md[CollectionStat.ARTIST_COUNTS] = sum(artist_counts.values())

    for track_md in track_mds:
        # Update artist, remixer, and label counts for track
        if ArtistFields.ARTISTS in track_md:
            track_md[ArtistFields.ARTISTS] = generate_artist_counts(
                artist_counts, track_md[ArtistFields.ARTISTS]
            )
        if ArtistFields.REMIXERS in track_md:
            track_md[ArtistFields.REMIXERS] = generate_artist_counts(
                artist_counts, track_md[ArtistFields.REMIXERS]
            )
        if TrackDBCols.LABEL in track_md:
            label = track_md[TrackDBCols.LABEL]
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

    time_range = (
        collection_md[CollectionStat.NEWEST] - collection_md[CollectionStat.OLDEST]
    )
    collection_md[CollectionStat.TIME_RANGE] = time_range

    return camelot_map, collection_md


def get_bpm_bound(bpm, bound):
    return bpm / (1 + bound)


def get_max_smms():
    return get_config_value(["HARMONIC_MIXING", "3_SD_SMMS"])
