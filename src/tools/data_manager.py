from src.utils.file_processing import *


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
        for track in self.audio_files:
            id3_data = extract_id3_data(join(self.audio_dir, track))

            # Use heuristics to derive metadata from track title if no ID3 data
            if id3_data is None:
                track_md = re.findall(FORMAT_REGEX, track)[0]
                basename = ('.'.join(track.split('.')[0:-1])).split(track_md + ' ')[1]
                split_basename = basename.split(' - ')

                artists = split_basename[0].split(' and ' if ' and ' in split_basename[0] else ' & ')
                title = ' - '.join(split_basename[1:])
                paren_index = title.index('(')
                if paren_index != -1:
                    title = title[0:paren_index]
                    remix_segment = title[paren_index + 1:len(title) - 1].split(' ')
                    if remix_segment[-1] == 'Remix':
                        remixer_segment = remix_segment[0:-1]
                        remixers = remixer_segment.split(' and ' if ' and ' in remixer_segment else ' & ')
                else:
                    remixers = []

                camelot_code, key, bpm = track_md[0]
                key = CANONICAL_KEY_MAP.get(key.lower())

            # Pick metadata off the ID3 data
            else:
                title, featured = format_title(id3_data.get(ID3Tag.TITLE))
                artists = id3_data.get(ID3Tag.ARTIST, '').split(', ')
                remixers = id3_data.get(ID3Tag.REMIXER, '').split(', ')
                key = CANONICAL_KEY_MAP.get(id3_data.get(ID3Tag.KEY, '').lower())
                bpm = id3_data.get(ID3Tag.BPM)
                camelot_code = CAMELOT_MAP.get(key)
                genre = id3_data.get(ID3Tag.GENRE)

            track_metadata = {k: v for k, v in {
                'Title': title,
                'Artists': artists,
                'Remixers': remixers,
                'BPM': bpm,
                'Key': key,
                'Genre': genre,
                'Camelot Code': camelot_code
            }.items() if not (v is None or v == '' or v == [])}

            for artist in artists + remixers + ([featured] if featured is not None else []):
                artist_counts[artist.lower()] += 1

            collection_metadata['.'.join(track.split('.')[0:-1])] = track_metadata

        output = {
            'Track Metadata': collection_metadata,
            'Artist Counts': artist_counts
        }

        with open(join(self.data_dir, output_file), 'w') as w:
            json.dump(output, w, indent=2)
