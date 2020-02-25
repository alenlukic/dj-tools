from ast import literal_eval
from collections import ChainMap, defaultdict
from os import path, stat
from time import ctime

import mutagen

from src.utils.common import is_empty
from src.definitions.data_management import *


class AudioFile:
    """ Encapsulates an audio file and its metadata. """

    def __init__(self, full_path):
        """
        Constructor. Reads ID3 tags and generates metadata.

        :param full_path: Qualified path to the file on disk.
        """

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
        key = key.capitalize()
        title = self.generate_title(camelot_code, key, bpm)

        metadata = {
            'file_path': self.full_path,
            'title': title,
            'bpm': int(bpm),
            'key': key,
            'camelot_code': camelot_code,
            'energy': self.parse_energy(),
            'genre': self.get_tag(ID3Tag.GENRE),
            'label': self.get_tag(ID3Tag.LABEL),
            'date_added': ctime(stat(self.full_path).st_birthtime)
        }
        metadata = {k: v for k, v in metadata.items() if not is_empty(v)}

        comment = str({k: v for k, v in dict(ChainMap(
            {k: v for k, v in metadata.items()},
            {'artists': self.get_tag(ID3Tag.ARTIST), 'remixers': self.get_tag(ID3Tag.REMIXER)}
        )).items() if not is_empty(v)})
        metadata['comment'] = comment

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
        return ' - '.join(['[' + camelot_code, key, bpm + ']'])

    def format_artist_string(self, featured):
        """
        Generate formatted artist string (first segment of artist midfix in track title).

        :param featured: Featured artist on the track (if any).
        """
        artists = self.get_tag(ID3Tag.ARTIST, '')
        featured_set = set() if featured is None else set(featured)
        filtered_artists = list(filter(lambda artist: artist not in featured_set, artists.split(', ')))

        # If any artist names contain "&" then we want to use "and" to separate artist names in the title, for clarity.
        # TODO: handle artist aliases
        separator = ' and ' if any('&' in artist for artist in filtered_artists) else ' & '
        return separator.join(filtered_artists)

    def parse_title(self):
        """ Parses track title and returns formatted track title and featured artist name, if any. """

        title = self.get_tag(ID3Tag.TITLE, '')
        track_md = re.findall(MD_COMPOSITE_REGEX, title)
        if len(track_md) > 0:
            title = title.split(track_md[0])[-1].strip()
            title = title.split(' - ')[-1]

        segments = title.split(' ')
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
                    # If we haven't seen an open parentheses yet, assume featured artist's name
                    # is composed of all words occuring before the parentheses and after 'ft.'
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

        comment_tags = [ID3Tag.COMMENT, ID3Tag.USER_COMMENT, ID3Tag.COMMENT_ENG]
        for tag in comment_tags:
            try:
                comment = self.get_tag(tag)

                if comment is None:
                    continue

                if comment.isnumeric():
                    return int(comment)

                if comment.startswith('Energy'):
                    segments = [s.strip() for s in comment.split()]
                    return int(segments[1])

                if comment.startswith('Metadata: ') or comment.startswith('{'):
                    track_metadata = (literal_eval(comment) if comment.startswith('{')
                                      else literal_eval(comment.split('Metadata: ')[1]))
                    return int(track_metadata.get('Energy', ''))

            except Exception:
                continue

        return None

    def format_bpm(self):
        """ Format BPM value as padded 3-digit representation. """
        bpm = self.get_tag(ID3Tag.BPM, '')
        return ''.join([str(0)] * max(3 - len(bpm), 0)) + bpm

    def format_key(self):
        """ Formats track key as canonical representation. """
        return CANONICAL_KEY_MAP.get(self.get_tag(ID3Tag.KEY, '').lower(), '')

    def format_camelot_code(self, formatted_key):
        """ Formats Camelot code based on track key. """
        return CAMELOT_MAP.get(formatted_key, '')

    # =======
    # Getters
    # =======

    def get_basename(self):
        """ Return file base name. """
        return self.basename

    def get_metadata(self):
        """ Return track's metadata dict. """
        return self.metadata

    def get_tag(self, tag, default=None):
        """
        Return specified tag's value.

        :param tag: Tag whose value to return.
        :param default: Default value to return if tag value not present.
        """
        return self.tags.get(tag.value, default)

    def get_tags(self):
        """ Gets ID3 tag dict. """
        return self.tags

    # ===================
    # ID3-related methods
    # ===================

    def read_id3(self):
        """ Read ID3 data from file. """

        id3 = mutagen.File(self.full_path)
        if id3 is None:
            raise Exception('Could not load ID3 data for %s' % self.full_path)

        return id3

    def save_id3(self):
        """ Save ID3 tag values to file. """
        self.id3.save()

    def read_tags(self):
        """ Read relevant tags from ID3 data. """
        tag_dict = self.id3.items()
        return defaultdict(str, {k: v.text[0] for k, v in tag_dict if k in ALL_ID3_TAGS and len(v.text or []) > 0})

    def write_tag(self, tag, value, save=True):
        """
        Write value to specified ID3 tag.

        :param tag: Tag to write to.
        :param value: Tag value.
        :param save: Whether tag value should be saved to file immediately.
        """

        if tag in self.id3:
            self.id3[tag].text = [value]
            if save:
                self.id3.save()

    def write_tags(self):
        """ Writes metadata to ID3 tags and saves to file. """

        track_metadata = self.get_metadata()
        for k, v in track_metadata.items():
            mk = METADATA_KEY_TO_ID3.get(k)
            self.write_tag(mk, v)

        self.id3.save()
