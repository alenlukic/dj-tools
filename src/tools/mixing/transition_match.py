from os.path import basename

class TransitionMatch:
    """ Wrapper for a track with a harmonic transition from the current track. """

    def __init__(self, metadata, cur_track_md, camelot_priority):
        """
        Initialize this track and playing track's metadata.

        :param metadata - this track's metadata.
        :param cur_track_md - playing track's metadata.
        :param camelot_priority - priority of the transition.
        """

        self.metadata = metadata
        self.cur_track_md = cur_track_md
        self.camelot_priority = camelot_priority
        self.score = None

    def format(self):
        """ Format result with score and track's base file name. """
        return '\t\t'.join([str(self.camelot_priority), '{:.3f}'.format(self.get_score()),
                            basename(self.metadata['Path'])])

    def get_bpm_score(self):
        """ Calculates BPM match component of the score. """

        bpm = str(self.metadata.get('BPM', ''))
        cur_track_bpm = str(self.cur_track_md.get('BPM', ''))
        if not (bpm.isnumeric() and cur_track_bpm.isnumeric()):
            return 0.5

        bpm = int(bpm)
        cur_track_bpm = int(cur_track_bpm)

        return min(bpm, cur_track_bpm) / max(bpm, cur_track_bpm)

    def get_score(self):
        """ Calculate the transition score using several factors. """
        if self.score is None:
            score_weights = [
                (self._get_artist_score(), 0.25),
                (self.get_bpm_score(), 0.25),
                (self._get_energy_score(), 0.125),
                (self._get_attribute_score('Genre'), 0.125),
                (self._get_attribute_score('Label'), 0.25),
            ]
            self.score = sum([score * weight for score, weight in score_weights])

        return self.score

    def _get_artist_score(self):
        """ Returns artist/remixer intersection component of the score. """

        artists = set(self.metadata.get('Artists', []) + self.metadata.get('Remixers', []))
        cur_track_artists = set(self.cur_track_md.get('Artists', []) + self.cur_track_md.get('Remixers', []))
        total_artists = float(len(artists) + len(cur_track_artists))

        return len(artists.intersection(cur_track_artists)) / total_artists

    def _get_attribute_score(self, attribute):
        """ Default scoring method - returns 1 if the attributes match, 0.5 if one or both missing, and 0 otherwise. """

        if self.metadata.get(attribute) is None or self.cur_track_md.get(attribute) is None:
            return 0.5

        return 0.0 if self.metadata[attribute] != self.cur_track_md[attribute] else 1.0

    def _get_energy_score(self):
        """ Calculates the energy match component of the score. """

        energy = str(self.metadata.get('Energy', ''))
        cur_track_energy = str(self.cur_track_md.get('Energy', ''))
        if not (energy.isnumeric() and cur_track_energy.isnumeric()):
            return 0.5

        energy = int(energy)
        cur_track_energy = int(cur_track_energy)
        return 1.0 - (abs(energy - cur_track_energy) / 10.0)

    def __lt__(self, other):
        return ((self.camelot_priority, self.get_score(), self.get_bpm_score()) <
                (other.camelot_priority, other.get_score(), other.get_bpm_score()))

    def __hash__(self):
        return hash(self.metadata['Title'])
