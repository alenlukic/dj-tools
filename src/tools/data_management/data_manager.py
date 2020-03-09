from ast import literal_eval
from collections import defaultdict
import json
from os.path import basename, join, splitext
from shutil import copyfile

from src.db import database
from src.db.entities.artist import Artist
from src.db.entities.artist_track import ArtistTrack
from src.db.entities.track import Track
from src.definitions.common import PROCESSED_MUSIC_DIR
from src.definitions.data_management import *
from src.tools.data_management.audio_file import AudioFile
from src.utils.data_management import split_artist_string
from src.utils.errors import *
from src.utils.file_operations import get_audio_files


class DataManager:
    """ Encapsulates track database management utilities. """

    def __init__(self):
        """ Initialize data manager. """
        self.database = database

    def load_tracks(self):
        """ Loads tracks from the database into memory. """

        session = self.database.create_session()
        try:
            return session.query(Track).all()
        finally:
            session.close()

    def ingest_tracks(self, input_dir, target_dir=PROCESSED_MUSIC_DIR, upsert=False):
        """
        Ingest new tracks - extract tags, format fields, and create DB entries.

        :param input_dir: Directory containing audio files to ingest
        :param target_dir: Directory where updated audio files should be saved
        :param upsert: If True, tracks are upserted into the DB and original base names are retained
        """

        session = self.database.create_session()

        try:
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
                    print('Can\'t automatically rename %s due to missing requisite ID3 tags' % old_path)
                    continue

                # Generate track name
                metadata = track.get_metadata()
                track_title = metadata.get(TrackDBCols.TITLE.value)

                if track_title is None and not upsert:
                    print('Failed to generate title for %s' % old_path)
                    continue

                file_ext = splitext(old_path)[-1].strip()
                new_path = join(target_dir, old_base_name if upsert else track_title + file_ext)

                existing_track_check = session.query(Track).filter_by(file_path=new_path).first()
                if existing_track_check is not None:
                    print('Existing track (id: %d) in DB with path %s - skipping' % (existing_track_check.id, new_path))
                    continue

                # Copy to target directory
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
            self.upsert_tracks(tracks_to_save) if upsert else self.insert_tracks(tracks_to_save)

        except Exception as e:
            handle_error(e)

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
                # Update ID3 tags
                track.write_tags()

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

                try:
                    comment = literal_eval(track_metadata.get(TrackDBCols.COMMENT.value, '{}'))
                except Exception:
                    comment = {}

                title = comment.get(TrackDBCols.TITLE.value)

                # Update artists
                artist_updates = self.update_artists(session, comment)
                DataManager.print_database_operation_statuses('Artist update statuses for %s' % title, artist_updates)

                # Add artist tracks
                track_id = session.query(Track).filter_by(file_path=new_track_path).first().id
                successful_artist_ids = [a for a, s in artist_updates.items() if s != DBUpdateType.FAILURE]
                artist_track_updates = self.insert_artist_tracks(session, track_id, successful_artist_ids)
                DataManager.print_database_operation_statuses('Artist track updates statuses for %s' % title,
                                                              artist_track_updates)

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
            for track_path, track in tracks.items():
                # Update ID3 tags
                track.write_tags()

                # Get existing row
                existing_track = session.query(Track).filter_by(file_path=track_path).first()
                if existing_track is None:
                    raise Exception('Could not find track associated with file path %s in DB' % track_path)

                # Update row with new metadata values
                track_metadata = track.get_metadata()
                for col in columns_to_update:
                    new_val = track_metadata.get(col)
                    if new_val is not None:
                        setattr(existing_track, col, new_val)

                session.commit()

        except Exception as e:
            handle_error(e)
            raise e

        finally:
            session.close()

    def update_artists(self, session, track_comment_metadata):
        """
        Update artists after ingesting new track.

        :param session: Open DB session
        :param track_comment_metadata: Dictionary containing relevant track metadata, stored in the ID3 comment field
        """

        artists = track_comment_metadata.get(ArtistFields.ARTISTS.value)
        remixers = track_comment_metadata.get(ArtistFields.REMIXERS.value)
        all_artists = split_artist_string(artists) + split_artist_string(remixers)

        artist_updates = {}
        for a in all_artists:
            artist_row = session.query(Artist).filter_by(name=a).first()

            if artist_row is None:
                try:
                    session.add(Artist(**{'name': a, 'track_count': 1}))
                    session.commit()

                    artist_row = session.query(Artist).filter_by(name=a).first()
                    artist_updates[artist_row.id] = DBUpdateType.INSERT
                except Exception as e:
                    handle_error(e)
                    artist_updates[a] = DBUpdateType.FAILURE
                    continue
            else:
                artist_row.track_count += 1
                artist_updates[artist_row.id] = DBUpdateType.UPDATE

        return artist_updates

    def insert_artist_tracks(self, session, track_id, artist_ids):
        """
        Add artist tracks after ingesting new track.

        :param session: Open DB session
        :param track_id: The new track's ID in the database
        :param artist_ids: Artist IDs for artists associated with this track
        """

        artist_track_updates = {}
        for artist_id in artist_ids:
            try:
                session.add(ArtistTrack(**{'track_id': track_id, 'artist_id': artist_id}))
                session.commit()

                artist_track_row = session.query(ArtistTrack).filter_by(artist_id=artist_id).first()
                artist_track_updates[artist_track_row.id] = DBUpdateType.INSERT
            except Exception as e:
                handle_error(e)
                artist_track_updates[artist_id] = DBUpdateType.FAILURE
                continue

        return artist_track_updates

    def delete_tracks(self, track_ids):
        """
        Safely delete tracks.

        :param track_ids: IDs of tracks to delete
        """

        session = database.create_session()

        try:
            deletion_statuses, artist_ids_to_update = self.delete_artist_tracks(session, track_ids)
            DataManager.print_database_operation_statuses('Artist track deletion statuses', deletion_statuses)

            update_statuses = self.update_artist_counts(session, artist_ids_to_update)
            DataManager.print_database_operation_statuses('Artist track count update statuses', update_statuses)

            track_deletion_statuses = {}
            for track_id in track_ids:
                try:
                    track = session.query(Track).filter_by(id=track_id).first()
                    session.delete(track)
                    track_deletion_statuses[track_id] = DBUpdateType.DELETE
                except Exception as e:
                    handle_error(e)
                    track_deletion_statuses[track_id] = DBUpdateType.FAILURE
                    continue

            DataManager.print_database_operation_statuses('Track deletion statuses', track_deletion_statuses)

            print('Committing session')
            session.commit()

        except Exception as e:
            handle_error(e)
            print('Session not committed')

        finally:
            session.close()

    def delete_artist_tracks(self, session, track_ids):
        """
        Delete artist track entries associated with set of track IDs to be deleted.

        :param session: Current database session
        :param track_ids: IDs of tracks to delete
        """

        deletion_statuses = {}
        artist_ids_to_update = defaultdict(int)

        for track_id in track_ids:
            artist_tracks = session.query(ArtistTrack).filter_by(track_id=track_id).all()

            for at in artist_tracks:
                artist_id = at.artist_id

                try:
                    session.delete(at)
                    artist_ids_to_update[artist_id] += 1
                    deletion_statuses[(track_id, artist_id)] = DBUpdateType.DELETE

                except Exception as e:
                    handle_error(e)
                    deletion_statuses[(track_id, artist_id)] = DBUpdateType.FAILURE
                    continue

        return deletion_statuses, artist_ids_to_update

    def update_artist_counts(self, session, artist_ids_to_update):
        """
        Update artist counts to reflect deleted tracks.

        :param session: Current database session
        :param artist_ids_to_update: IDs of artists whose counts should be updated
        """

        update_statuses = {}

        for aid, update_count in artist_ids_to_update.items():
            try:
                artist = session.query(Artist).filter_by(id=aid).first()
                artist.track_count -= update_count

                if artist.track_count == 0:
                    session.delete(artist)
                    update_statuses[aid] = DBUpdateType.DELETE
                else:
                    update_statuses[aid] = DBUpdateType.UPDATE

            except Exception as e:
                handle_error(e)
                update_statuses[aid] = DBUpdateType.FAILURE
                continue

        return update_statuses

    def sync_track_fields(self, tracks):
        """
        Sync track field values in DB and comments. Prefer DB values when available.

        :param tracks: Set of tracks for which to sync fields.
        """

        sync_statuses = {}
        update_msg = 'Updating %s field \'%s\' using %s value: %s -> %s'

        for track in tracks:
            track_pk = track.get_primary_key()
            log_buffer = []

            try:
                try:
                    comment = literal_eval(track.comment)
                except Exception:
                    log_buffer.append('Could not load comment')
                    comment = {}

                for field in COMMENT_FIELDS:
                    col_value = getattr(track, field, None)
                    comment_value = comment.get(field, None)

                    if col_value is None and comment_value is None:
                        log_buffer.append('%s is null in DB and comment')
                        continue

                    if col_value == comment_value:
                        continue

                    if col_value is not None:
                        log_buffer.append(update_msg % ('comment', field, 'column', str(comment_value), str(col_value)))
                        comment[field] = col_value

                    elif col_value is None and comment_value is not None:
                        log_buffer.append(update_msg % ('column', field, 'comment', str(None), str(comment_value)))
                        setattr(track, field, comment_value)

                if len(log_buffer) > 0:
                    progress_msg = 'Sync log for %s' % track_pk
                    banner = get_banner(progress_msg)
                    print('\n%s' % banner)
                    print(progress_msg)
                    print('%s' % banner)
                    print('\n'.join(log_buffer))

                    track.comment = str(comment)
                    sync_statuses[track.id] = DBUpdateType.UPDATE
                else:
                    sync_statuses[track.id] = DBUpdateType.NOOP

            except Exception as e:
                handle_error(e, 'Unexpected exception syncing fields for %s' % track_pk)
                sync_statuses[track.id] = DBUpdateType.FAILURE
                continue

        return sync_statuses

    @staticmethod
    def print_database_operation_statuses(prefix, updates):
        """
        Print status of attempted database operations.

        :param prefix: Message to print before update statuses
        :param updates: Mapping of unique identifier (primary key-like) to status of associated DB op
        """
        print('%s:\n%s\n' % (prefix, json.dumps({k: v.value for k, v in updates.items()}, indent=1)))
