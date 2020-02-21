from abc import ABC, abstractmethod
from ast import literal_eval
from collections import ChainMap
from os import path, stat
from time import ctime

from src.utils.common import is_empty
from src.definitions.data_management import *


class AudioFile(ABC):
    def __init__(self, full_path):
        self.full_path = full_path
        self.basename = path.basename(full_path)
        self.id3 = self.read_id3()
        self.tags = self.read_tags()
        self.metadata = self.generate_metadata()

    def generate_metadata(self):
        """ Generates audio metadata. """
        bpm = self.format_bpm()
        key = self.format_key()
        camelot_code = self.format_camelot_code(key)
        title = self.generate_title(camelot_code, key, bpm)

        metadata = {
            'file_path': self.full_path,
            'title': title,
            'bpm': int(bpm),
            'key': key,
            'camelot_code': camelot_code,
            'energy': self.parse_energy(),
            'genre': self.tags.get(ID3Tag.GENRE.value),
            'label': self.tags.get(ID3Tag.LABEL.value),
            'date_added': ctime(stat(self.full_path).st_birthtime)
        }
        metadata = {k: v for k, v in metadata.items() if not is_empty(v)}
        metadata['comment'] = str({k: v for k, v in dict(ChainMap(
            {k: v for k, v in metadata.items() if k != 'file_path'},
            {'artists': self.tags.get(ID3Tag.ARTIST.value), 'remixers': self.tags.get(ID3Tag.REMIXER.value)}
        )).items() if not is_empty(v)})

        return metadata

    # =====================
    # Title-related methods
    # =====================

    def generate_title(self, camelot_code, key, bpm):
        """
        Generates track title.

        :param camelot_code: Track's Camelot Code.
        :param key: Track's key.
        :param bpm: Track's BPM.
        """

        parsed_title, featured = self.parse_title()
        title_prefix = self.generate_title_prefix(camelot_code, key, bpm)
        artist_midfix = self.format_artist_string(featured) + ('' if featured is None else ' ft. ' + featured)

        return title_prefix + ' ' + artist_midfix + ' - ' + parsed_title

    def generate_title_prefix(self, camelot_code, key, bpm):
        """
        Generates title prefix metadata.

        :param camelot_code: Track's Camelot Code.
        :param key: Track's key.
        :param bpm: Track's BPM.
        """
        return ' - '.join(['[' + camelot_code, key.capitalize(), bpm + ']'])

    def format_artist_string(self, featured):
        """
        Generate formatted artist string (first segment of artist midfix in track title).

        :param featured: Featured artist on the track (if any).
        """
        artists = self.tags.get(ID3Tag.ARTIST.value)
        featured_set = set() if featured is None else set(featured)
        filtered_artists = list(filter(lambda artist: artist not in featured_set, artists.split(', ')))

        # If any artist names contain "&" then we want to use "and" to separate artist names in the title, for clarity.
        # TODO: handle artist aliases
        separator = ' and ' if any('&' in artist for artist in filtered_artists) else ' & '
        return separator.join(filtered_artists)

    def parse_title(self):
        """ Parses track title and returns formatted track title and featured artist name, if any. """

        segments = self.tags.get(ID3Tag.TITLE.value).split(' ')
        n = len(segments)

        i = 0
        featured = None
        open_paren_found = False
        filtered_segments = []
        while i < n:
            segment = segments[i]

            if '(' in segment:
                open_paren_found = True

            # Replace all instances of 'feat.' with 'ft.' inside the parenthetical phrase indicating mix type.
            # Ex: "(Hydroid feat. Santiago Nino Mix)" becomes "(Hydroid ft. Santiago Nino Mix)."
            segment_lowercase = segment.lower()
            if segment_lowercase == 'feat.' or segment_lowercase == 'ft.':
                if open_paren_found:
                    filtered_segments.append('ft.')
                    i += 1
                else:
                    # If we haven't seen an open parentheses yet, assume featured artist's
                    # name is composed of all words occuring before the parentheses and after 'ft.'
                    featured = []
                    for j in range(i + 1, n):
                        next_part = segments[j]
                        if '(' in next_part:
                            break
                        featured.append(next_part)
                    featured = ' '.join(featured)
                    i = j
            else:
                filtered_segments.append(segment.strip())
                i += 1

        # Get rid of the "(Original Mix)" and "(Extended Mix)" redundant suffixes.
        formatted_title = ' '.join(filtered_segments).replace('(Original Mix)', '').replace('(Extended Mix)', '')

        return formatted_title, featured

    # =======================
    # Feature-related methods
    # =======================

    def parse_energy(self):
        """ Parse track energy (if any) from the comment tag. """
        comment = self.tags.get(ID3Tag.COMMENT.value)
        if comment is None:
            return None

        if comment.startswith('Energy'):
            segments = [s.strip() for s in comment.split()]
            if len(segments) > 1 and segments[1].isnumeric():
                return int(segments[1])

        if comment.startswith('Metadata: '):
            track_metadata = literal_eval(comment.split('Metadata: ')[1])
            energy = str(track_metadata.get('Energy', ''))
            return None if not energy.isnumeric() else int(energy)

        return None

    def format_bpm(self):
        """ Format BPM value as padded 3-digit representation. """
        bpm = self.tags.get(ID3Tag.BPM.value)
        return ''.join([str(0)] * max(3 - len(bpm), 0)) + bpm

    def format_key(self):
        """ Formats track key as canonical representation. """
        key = self.tags.get(ID3Tag.KEY.value)
        return CANONICAL_KEY_MAP.get(key.lower())

    def format_camelot_code(self, formatted_key):
        """ Formats Camelot code based on track key. """
        return CAMELOT_MAP.get(formatted_key)

    # =======
    # Getters
    # =======

    def get_basename(self):
        """ Return file base name. """
        return self.basename

    def get_metadata(self):
        """ Return track's metadata dict. """
        return self.metadata

    # ===================
    # ID3-related methods
    # ===================

    @abstractmethod
    def read_id3(self):
        """ Read ID3 data from file. """
        pass

    @abstractmethod
    def read_tags(self):
        """ Read relevant tags from ID3 data. """
        pass

    @abstractmethod
    def write_tags(self):
        """ Writes ID3 tags to file. """
        pass
