from src.utils.file_processing import *


class DataManager:

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
            id3_data = extract_id3_data(track_path)

            # Use heuristics to derive artists from track title if no ID3 data
            if id3_data is None:
                continue
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
                collection_metadata['.'.join(f.split('.')[0:-1])] = track_metadata

                for artist in artists + remixers + [featured]:
                    artist_counts[artist.lower()] += 1

        output = {
            'Track Metadata': collection_metadata,
            'Artist Counts': artist_counts
        }

        with open(join(self.data_dir, output_file), 'w') as w:
            json.dump(output, w, indent=2)
