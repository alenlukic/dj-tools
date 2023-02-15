from src.db.entities.transition_match import TransitionMatch as TransitionMatchRow
from src.definitions.data_management import *
from src.definitions.feature_extraction import Feature
from src.definitions.harmonic_mixing import *
from src.utils.common import log2smooth


class TransitionMatch:
    """ Encapsulates a transition match from current track to next track. """
    collection_metadata = None
    db_session = None
    result_column_header = '   '.join(['Total Score', 'SMMS Score', ' Track'])

    def __init__(self, metadata, cur_track_md, camelot_priority):
        self.metadata = metadata
        self.cur_track_md = cur_track_md
        self.camelot_priority = camelot_priority
        self.score = None
        self.factors = {}

    def format(self):
        score = '{:.2f}'.format(self.get_score())
        smms_score = '{:.2f}'.format(100 * self.get_smms_score())
        return ('         ' * (6 - len(score))).join([score, smms_score, self.metadata[TrackDBCols.TITLE]])

    def get_score(self):
        if self.score is None:
            if self.cur_track_md[TrackDBCols.TITLE] == self.metadata[TrackDBCols.TITLE]:
                self.score = 100
            else:
                score_weights = [
                    (self.get_camelot_priority_score(), MATCH_WEIGHTS[MatchFactors.CAMELOT.name]),
                    (self.get_bpm_score(), MATCH_WEIGHTS[MatchFactors.BPM.name]),
                    (self.get_smms_score(), MATCH_WEIGHTS[MatchFactors.SMMS_SCORE.name]),
                    (self.get_freshness_score(), MATCH_WEIGHTS[MatchFactors.FRESHNESS.name]),
                    (self.get_genre_score(), MATCH_WEIGHTS[MatchFactors.GENRE.name]),
                    (self.get_label_score(), MATCH_WEIGHTS[MatchFactors.LABEL.name]),
                    (self.get_artist_score(), MATCH_WEIGHTS[MatchFactors.ARTIST.name]),
                    (self.get_energy_score(), MATCH_WEIGHTS[MatchFactors.ENERGY.name]),
                ]
                self.score = 100 * sum([score * weight for score, weight in score_weights])

        return self.score

    def get_artist_score(self):
        def _get_artist_score():
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

            log_artist_count = log2smooth(self.collection_metadata[CollectionStat.ARTIST_COUNTS])
            return sum([1.0 - (log2smooth(unified_counts[artist]) / log_artist_count) for artist in overlap]) / n

        if MatchFactors.ARTIST not in self.factors:
            self.factors[MatchFactors.ARTIST] = _get_artist_score()
        return self.factors[MatchFactors.ARTIST]

    def get_bpm_score(self):
        def _get_bpm_score():
            bpm = self.metadata.get(TrackDBCols.BPM)
            cur_track_bpm = self.cur_track_md.get(TrackDBCols.BPM)
            if bpm is None or cur_track_bpm is None:
                return 0.0

            absolute_diff = cur_track_bpm - bpm
            if absolute_diff == 0:
                return 1.0

            relative_diff = abs(absolute_diff) / float(cur_track_bpm)
            if absolute_diff < 0:
                if relative_diff <= SAME_UPPER_BOUND:
                    score = float(SAME_UPPER_BOUND - relative_diff) / SAME_UPPER_BOUND
                    self.factors[MatchFactors.BPM] = score
                    return score

                if relative_diff <= UP_KEY_UPPER_BOUND:
                    # TODO: Not sure how to evaluate step up / down - using range midpoint for now
                    midpoint = (UP_KEY_LOWER_BOUND + UP_KEY_UPPER_BOUND) / 2
                    return float(midpoint - abs(midpoint - relative_diff)) / midpoint

                return 0.0

            abs_same_lower_bound = abs(SAME_LOWER_BOUND)
            abs_down_key_upper_bound = abs(DOWN_KEY_UPPER_BOUND)
            abs_down_key_lower_bound = abs(DOWN_KEY_LOWER_BOUND)

            # Slightly discount score of lower BPM tracks
            score = 0.0
            discount = 0.9

            if relative_diff <= abs_same_lower_bound:
                score = float(abs_same_lower_bound - relative_diff) / abs_same_lower_bound

            if relative_diff <= abs_down_key_lower_bound:
                midpoint = (abs_down_key_lower_bound + abs_down_key_upper_bound) / 2
                score = float(midpoint - abs(midpoint - relative_diff)) / midpoint

            return score * discount

        if MatchFactors.BPM not in self.factors:
            self.factors[MatchFactors.BPM] = _get_bpm_score()
        return self.factors[MatchFactors.BPM]

    def get_camelot_priority_score(self):
        def _get_camelot_priority_score():
            if self.camelot_priority == CamelotPriority.ONE_OCTAVE_JUMP:
                self.factors[MatchFactors.CAMELOT] = 0.1
                return 0.1
            if self.camelot_priority == CamelotPriority.ADJACENT_JUMP:
                self.factors[MatchFactors.CAMELOT] = 0.25
                return 0.25
            if self.camelot_priority == CamelotPriority.MAJOR_MINOR_JUMP:
                self.factors[MatchFactors.CAMELOT] = 0.9
                return 0.9

            return float(self.camelot_priority / CamelotPriority.SAME_KEY.value)

        if MatchFactors.CAMELOT not in self.factors:
            self.factors[MatchFactors.CAMELOT] = _get_camelot_priority_score()
        return self.factors[MatchFactors.CAMELOT]

    # Track's energy as calculated by Mixed In Key
    def get_energy_score(self):
        def _get_energy_score():
            energy = self.metadata.get(TrackDBCols.ENERGY)
            cur_track_energy = self.cur_track_md.get(TrackDBCols.ENERGY)
            if energy is None or cur_track_energy is None:
                return 0.0

            return 1.0 - (abs(energy - cur_track_energy) / 10.0)

        if MatchFactors.ENERGY not in self.factors:
            self.factors[MatchFactors.ENERGY] = _get_energy_score()
        return self.factors[MatchFactors.ENERGY]

    def get_freshness_score(self):
        def _get_freshness_score():
            date_added = self.metadata.get(TrackDBCols.DATE_ADDED)
            if date_added is None:
                return 0.5

            return ((date_added - self.collection_metadata[CollectionStat.OLDEST]) /
                    self.collection_metadata[CollectionStat.TIME_RANGE])

        if MatchFactors.FRESHNESS not in self.factors:
            self.factors[MatchFactors.FRESHNESS] = _get_freshness_score()
        return self.factors[MatchFactors.FRESHNESS]

    def get_genre_score(self):
        def _get_genre_score():
            genre = self.metadata.get(TrackDBCols.GENRE)
            cur_track_genre = self.cur_track_md.get(TrackDBCols.GENRE)

            if genre is None or cur_track_genre is None:
                return 0.0

            if genre == cur_track_genre:
                return 1.0

            # TODO: genre-specific hacks, fix
            trance_genres = {'Trance', 'Classic Trance'}
            if genre in trance_genres and cur_track_genre in trance_genres:
                return 0.5

            return 0.0

        if MatchFactors.GENRE not in self.factors:
            self.factors[MatchFactors.GENRE] = _get_genre_score()
        return self.factors[MatchFactors.GENRE]

    def get_label_score(self):
        def _get_label_score():
            label, label_count = self.metadata.get(TrackDBCols.LABEL, (None, None))
            cur_label, cur_label_count = self.cur_track_md.get(TrackDBCols.LABEL, (None, None))
            if label != cur_label or label == 'CDR' or cur_label == 'CDR' or label is None or cur_label is None:
                return 0.0

            return 1.0 - (log2smooth(label_count) / log2smooth(self.collection_metadata[CollectionStat.LABEL_COUNTS]))

        if MatchFactors.LABEL not in self.factors:
            self.factors[MatchFactors.LABEL] = _get_label_score()
        return self.factors[MatchFactors.LABEL]

    def get_smms_score(self):
        def _get_smms_score():
            smms_score = self.db_session.query(TransitionMatchRow).filter(
                TransitionMatchRow.on_deck_id == self.cur_track_md.get(TrackDBCols.ID),
                TransitionMatchRow.candidate_id == self.metadata.get(TrackDBCols.ID)).first()
            if smms_score is None:
                return 0.0
            else:
                smms_val = smms_score.match_factors[Feature.SMMS.value]
                smms_max = self.collection_metadata[CollectionStat.SMMS_MAX]
                return max(0.0, 1.0 - (float(smms_val) / smms_max))

        if MatchFactors.SMMS_SCORE not in self.factors:
            self.factors[MatchFactors.SMMS_SCORE] = _get_smms_score()
        return self.factors[MatchFactors.SMMS_SCORE]

    def __lt__(self, other):
        return ((self.get_score(), self.get_smms_score(), self.get_freshness_score()) <
                (other.get_score(), self.get_smms_score(), other.get_freshness_score()))

    def __hash__(self):
        return hash(self.metadata[TrackDBCols.FILE_PATH])
