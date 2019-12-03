from collections import defaultdict, OrderedDict
import logging
from os.path import basename, exists
from shutil import copyfile

from src.db.database import Database
from src.db.entities.artist import Artist as ArtistEntity
from src.db.entities.artist_track import ArtistTrack as ArtistTrackEntity
from src.db.entities.track import Track as TrackEntity
from src.definitions.common import *
from src.definitions.data_management import *
from src.tools.data_management.track import Track
from src.utils.common import is_empty
from src.utils.data_management import *
from src.utils.file_operations import *


# Suppress annoying eyed3 logs
logging.getLogger('eyed3').setLevel(logging.ERROR)


class DataManager:
    """ Encapsulates track collection metadata management utilities. """

    def __init__(self, audio_dir=PROCESSED_MUSIC_DIR, data_dir=DATA_DIR):
        """
        Initializes class with music directory info.

        :param audio_dir - directory containing processed (e.g. renamed) tracks.
        """

        self.audio_dir = audio_dir
        self.data_dir = data_dir
        self.database = Database()
        self.audio_files = get_audio_files(self.audio_dir)

    def generate_collection_metadata(self, output_file='metadata.json'):
        """
        Generates collection and track metadata.

        :param output_file - name of output JSON file to be saved in the data directory.
        """

        collection_metadata = {}
        artist_counts = defaultdict(int)
        label_counts = defaultdict(int)

        # Generate metadata
        for track_file in self.audio_files:
            track_path = join(self.audio_dir, track_file)
            track_metadata = self.write_track_metadata(track_path)
            if track_metadata is not None:
                collection_metadata[track_path] = track_metadata.get_metadata()
                for artist in track_metadata.artists + track_metadata.remixers:
                    artist_counts[artist] += 1
                if track_metadata.label is not None:
                    label_counts[track_metadata.label] += 1

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

        # Sort label counts in order of decreasing frequency
        sorted_label_counts = OrderedDict()
        sorted_count_tuples = sorted([(v, k) for k, v in label_counts.items()], reverse=True)
        for count, label in sorted_count_tuples:
            sorted_label_counts[label] = count

        # Write metadata to file
        output = {
            'Track Metadata': sorted_track_metadata,
            'Artist Counts': sorted_artist_counts,
            'Label Counts': sorted_label_counts
        }
        with open(join(self.data_dir, output_file), 'w') as w:
            json.dump(output, w, indent=2)

    def generate_track_metadata(self, track_path):
        """
        Generate formatted metadata for a track.

        :param track_path - Qualified path to the track.
        """

        track = Track(track_path)
        id3_data = track.get_id3_data()
        try:
            return (self._generate_metadata_heuristically(track) if is_empty(id3_data) else
                    track.generate_metadata_from_id3())
        except Exception as e:
            print('Error while generating metadata for track %s: %s' % (track_path, e))
            return None

    def write_track_metadata(self, track_path):
        """
        Generate formatted metadata for a track and write it to its comment field.

        :param track_path - Qualified path to the track.
        """

        try:
            track_metadata = self.generate_track_metadata(track_path)
            if track_metadata is None:
                return None
            track_metadata.write_tags(track_path)
            return track_metadata
        except Exception as e:
            print('Error while writing metadata for track %s: %s' % (track_path, e))
            return None

    def load_collection_metadata(self, data_dir=DATA_DIR, file_name='metadata.json'):
        """
        Loads collection metadata from JSON.

        :param data_dir - directory where metadata JSON is located
        :param file_name - name of file containing metadata
        """

        file_path = join(data_dir, file_name)
        if exists(file_path):
            with open(file_path, 'r') as f:
                return json.load(f)

        return {}

    def update_collection_metadata(self, new_tracks, data_dir=DATA_DIR, file_name='metadata.json'):
        """
        Updates the metadata collection with new tracks. TODO: deprecate this.

        :param new_tracks - dictionary mapping new track name to its metadata
        :param data_dir - directory where metadata JSON is located
        :param file_name - name of file containing metadata
        """

        metadata = self.load_collection_metadata(data_dir, file_name)

        for track_name, track_metadata in new_tracks.items():
            md_dict = track_metadata.get_metadata()
            metadata['Track Metadata'][track_name] = md_dict

            artists = md_dict.get('Artists', []) + md_dict.get('Remixers', [])
            for artist in artists:
                metadata['Artist Counts'][artist] = metadata['Artist Counts'].get(artist, 0) + 1
            label = md_dict.get('Label')
            if label is not None:
                metadata['Label Counts'][label] = metadata['Label Counts'].get(label, 0) + 1

        with open(join(data_dir, file_name), 'w') as w:
            json.dump(metadata, w, indent=2)

    def update_database(self, new_tracks):
        """
        Updates the database with new tracks' info.

        :param new_tracks - dictionary mapping new track name to its metadata
        """

        sessions = []

        for track_name, track_metadata in new_tracks.items():
            try:
                session = self.database.create_session()
                sessions.append(session)

                # Create row in track table
                session.add(TrackEntity(**track_metadata.get_database_row(track_name)))
                session.commit()

                # Update artists' data
                track_id = session.query(TrackEntity).filter_by(file_path=track_name).first().id
                for artist in (track_metadata.artists or []) + (track_metadata.remixers or []):
                    # Create or update row in artist table
                    artist_row = session.query(ArtistEntity).filter_by(name=artist).first()
                    if artist_row is None:
                        session.add(ArtistEntity(**{'name': artist, 'track_count': 1}))
                        session.commit()
                        artist_row = session.query(ArtistEntity).filter_by(name=artist).first()
                    else:
                        artist_row.track_count += 1

                    # Create row in artist_track table
                    session.add(ArtistTrackEntity(**{'track_id': track_id, 'artist_id': artist_row.id}))

                session.commit()

            except Exception as e:
                session.rollback()
                raise e

        self.database.close_sessions(sessions)

    def rename_songs(self, input_dir=TMP_MUSIC_DIR, target_dir=None):
        """
        Standardizes song names and copy them to library.

        :param input_dir - directory containing audio files to rename.
        :param target_dir - directory where updated audio files should be saved
        """

        target_dir = target_dir or self.audio_dir
        input_files = get_audio_files(input_dir)
        new_tracks = {}

        for f in input_files:
            old_name = join(input_dir, f)
            old_base_name = basename(old_name)
            track = Track(old_name)
            id3_data = track.get_id3_data()

            if is_empty(id3_data) is None or not REQUIRED_ID3_TAGS.issubset(set(id3_data.keys())):
                # All non-mp3 audio files (and some mp3 files) won't have requisite ID3 metadata for automatic renaming
                # - user will need to enter new name manually.
                print('Can\'t automatically rename this track: %s' % old_base_name)
                print('Enter the new name here:')
                new_name = join(target_dir, input())
                copyfile(old_name, new_name)
            else:
                # Generate formatted track name
                formatted_name = track.format_track_name()
                new_name = ''.join([join(target_dir, formatted_name).strip(), '.', old_name.split('.')[-1].strip()])

                # Copy track to user audio directory
                copyfile(old_name, new_name)
                new_track = load(new_name).tag
                new_track.title = formatted_name
                new_track.save()

                # Create metadata
                metadata = self.write_track_metadata(new_name)
                new_tracks[new_name] = metadata

            new_base_name = basename(new_name)
            try:
                print('\nRenaming:\t%s\nto:\t\t%s' % (old_base_name, new_base_name))
            except Exception as e:
                print('Could not rename %s to %s (exception: %s)' % (old_base_name, new_base_name, str(e)))

        # Update collection metadata
        self.update_collection_metadata(new_tracks)
        self.update_database(new_tracks)

    def show_malformed_tracks(self):
        """ Prints any malformed track names to stdout. """

        malformed = []
        for track in self.audio_files:
            track_md = re.findall(MD_FORMAT_REGEX, track)

            # Metadata missing or malformed
            if len(track_md) != 1 or len(track_md[0]) != 3:
                malformed.append((track, 'Malformed metadata'))
                continue

            camelot_code, key, bpm = track_md[0]
            key = key.lower()
            canonical_key = CANONICAL_KEY_MAP.get(key)

            # Key is missing or malformed
            if canonical_key is None or key != canonical_key:
                malformed.append((track, 'Invalid key'))
                continue

            canonical_cc = CAMELOT_MAP.get(canonical_key)

            # Camelot code/key mismatch
            if camelot_code != canonical_cc:
                malformed.append((track, 'Camelot code/key mismatch'))
                continue

            # BPM is malformed
            if len(bpm) != 3 or not bpm.isnumeric():
                malformed.append((track, 'Malformed BPM'))

        malformed = sorted(malformed)
        for track, error in malformed:
            print('Track: %s\nError: %s\n\n' % (track, error))

    def _generate_metadata_heuristically(self, track):
        """
        Use formatted track name to derive subset of track metadata when ID3 tags not available.

        :param track - Track wrapper class instance.
        """

        base_path = basename(track.get_track_path())
        title = '.'.join(base_path.split('.')[0:-1])

        # Chop up the filename
        track_md_matches = re.findall(MD_FORMAT_REGEX, base_path)

        if len(track_md_matches) == 1:
            track_md = track_md_matches[0]
        else:
            raise Exception('Could not parse metadata from title for track %s' % base_path)

        md_str = '[' + ' - '.join(track_md) + ']'
        base_name = title.split(md_str + ' ')[1]
        split_basename = base_name.split(' - ')
        title_suffix = ' - '.join(split_basename[1:])
        paren_index = title_suffix.find('(')

        # Format title and derive featured artist
        formatted_title, featured = parse_title(base_name)

        # Derive artists - TODO: handle artist aliases and "ft."
        artists = split_basename[0].split(' and ' if ' and ' in split_basename[0] else ' & ') + [featured]

        # Derive remixers
        remixers = []
        if paren_index != -1:
            title_suffix = title_suffix[0:paren_index]
            remix_span = title_suffix[paren_index + 1:len(title_suffix) - 1]
            remix_segment = remix_span.split(' ')

            if "'s" in remix_span:
                remixers.append(remix_span.split("'s")[0])
            elif remix_segment[-1] == 'Remix':
                # TODO: handle artist aliases and "ft."
                remixer_segment = ' '.join(remix_segment[0:-1])
                remixers = remixer_segment.split(' and ' if ' and ' in remixer_segment else ' & ')

        camelot_code, key, bpm = track_md
        key = CANONICAL_KEY_MAP.get(key.lower())
        key = None if key is None else key[0].upper() + ''.join(key[1:])
        date_added = track.get_date_added()

        return track.generate_metadata(formatted_title, artists, remixers, None, None,
                                       bpm, key, camelot_code, None, date_added)
