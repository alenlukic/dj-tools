from os.path import basename

from src.definitions.data_management import *
from src.definitions.harmonic_mixing import *
from src.utils.common import log2smooth


class TransitionMatch:
    """ Wrapper for a track with a harmonic transition from the current track. """
    collection_md = None

    def __init__(self, metadata, cur_track_md, camelot_priority):
        """
        Initialize this track and playing track's metadata.

        :param metadata: This track's metadata.
        :param cur_track_md: Playing track's metadata.
        :param camelot_priority: Priority of the transition.
        """

        self.metadata = metadata
        self.cur_track_md = cur_track_md
        self.camelot_priority = camelot_priority
        self.score = None

    def get_score(self):
        """ Calculate the transition score using multiple weighed subscores. """

        if self.score is None:
            score_weights = [
                (self.get_artist_score(), 0.08),
                (self.get_bpm_score(), 0.23),
                (self.get_camelot_priority_score(), 0.23),
                (self.get_energy_score(), 0.05),
                (self.get_freshness_score(), 0.12),
                (self.get_genre_score(), 0.13),
                (self.get_label_score(), 0.16),
            ]
            self.score = 100 * sum([score * weight for score, weight in score_weights])

        return self.score

    def get_artist_score(self):
        """ Returns artist/remixer intersection component of the score. """

        artist_counts = self.metadata.get(ArtistFields.ARTISTS, {})
        remixer_counts = self.metadata.get(ArtistFields.REMIXERS, {})
        cur_track_artist_counts = self.cur_track_md.get(ArtistFields.ARTISTS, {})
        cur_track_remixer_counts = self.cur_track_md.get(ArtistFields.REMIXERS, {})

        artists = (set(artist_counts.keys())).union(set(remixer_counts.keys()))
        cur_track_artists = (set(cur_track_artist_counts.keys())).union(set(cur_track_remixer_counts.keys()))

        total_artists = len(artists) + len(cur_track_artists)
        if total_artists == 0:
            return 0.0

        overlap = artists.intersection(cur_track_artists)
        n = len(overlap)
        if n == 0:
            return 0.0

        unified_counts = {}
        for count_dict in [artist_counts, remixer_counts, cur_track_artist_counts, cur_track_remixer_counts]:
            for k, v in count_dict.items():
                unified_counts[k] = v

        log_artist_count = log2smooth(self.collection_md[CollectionStat.ARTIST_COUNTS])
        return sum([1.0 - (log2smooth(unified_counts[artist]) / log_artist_count) for artist in overlap]) / n

    def get_bpm_score(self):
        """ Calculates BPM match component of the score. """

        bpm = self.metadata.get(TrackDBCols.BPM)
        cur_track_bpm = self.cur_track_md.get(TrackDBCols.BPM)
        if bpm is None or cur_track_bpm is None:
            return 0.0

        # Exact match
        absolute_diff = cur_track_bpm - bpm
        if absolute_diff == 0:
            return 1.0

        # Current track's BPM is lower
        relative_diff = abs(absolute_diff) / float(cur_track_bpm)
        if absolute_diff < 0:
            if relative_diff <= SAME_UPPER_BOUND:
                return float(SAME_UPPER_BOUND - relative_diff) / SAME_UPPER_BOUND
            if relative_diff <= UP_KEY_UPPER_BOUND:
                # Not sure how to evaluate step up / down - arbitrarily pick middle of the range
                midpoint = (UP_KEY_LOWER_BOUND + UP_KEY_UPPER_BOUND) / 2
                return float(midpoint - abs(midpoint - relative_diff)) / midpoint
            return 0.0

        # Current track's BPM is higher
        abs_same_lower_bound = abs(SAME_LOWER_BOUND)
        abs_down_key_upper_bound = abs(DOWN_KEY_UPPER_BOUND)
        abs_down_key_lower_bound = abs(DOWN_KEY_LOWER_BOUND)
        if relative_diff <= abs_same_lower_bound:
            return float(abs_same_lower_bound - relative_diff) / abs_same_lower_bound
        if relative_diff <= abs_down_key_lower_bound:
            midpoint = (abs_down_key_lower_bound + abs_down_key_upper_bound) / 2
            return float(midpoint - abs(midpoint - relative_diff)) / midpoint

        return 0.0

    def get_camelot_priority_score(self):
        """ Gets camelot priority component of the score. """

        if self.camelot_priority == CamelotPriority.ONE_OCTAVE_JUMP:
            return 0.1
        if self.camelot_priority == CamelotPriority.ADJACENT_JUMP:
            return 0.25
        if self.camelot_priority == CamelotPriority.MAJOR_MINOR_JUMP:
            return 0.9

        return float(self.camelot_priority / CamelotPriority.SAME_KEY.value)

    def get_energy_score(self):
        """ Calculates the energy match component of the score. """

        energy = self.metadata.get(TrackDBCols.ENERGY)
        cur_track_energy = self.cur_track_md.get(TrackDBCols.ENERGY)
        if energy is None or cur_track_energy is None:
            return 0.0

        return 1.0 - (abs(energy - cur_track_energy) / 10.0)

    def get_freshness_score(self):
        """ Calculates the freshness component of the score. """
        date_added = self.metadata.get(TrackDBCols.DATE_ADDED)
        if date_added is None:
            return 0.5

        return (date_added - self.collection_md[CollectionStat.OLDEST]) / self.collection_md[CollectionStat.TIME_RANGE]

    def get_genre_score(self):
        """ Returns 1 if genres match and 0 otherwise. """

        genre = self.metadata.get(TrackDBCols.GENRE)
        cur_track_genre = self.cur_track_md.get(TrackDBCols.GENRE)

        return 0.0 if (genre is None or cur_track_genre is None or genre != cur_track_genre) else 1.0

    def get_label_score(self):
        """ Calculates the label match component of the score. """

        label, label_count = self.metadata.get(TrackDBCols.LABEL, (None, None))
        cur_label, cur_label_count = self.cur_track_md.get(TrackDBCols.LABEL, (None, None))
        if label is None or cur_label is None or label != cur_label:
            return 0.0

        return 1.0 - (log2smooth(label_count) / log2smooth(self.collection_md[CollectionStat.LABEL_COUNTS]))

    def format(self):
        """ Format result with score and track's base file name. """

        score = '{:.2f}'.format(self.get_score())
        title = '.'.join(basename(self.metadata[TrackDBCols.FILE_PATH]).split('.')[:-1])

        return '\t\t\t'.join([score, title if len(title) < 120 else title[:120] + '...'])

    def __lt__(self, other):
        return (self.get_score(), self.get_freshness_score()) < (other.get_score(), other.get_freshness_score())

    def __hash__(self):
        return hash(self.metadata[TrackDBCols.FILE_PATH])
