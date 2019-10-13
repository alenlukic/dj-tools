from collections import OrderedDict
from os.path import getctime
from time import ctime

from src.utils.data_management import *
from src.utils.file_management import *
from src.utils.utils import *


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
        for f in self.audio_files:
            track_path = join(self.audio_dir, f)
            track = Track(track_path)
            id3_data = track.get_id3_data()
            try:
                # Use heuristics to derive metadata from track title if no ID3 data
                if id3_data is None:
                    # Chop up the filename
                    track_md = re.findall(MD_FORMAT_REGEX, f)[0]
                    md_str = '[' + ' - '.join(track_md) + ']'
                    basename = ('.'.join(f.split('.')[0:-1])).split(md_str + ' ')[1]
                    split_basename = basename.split(' - ')

                    # Derive artists
                    artists = split_basename[0].split(' and ' if ' and ' in split_basename[0] else ' & ')

                    # Derive title and remixers
                    title = ' - '.join(split_basename[1:])
                    paren_index = title.find('(')
                    if paren_index != -1:
                        title = title[0:paren_index]
                        remix_segment = title[paren_index + 1:len(title) - 1].split(' ')
                        if remix_segment[-1] == 'Remix':
                            remixer_segment = ' '.join(remix_segment[0:-1])
                            remixers = remixer_segment.split(' and ' if ' and ' in remixer_segment else ' & ')
                    else:
                        remixers = []

                    camelot_code, key, bpm = track_md[0]
                    key = CANONICAL_KEY_MAP.get(key.lower())

                    genre = None
                    label = None
                    energy = None

                # Pick metadata off the ID3 data
                else:
                    title, featured = track.format_title()
                    artists = track.get_tag(ID3Tag.ARTIST)
                    artists = None if artists is None else artists.split(', ')
                    remixers = track.get_tag(ID3Tag.REMIXER)
                    remixers = None if remixers is None else remixers.split(', ')
                    genre = track.get_tag(ID3Tag.GENRE)
                    bpm = track.get_tag(ID3Tag.BPM)
                    key = track.format_key()
                    camelot_code = track.format_camelot_code()
                    energy = track.format_energy()

                key = None if key is None else key[0].upper() + ''.join(key[1:])
                date_added = ctime(getctime(track_path))
                track_metadata = {k: v for k, v in {
                    'Title': title,
                    'Artists': artists,
                    'Remixers': remixers,
                    'Genre': genre,
                    'Label': label,
                    'BPM': bpm,
                    'Key': key,
                    'Camelot Code': camelot_code,
                    'Energy': energy,
                    'Date Added': date_added
                }.items() if not is_empty(v)}

                collection_metadata[title] = track_metadata
                for artist in artists + remixers + ([] if featured is None else [featured]):
                    artist_counts[artist] += 1
            except Exception as e:
                print('Error %s while processing track %s' % (e, track))
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
                key_frame = list(filter(lambda frame: frame.id.decode('utf-8') == ID3_MAP[ID3Tag.KEY], md.frameiter()))

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
