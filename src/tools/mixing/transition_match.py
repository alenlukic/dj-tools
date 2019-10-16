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
        return '\t\t'.join([str(self.camelot_priority), '{:.2f}'.format(self.get_score()),
                            basename(self.metadata['Path'])])

    def get_score(self):
        """ Calculate the transition score using several factors. """
        if self.score is None:
            artists = set(self.metadata.get('Artists', []) + self.metadata.get('Remixers', []))
            cur_track_artists = set(self.cur_track_md.get('Artists', []) + self.cur_track_md.get('Remixers', []))
            artist_score = len(artists.intersection(cur_track_artists))
            label_score = self._get_attribute_score('Label')
            genre_score = 0.5 * self._get_attribute_score('Genre')
            energy_score = 0.5 * self._get_energy_score()

            self.score = artist_score + genre_score + label_score + energy_score

        return self.score

    def _get_attribute_score(self, attribute):
        """ Default scoring method - returns 1 if the attributes match, and 0 otherwise. """
        if self.metadata.get(attribute) is None or self.cur_track_md.get(attribute) is None:
            return 0.0

        return 1.0 if self.metadata[attribute] == self.cur_track_md[attribute] else 0.0

    def _get_energy_score(self):
        """ Calculates the energy match component of the score. """
        energy = self.metadata.get('Energy')
        cur_track_energy = self.cur_track_md.get('Energy')
        if energy is None or cur_track_energy is None:
            return 0.0

        return 1.0 - (abs(energy - cur_track_energy) / 10.0)

    def __lt__(self, other):
        if self.camelot_priority < other.camelot_priority:
            return True
        return self.get_score() < other.get_score()

    def __eq__(self, other):
        return self.camelot_priority == other.camelot_priority and self.get_score() == other.get_score()
