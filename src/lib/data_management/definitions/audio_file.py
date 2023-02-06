from os import path
from time import ctime

import mutagen
from mutagen.id3 import TIT2, TCON, TBPM, TKEY, TPUB, COMM

from src.definitions.common import PROCESSED_MUSIC_DIR
from src.definitions.data_management import *
from src.utils.data_management import *
from src.utils.file_operations import get_file_creation_time


class AudioFile:
    """ Encapsulates an audio file and its metadata. """

    def __init__(self, track_name, track_directory=PROCESSED_MUSIC_DIR):
        # TODO: rm this hack once file_path values have been migrated in DB
        self.full_path = path.join(track_directory, track_name) if track_directory not in track_name else track_name
        self.basename = path.basename(track_name)
        self.id3 = mutagen.File(self.full_path)
        self.tags = self.read_tags()
        self.metadata = None

    def generate_metadata(self):
        bpm = self.format_bpm()
        key = self.format_key()
        camelot_code = AudioFile.format_camelot_code(key)
        title = dedupe_title(self.generate_title(camelot_code, key, bpm))

        metadata = {
            TrackDBCols.FILE_PATH.value: self.basename,
            TrackDBCols.TITLE.value: title,
            TrackDBCols.BPM.value: None if bpm is None else float(bpm),
            TrackDBCols.KEY.value: key,
            TrackDBCols.CAMELOT_CODE.value: camelot_code,
            TrackDBCols.ENERGY.value: self.parse_energy(),
            TrackDBCols.GENRE.value: transform_genre(self.get_tag(ID3Tag.GENRE, '')),
            TrackDBCols.LABEL.value: transform_label(self.get_tag(ID3Tag.LABEL, '')),
            TrackDBCols.DATE_ADDED.value: ctime(get_file_creation_time(self.full_path))
        }
        metadata = {k: v for k, v in metadata.items() if not is_empty(v)}
        metadata[TrackDBCols.COMMENT.value] = self.generate_comment(metadata)

        return metadata

    def generate_comment(self, metadata):
        comment = {k: v for k, v in dict(ChainMap(
            {k: v for k, v in metadata.items()},
            {
                ArtistFields.ARTISTS.value: self.get_tag(ID3Tag.ARTIST),
                ArtistFields.REMIXERS.value: self.get_tag(ID3Tag.REMIXER)
            }
        )).items() if not is_empty(v) and k != TrackDBCols.COMMENT.value}

        return str(comment)

    # =====================
    # Title-related methods
    # =====================

    def generate_title(self, camelot_code, key, bpm):
        parsed_title, featured = self.parse_title()
        title_prefix = AudioFile.generate_title_prefix(camelot_code, key, bpm)
        artist_midfix = self.format_artist_string(featured) + ('' if featured is None else ' ft. ' + featured)

        return (title_prefix + artist_midfix + ' - ' + parsed_title).strip()

    @staticmethod
    def generate_title_prefix(camelot_code, key, bpm):
        if camelot_code is None or key is None or bpm is None:
            return ''

        return ' - '.join(['[' + camelot_code, key, bpm + ']']) + ' '

    def format_artist_string(self, featured):
        artists = self.get_tag(ID3Tag.ARTIST)
        featured_set = set() if featured is None else {transform_artist(featured)}
        filtered_artists = [transform_artist(a) for a in split_artist_string(artists) if a not in featured_set]

        # If any artist names contain "&" then we want to use "and" to separate artist names in the title, for clarity
        # TODO: handle artist aliases
        separator = ' and ' if any('&' in artist for artist in filtered_artists) else ' & '
        return separator.join(filtered_artists)

    def parse_title(self):
        title = self.get_tag(ID3Tag.TITLE, '')
        segments = [seg.strip() for seg in title.split(' ') if not is_empty(seg)]

        i = 0
        n = len(segments)
        featured = None
        in_parens = False
        filtered_segments = []
        while i < n:
            segment = segments[i]

            if '(' in segment:
                in_parens = True

            if ')' in segment and '(' not in segment:
                in_parens = False

            # Replace all instances of 'feat.' with 'ft.' inside the parenthetical phrase indicating mix type.
            # Ex: "(Hydroid feat. Santiago Nino Mix)" becomes "(Hydroid ft. Santiago Nino Mix)"
            segment_lowercase = segment.lower()
            if segment_lowercase == 'feat.' or segment_lowercase == 'ft.':
                if in_parens:
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

                    if j == n - 1:
                        break
                    i = j

            else:
                filtered_segments.append(segment)
                i += 1

            if ')' in segment:
                in_parens = False

        # Get rid of the "(Original Mix)" and "(Extended Mix)" redundant suffixes.
        formatted_title = ' '.join(filtered_segments).replace('(Original Mix)', '').replace('(Extended Mix)', '')

        return formatted_title, featured

    # =======================
    # Feature-related methods
    # =======================

    def parse_energy(self):
        try:
            energy = self.get_tag(ID3Tag.ENERGY)
            return int(energy)
        except Exception:
            pass

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
                    track_metadata = (load_comment(comment) if comment.startswith('{')
                                      else load_comment(comment.split('Metadata: ')[1]))
                    return int(track_metadata.get('Energy', ''))

            except Exception:
                continue

        return None

    def format_bpm(self):
        bpm = self.get_tag(ID3Tag.BPM)
        if bpm is None:
            return None

        parts = bpm.split('.')
        whole = parts[0]
        fractional = parts[1] if len(parts) > 1 else '00'
        whole_padded = (str(0) * max(3 - len(whole), 0)) + whole
        fractional_padded = fractional + (str(0) * max(2 - len(fractional), 0))

        return '.'.join([whole_padded, fractional_padded])

    def format_key(self):
        key = self.get_tag(ID3Tag.KEY)
        if key is None:
            return None

        canonical_key = CANONICAL_KEY_MAP.get(key.lower())
        return None if canonical_key is None else canonical_key.capitalize()

    @staticmethod
    def format_camelot_code(formatted_key):
        return None if formatted_key is None else CAMELOT_MAP.get(formatted_key.lower())

    # =======
    # Getters
    # =======

    def get_basename(self):
        return self.basename

    def get_metadata(self):
        if self.metadata is None:
            self.metadata = self.generate_metadata()
        return self.metadata

    def get_tag(self, tag, default=None):
        id3_tag = getattr(tag, 'value', tag)
        tag_values = self.tags.get(id3_tag, [])

        if len(tag_values) > 0:
            return tag_values[0]

        synonym_values = list(self.get_synonym_values(id3_tag).values())
        if len(synonym_values) > 0:
            return synonym_values[0][0]

        return default

    @staticmethod
    def get_tag_synonyms(tag):
        return ID3_TAG_SYNONYMS.get(tag, [tag])

    def get_synonym_values(self, tag):
        return {k: v for k, v in {
            syn: self.tags.get(syn, []) for syn in AudioFile.get_tag_synonyms(tag)
        }.items() if len(v) > 0}

    def get_tags(self):
        return self.tags

    # ===================
    # ID3-related methods
    # ===================

    def get_id3(self):
        if self.id3 is not None:
            return self.id3

        self.id3 = mutagen.File(self.full_path)
        if self.id3 is None:
            raise Exception('Could not load ID3 data for %s' % self.full_path)

        return self.id3

    def read_tags(self):
        return {k: getattr(self.get_id3().get(k, {}), 'text', []) for k in TRACK_MD_ID3_TAGS}

    def write_tag(self, tag, value, save=True):
        id3 = self.get_id3()
        text = [normalize_tag_text(value)]

        if tag in id3.keys():
            id3[tag].text = text

        elif tag in TRACK_MD_ID3_TAGS:
            if tag == ID3Tag.TITLE.value:
                id3[tag] = TIT2(text=text)
            elif tag == ID3Tag.GENRE.value:
                id3[tag] = TCON(text=text)
            elif tag == ID3Tag.BPM.value:
                id3[tag] = TBPM(text=text)
            elif tag == ID3Tag.KEY.value:
                id3[tag] = TKEY(text=text)
            elif tag == ID3Tag.LABEL.value:
                id3[tag] = TPUB(text=text)
            elif tag == ID3Tag.COMMENT.value or tag == ID3Tag.COMMENT_ENG.value or tag == ID3Tag.COMMENT_XXX.value:
                id3[ID3Tag.COMMENT.value] = COMM(text=text)
                id3[ID3Tag.COMMENT_ENG.value] = COMM(text=text)
                id3[ID3Tag.COMMENT_XXX.value] = COMM(text=text)

        if save:
            self.save_tags()

    def write_tags(self, tags_to_write=None):
        track_metadata = tags_to_write or self.get_metadata()

        for k, v in track_metadata.items():
            mk = METADATA_KEY_TO_ID3.get(k)
            synonyms = set([mk] + list(self.get_synonym_values(mk).keys()))
            for syn in synonyms:
                self.write_tag(syn, v, False)

        self.save_tags()

    def save_tags(self):
        self.id3.save()
