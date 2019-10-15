class TransitionMatch:
    """ Encapsulates a matching transition track. """

    def __init__(self, metadata, current_track_md, camelot_priority):
        self.metadata = metadata
        self.current_track_md = current_track_md
        self.camelot_priority = camelot_priority
        self.score = None

    def format(self):
        return '{:.2f}'.format(self.get_score()) + '\t\t' + self.metadata['Title']

    def get_score(self):
        if self.score is None:
            artists = set(self.metadata.get('Artists', []) + self.metadata.get('Remixers', []))
            ct_artists = set(self.current_track_md.get('Artists', []) + self.current_track_md.get('Remixers', []))
            artist_score = len(artists.intersection(ct_artists))
            genre_score = 0.5 * self._get_attribute_score('Genre')
            label_score = self._get_attribute_score('Label')
            energy_score = self._get_energy_score()

            self.score = artist_score + genre_score + label_score + energy_score

        return self.score

    def _get_attribute_score(self, attribute):
        if self.metadata.get(attribute) is None or self.current_track_md.get(attribute) is None:
            return 0.0

        return 1.0 if self.metadata[attribute] == self.current_track_md[attribute] else 0.0

    def _get_energy_score(self):
        energy = self.metadata.get('Energy')
        current_track_energy = self.current_track_md.get('Energy')
        if energy is None or current_track_energy is None:
            return 0.0

        return 1.0 - (abs(energy - current_track_energy) / 10.0)

    def __lt__(self, other):
        return self.camelot_priority < other.camelot_priority or self.get_score() < other.get_score()

    def __eq__(self, other):
        return self.camelot_priority == other.camelot_priority and self.get_score() == other.get_score()
