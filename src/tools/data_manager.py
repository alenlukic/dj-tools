from collections import OrderedDict
from os.path import basename

from src.utils.data_management import *
from src.utils.file_management import *


class DataManager:
    """ Encapsulates track collection metadata management utilities. """

    def __init__(self, audio_dir=PROCESSED_MUSIC_DIR, data_dir=DATA_DIR):
        """
        Initializes class with music directory info.

        :param audio_dir - directory containing processed (e.g. renamed) tracks.
        """

        self.audio_dir = audio_dir
        self.data_dir = data_dir
        self.audio_files = get_audio_files(self.audio_dir)

    def generate_collection_metadata(self, output_file='metadata.json'):
        """
        Generates collection and track metadata.

        :param output_file - name of output JSON file to be saved in the data directory.
        """

        collection_metadata = {}
        artist_counts = defaultdict(int)

        # Generate metadata
        for f in self.audio_files:
            track_path = join(self.audio_dir, f)
            track_name = '.'.join(f.split('.')[0:-1])
            track = Track(track_path)
            id3_data = track.get_id3_data()
            try:
                track_metadata = (self._generate_metadata_heuristically(track) if id3_data is None else
                                  self._generate_metadata_from_id3(track))
                track_metadata.write_metadata_to_comment(track_path)
                collection_metadata[track_name] = track_metadata.get_metadata()
                for artist in track_metadata.artists + track_metadata.remixers:
                    artist_counts[artist] += 1
            except Exception as e:
                print('Error while processing track %s: %s' % (f, e))
                continue

        # Sort track names alphabetically
        sorted_track_metadata = OrderedDict()
        sorted_track_names = sorted(list(collection_metadata.keys()))
        for track_name in sorted_track_names:
            sorted_track_metadata[track_name] = collection_metadata[track_name]

        # Sort artist counts in order of decreasing frequency
        sorted_artist_counts = OrderedDict()
        sorted_count_tuples = sorted([(v, k) for k, v in artist_counts.items()], reverse=True)
        for count, artist in sorted_count_tuples:
            sorted_artist_counts[artist] = count

        # Write metadata to file
        output = {
            'Track Metadata': sorted_track_metadata,
            'Artist Counts': sorted_artist_counts
        }
        with open(join(self.data_dir, output_file), 'w') as w:
            json.dump(output, w, indent=2)

    def standardize_key_tags(self):
        """ Uses track titles to set a standard ID3 key tag for all audio files. """

        warnings = []
        errors = []
        for track in self.audio_files:
            try:
                md = load(join(PROCESSED_MUSIC_DIR, track))
                if md is None:
                    warnings.append('Could not load ID3 data for %s' % track)
                    continue
                md = md.tag
                key_frame = list(filter(lambda frame: frame.id.decode('utf-8') == ID3Tag.KEY.value, md.frameiter()))

                if len(key_frame) == 1:
                    track_md = re.findall(MD_FORMAT_REGEX, track)
                    _, key, _ = track_md[0]
                    key_frame[0].text = key
                    md.save()
                else:
                    warnings.append('No key frame found for %s' % track)
            except Exception as e:
                errors.append('Error with track %s: %s' % (track, str(e)))
                continue

        warnings = '\n'.join(sorted(warnings))
        errors = '\n'.join(sorted(errors))
        print('Warnings:\n%s' % warnings)
        print('\n\nErrors:\n%s' % errors)

    def _generate_metadata_from_id3(self, track):
        """
        Use ID3 tags to generate track metadata.

        :param track - Track wrapper class instance.
        """

        title, featured = track.format_title()
        artists = track.get_tag(ID3Tag.ARTIST)
        artists = ([] if artists is None else artists.split(', ')) + ([] if featured is None else [featured])
        remixers = track.get_tag(ID3Tag.REMIXER)
        remixers = [] if remixers is None else remixers.split(', ')
        genre = track.get_tag(ID3Tag.GENRE)
        label = track.get_tag(ID3Tag.LABEL)
        bpm = track.get_tag(ID3Tag.BPM)
        key = track.format_key()
        key = None if key is None else key[0].upper() + ''.join(key[1:])
        camelot_code = track.format_camelot_code()
        energy = track.format_energy()
        date_added = track.get_date_added()

        return TrackMetadata(title, artists, remixers, genre, label, bpm, key, camelot_code, energy, date_added)

    def _generate_metadata_heuristically(self, track):
        """
        Use formatted track name to derive subset of track metadata when ID3 tags not available.

        :param track - Track wrapper class instance.
        """

        base_path = basename(track.get_track_path())
        track_name = '.'.join(base_path.split('.')[0:-1])

        # Chop up the filename
        track_md = re.findall(MD_FORMAT_REGEX, base_path)[0]
        md_str = '[' + ' - '.join(track_md) + ']'
        base_name = track_name.split(md_str + ' ')[1]
        split_basename = base_name.split(' - ')

        # Derive artists
        artists = split_basename[0].split(' and ' if ' and ' in split_basename[0] else ' & ')

        # Derive title and remixers
        title = ' - '.join(split_basename[1:])
        paren_index = title.find('(')
        remixers = []
        if paren_index != -1:
            title = title[0:paren_index]
            remix_segment = title[paren_index + 1:len(title) - 1].split(' ')
            if remix_segment[-1] == 'Remix':
                remixer_segment = ' '.join(remix_segment[0:-1])
                remixers = remixer_segment.split(' and ' if ' and ' in remixer_segment else ' & ')

        camelot_code, key, bpm = track_md
        key = CANONICAL_KEY_MAP.get(key.lower())
        key = None if key is None else key[0].upper() + ''.join(key[1:])
        date_added = track.get_date_added()

        return TrackMetadata(title, artists, remixers, None, None, bpm, key, camelot_code, None, date_added)


if __name__ == '__main__':
    dm = DataManager()
    dm.generate_collection_metadata()
