from os.path import basename, splitext
from shutil import copyfile

from src.db import database
from src.db.entities.artist import Artist as ArtistEntity
from src.db.entities.artist_track import ArtistTrack
from src.db.entities.track import Track
from src.definitions.common import *
from src.definitions.data_management import *
from src.tools.data_management.audio_file import AudioFile
from src.utils.data_management import split_artist_string
from src.utils.errors import handle_error
from src.utils.file_operations import *


class DataManager:
    """ Encapsulates track collection metadata management utilities. """

    def __init__(self, audio_dir=PROCESSED_MUSIC_DIR):
        """
        Initializes class with music directory info.

        :param audio_dir: Directory containing processed (e.g. renamed) tracks.
        """

        self.audio_dir = audio_dir
        self.database = database
        self.audio_files = get_audio_files(self.audio_dir)

    def load_tracks(self):
        """ Loads tracks from the database into memory. """

        session = self.database.create_session()

        try:
            return session.query(Track).all()
        finally:
            session.close()

    def insert_tracks(self, tracks):
        """
        Inserts new track rows to the database.

        :param tracks: Dictionary mapping track name to its internal model
        """

        session = self.database.create_session()
        try:
            for new_track_path, track in tracks.items():
                # Create row in track table
                track_metadata = track.get_metadata()
                db_row = {k: v for k, v in track_metadata.items() if k in ALL_TRACK_DB_COLS}
                db_row[TrackDBCols.FILE_PATH.value] = new_track_path

                try:
                    session.add(Track(**db_row))
                    session.commit()
                except Exception as e:
                    handle_error(e)
                    continue

                # Update artists' data
                track_id = session.query(Track).filter_by(file_path=new_track_path).first().id
                artists = track_metadata.get(ArtistFields.ARTISTS.value)
                remixers = track_metadata.get(ArtistFields.REMIXERS.value)

                all_artists = split_artist_string(artists) + split_artist_string(remixers)
                for a in all_artists:
                    artist_row = session.query(ArtistEntity).filter_by(name=a).first()
                    if artist_row is None:
                        try:
                            session.add(ArtistEntity(**{'name': a, 'track_count': 1}))
                            session.commit()
                        except Exception as e:
                            handle_error(e)
                            continue

                        artist_row = session.query(ArtistEntity).filter_by(name=a).first()
                    else:
                        artist_row.track_count += 1

                    # Create row in artist_track table
                    try:
                        session.add(ArtistTrack(**{'track_id': track_id, 'artist_id': artist_row.id}))
                        session.commit()
                    except Exception as e:
                        handle_error(e)
                        continue

        except Exception as e:
            handle_error(e)
            raise e

        finally:
            session.close()

    def upsert_tracks(self, tracks):
        """
        Upserts new metadata to existing track rows.

        :param tracks: Dictionary mapping track name to its internal model
        """

        session = self.database.create_session()
        columns_to_update = [c for c in ALL_TRACK_DB_COLS if not (c == 'id' or c == 'file_path' or c == 'date_added')]

        try:
            for track_name, track in tracks.items():
                track_metadata = track.get_metadata()
                # Get existing row
                existing_track = session.query(Track).filter_by(file_path=track_name).first()
                if existing_track is None:
                    raise Exception('Could not find track associated with file path %s in DB' % track_name)

                # Update row with new metadata values
                for col in columns_to_update:
                    new_val = getattr(track_metadata, col)
                    if new_val is not None:
                        setattr(existing_track, col, new_val)

                session.commit()

        except Exception as e:
            handle_error(e)
            raise e

        finally:
            session.close()

    def update_database(self, tracks, upsert):
        """
        Updates the database with tracks' info.

        :param tracks: Dictionary mapping track name to internal model
        :param upsert: Indicates whether to update existing tracks
        """
        self.upsert_tracks(tracks) if upsert else self.insert_tracks(tracks)

    def rename_songs(self, input_dir=TMP_MUSIC_DIR, target_dir=None, upsert=False):
        """
        Standardizes song names and copy them to library.

        :param input_dir: Directory containing audio files to rename
        :param target_dir: Directory where updated audio files should be saved
        :param upsert: If True, tracks are upserted into the DB and original base names are retained
        """

        target_dir = target_dir or self.audio_dir
        input_files = get_audio_files(input_dir)
        tracks_to_save = {}

        for f in input_files:
            old_path = join(input_dir, f)
            old_base_name = basename(old_path)

            try:
                track = AudioFile(old_path)
            except Exception as e:
                handle_error(e, 'Couldn\'t read ID3 tags for %s' % old_path)
                continue

            id3_data = track.get_tags()
            if not REQUIRED_ID3_TAGS.issubset(set(id3_data.keys())):
                # Some files won't have requisite ID3 metadata for automatic renaming.
                # User will need to enter new name manually.
                print('Can\'t automatically rename %s due to missing requisite ID3 tags' % old_path)
                continue

            # Generate track name
            metadata = track.get_metadata()
            track_title = metadata.get(TrackDBCols.TITLE.value)
            if track_title is None and not upsert:
                print('Failed to generate title for %s' % old_path)
                continue

            _, file_ext = splitext(old_path)
            new_path = join(target_dir, old_base_name if upsert else track_title + file_ext)

            # Save updated tags and copy to target directory
            track.write_tags()
            new_base_name = basename(new_path)
            try:
                print('\nRenaming:\t%s\nto:\t\t%s' % (old_base_name, new_base_name))
                copyfile(old_path, new_path)
            except Exception as e:
                handle_error(e, 'Couldn\'t copy %s to target directory' % new_path)
                continue

            tracks_to_save[new_path] = track

        # Update database
        self.update_database(tracks_to_save, upsert)

    def show_malformed_tracks(self):
        """ Prints any malformed track names to stdout. """

        malformed = []
        for track in self.audio_files:
            track_md = re.findall(MD_SPLIT_REGEX, track)

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
