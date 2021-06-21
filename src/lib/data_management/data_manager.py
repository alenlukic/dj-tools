from collections import defaultdict

from src.db import database
from src.db.entities.artist import Artist
from src.db.entities.artist_track import ArtistTrack
from src.db.entities.tag_record import InitialTagRecord, PostMIKTagRecord, PostRekordboxTagRecord, FinalTagRecord
from src.db.entities.track import Track
from src.definitions.common import PROCESSED_MUSIC_DIR
from src.utils.common import *
from src.lib.data_management.audio_file import AudioFile
from src.utils.data_management import *
from src.lib.error_management.reporting_handler import handle
from src.utils.file_operations import get_audio_files


class DataManager:
    """ Encapsulates track database management utilities. """

    @staticmethod
    def load_tracks():
        session = database.create_session()
        try:
            return session.query(Track).all()
        finally:
            session.close()

    @staticmethod
    def ingest_tracks(input_dir, target_dir=PROCESSED_MUSIC_DIR):
        """ Ingest new tracks - extract tags, format fields, and create track table entries. """

        session = database.create_session()

        try:
            input_files = get_audio_files(input_dir)
            tracks_to_save = {}

            for f in input_files:
                old_path = join(input_dir, f)

                # Load track and read ID3 tags
                try:
                    track = AudioFile(old_path)
                except Exception as e:
                    handle(e, 'Couldn\'t read ID3 tags for %s' % old_path)
                    continue

                # Verify requisite ID3 tags exist
                id3_data = track.get_tags()
                if not REQUIRED_ID3_TAGS.issubset(set(id3_data.keys())):
                    print('Can\'t ingest %s due to missing requisite ID3 tags' % old_path)
                    continue

                # Copy to target directory
                new_path = join(target_dir, f)
                try:
                    print('\nCopying:\t%s\nto:\t\t%s' % (old_path, new_path))
                    copyfile(old_path, new_path)
                except Exception as e:
                    handle(e, 'Couldn\'t copy %s to target directory' % new_path)
                    continue

                tracks_to_save[new_path] = track

            # Update database
            DataManager.insert_tracks(tracks_to_save)

        except Exception as e:
            handle(e)

        finally:
            session.close()

    @staticmethod
    def insert_tracks(tracks):
        session = database.create_session()

        try:
            artist_updates = {}
            artist_track_updates = {}

            for new_track_path, track in tracks.items():
                # Create new row
                track_metadata = track.get_metadata()
                db_row = {k: v for k, v in track_metadata.items() if k in ALL_TRACK_DB_COLS}
                db_row[TrackDBCols.FILE_PATH.value] = new_track_path
                title = extract_unformatted_title(db_row[TrackDBCols.TITLE.value])
                db_row[TrackDBCols.TITLE.value] = title

                try:
                    # Persist row to DB
                    session.add(Track(**db_row))
                    session.commit()

                except Exception as e:
                    handle(e)
                    session.rollback()
                    continue

                # Update artists
                comment = load_comment(track_metadata.get(TrackDBCols.COMMENT.value), '{}')
                artist_updates_result = DataManager.update_artists(session, comment)
                artist_updates[title] = artist_updates_result

                # Add artist tracks
                track_id = session.query(Track).filter_by(file_path=new_track_path).first().id
                successful_artist_ids = [a for a, s in artist_updates_result.items() if s != DBUpdateType.FAILURE.value]
                artist_track_updates[title] = DataManager.insert_artist_tracks(session, track_id, successful_artist_ids)

            DataManager.print_database_operation_statuses('Artist updates', artist_updates)
            DataManager.print_database_operation_statuses('Artist track updates', artist_track_updates)

        except Exception as e:
            handle(e)
            session.rollback()
            raise e

        finally:
            session.close()

    @staticmethod
    def update_artists(session, track_comment_metadata):
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
                    artist_updates[artist_row.id] = DBUpdateType.INSERT.value
                except Exception as e:
                    handle(e)
                    artist_updates[a] = DBUpdateType.FAILURE.value
                    continue
            else:
                artist_row.track_count += 1
                artist_updates[artist_row.id] = DBUpdateType.UPDATE.value

        return artist_updates

    @staticmethod
    def insert_artist_tracks(session, track_id, artist_ids):
        artist_track_updates = {}
        for artist_id in artist_ids:
            try:
                session.add(ArtistTrack(**{'track_id': track_id, 'artist_id': artist_id}))
                session.commit()

                artist_track_row = session.query(ArtistTrack).filter_by(artist_id=artist_id).first()
                artist_track_updates[artist_track_row.id] = DBUpdateType.INSERT.value
            except Exception as e:
                handle(e)
                artist_track_updates[artist_id] = DBUpdateType.FAILURE.value
                continue

        return artist_track_updates

    @staticmethod
    def delete_tracks(track_ids):
        session = database.create_session()

        try:
            # Delete entries from artist_track tables first
            deletion_statuses, artist_ids_to_update = DataManager.delete_artist_tracks(session, track_ids)
            DataManager.print_database_operation_statuses('Artist track deletion statuses', deletion_statuses)

            # Then, update artist track count column
            update_statuses = DataManager.update_artist_counts(session, artist_ids_to_update)
            DataManager.print_database_operation_statuses('Artist track count update statuses', update_statuses)

            # Then, remove references from the ingestion pipeline tables
            tag_record_deletion_statuses = defaultdict(lambda: {})
            for track_id in track_ids:
                try:
                    initial_tr = session.query(InitialTagRecord).filter_by(track_id=track_id).first()
                    session.delete(initial_tr)
                    tag_record_deletion_statuses['Initial Record'][track_id] = DBUpdateType.DELETE.value
                except Exception as e:
                    handle(e)
                    tag_record_deletion_statuses['Initial Record'][track_id] = DBUpdateType.FAILURE.value
                    continue

                try:
                    post_mik_tr = session.query(PostMIKTagRecord).filter_by(track_id=track_id).first()
                    session.delete(post_mik_tr)
                    tag_record_deletion_statuses['Post-MIK Record'][track_id] = DBUpdateType.DELETE.value
                except Exception as e:
                    handle(e)
                    tag_record_deletion_statuses['Post-MIK Record'][track_id] = DBUpdateType.FAILURE.value
                    continue

                try:
                    post_rb_tr = session.query(PostRekordboxTagRecord).filter_by(track_id=track_id).first()
                    session.delete(post_rb_tr)
                    tag_record_deletion_statuses['Post-RB Record'][track_id] = DBUpdateType.DELETE.value
                except Exception as e:
                    handle(e)
                    tag_record_deletion_statuses['Post-RB Record'][track_id] = DBUpdateType.FAILURE.value
                    continue

                try:
                    final_tr = session.query(FinalTagRecord).filter_by(track_id=track_id).first()
                    session.delete(final_tr)
                    tag_record_deletion_statuses['Final Record'][track_id] = DBUpdateType.DELETE.value
                except Exception as e:
                    handle(e)
                    tag_record_deletion_statuses['Final Record'][track_id] = DBUpdateType.FAILURE.value
                    continue

            DataManager.print_database_operation_statuses('Tag record update statuses', tag_record_deletion_statuses)

            # Finally, delete the tracks themselves
            track_deletion_statuses = {}
            for track_id in track_ids:
                try:
                    track = session.query(Track).filter_by(id=track_id).first()
                    session.delete(track)
                    track_deletion_statuses[track_id] = DBUpdateType.DELETE.value
                except Exception as e:
                    handle(e)
                    track_deletion_statuses[track_id] = DBUpdateType.FAILURE.value
                    continue

            DataManager.print_database_operation_statuses('Track deletion statuses', track_deletion_statuses)

            print('Committing session')
            session.commit()

        except Exception as e:
            handle(e)
            print('Session not committed')

        finally:
            session.close()

    @staticmethod
    def delete_artist_tracks(session, track_ids):
        deletion_statuses = {}
        artist_ids_to_update = defaultdict(int)

        for track_id in track_ids:
            artist_tracks = session.query(ArtistTrack).filter_by(track_id=track_id).all()

            for at in artist_tracks:
                artist_id = at.artist_id
                try:
                    session.delete(at)
                    artist_ids_to_update[artist_id] += 1
                    deletion_statuses[str((track_id, artist_id))] = DBUpdateType.DELETE.value

                except Exception as e:
                    handle(e)
                    deletion_statuses[str((track_id, artist_id))] = DBUpdateType.FAILURE.value
                    continue

        return deletion_statuses, artist_ids_to_update

    @staticmethod
    def update_artist_counts(session, artist_ids_to_update):
        update_statuses = {}

        for aid, update_count in artist_ids_to_update.items():
            try:
                artist = session.query(Artist).filter_by(id=aid).first()
                artist.track_count -= update_count

                if artist.track_count == 0:
                    session.delete(artist)
                    update_statuses[aid] = DBUpdateType.DELETE.value
                else:
                    update_statuses[aid] = DBUpdateType.UPDATE.value

            except Exception as e:
                handle(e)
                update_statuses[aid] = DBUpdateType.FAILURE.value
                continue

        return update_statuses

    @staticmethod
    def sync_track_fields(tracks):
        sync_statuses = {}
        update_msg = 'Updating %s field \'%s\' using %s value: %s -> %s'

        for track in tracks:
            af = AudioFile(track.file_path)
            track_pk = track.get_id_title_identifier()
            log_buffer = []

            try:
                comment = load_comment(track.comment, '{}')
                tags_to_update = {}

                for field in COMMENT_FIELDS:
                    col_value = normalize_tag_text(getattr(track, field, None))
                    comment_value = normalize_tag_text(comment.get(field, None))
                    tag_value = af.get_tag(METADATA_KEY_TO_ID3.get(field, None))

                    if (col_value is None and comment_value is None) and tag_value is not None:
                        setattr(track, field, tag_value)
                        col_value = tag_value

                    if field == TrackDBCols.BPM.value or field == TrackDBCols.ENERGY.value:
                        col_value = None if col_value is None else int(col_value)
                        comment_value = None if comment_value is None else int(comment_value)

                    # Skip any fields without values in either DB or comment
                    if col_value is None and comment_value is None:
                        log_buffer.append('%s is null in DB and comment' % field)
                        continue

                    # Dedupe titles
                    if field == TrackDBCols.TITLE.value:
                        updated_col_title = dedupe_title(col_value)
                        updated_comment_title = dedupe_title(comment_value)
                        title = updated_col_title or updated_comment_title

                        if title != col_value or title != comment_value:
                            log_buffer.append(
                                update_msg % ('comment', field, 'deduped', str(comment_value), str(title)))
                            log_buffer.append(update_msg % ('column', field, 'deduped', str(col_value), str(title)))

                            comment[field] = title
                            setattr(track, field, title)
                            tags_to_update[field] = title

                            continue

                    if col_value == comment_value:
                        continue

                    # Prefer column value over comment value
                    if col_value is not None:
                        log_buffer.append(update_msg % ('comment', field, 'column', str(comment_value), str(col_value)))
                        comment[field] = col_value
                        tags_to_update[field] = col_value

                    elif col_value is None and comment_value is not None:
                        log_buffer.append(update_msg % ('column', field, 'comment', str(None), str(comment_value)))
                        setattr(track, field, comment_value)
                        tags_to_update[field] = comment_value

                if len(log_buffer) > 0:
                    progress_msg = 'Sync log for %s' % track_pk
                    banner = get_banner(progress_msg)
                    print('\n%s' % banner)
                    print(progress_msg)
                    print('%s' % banner)
                    print('\n'.join(log_buffer))

                    tags_to_update = {k: v for k, v in tags_to_update.items() if k in ID3_COMMENT_FIELDS}
                    af.write_tags(tags_to_update)
                    track.comment = str(comment)

                    sync_statuses[track.id] = DBUpdateType.UPDATE.value
                else:
                    sync_statuses[track.id] = DBUpdateType.NOOP.value

            except Exception as e:
                handle(e, 'Unexpected exception syncing fields for %s' % track_pk)
                sync_statuses[track.id] = DBUpdateType.FAILURE.value

                continue

        return sync_statuses

    @staticmethod
    def sync_track_tags(tracks):
        for track in tracks:
            af = AudioFile(track.file_path)
            track_pk = track.get_id_title_identifier()

            try:
                comment = load_comment(track.comment, '{}')
                tags_to_update = {}

                for field in ID3_COMMENT_FIELDS:
                    id3_tag = METADATA_KEY_TO_ID3.get(field)

                    col_value = normalize_tag_text(getattr(track, field, None))
                    comment_value = normalize_tag_text(comment.get(field, None))
                    old_value = af.get_tag(id3_tag)
                    new_value = col_value or comment_value

                    if str(new_value) != str(old_value):
                        tags_to_update[field] = new_value

                if len(tags_to_update) > 0:
                    af.write_tags(tags_to_update)

                    progress_msg = 'Tags saved for %s' % track_pk
                    banner = get_banner(progress_msg)
                    print('\n%s' % banner)
                    print(progress_msg)
                    print('%s' % banner)
                    print('\n'.join(['%s: %s' % (k, v) for k, v in tags_to_update.items()]))

            except Exception as e:
                handle(e, 'Unexpected exception syncing tags for %s' % track_pk)
                continue

    @staticmethod
    def print_database_operation_statuses(prefix, updates):
        banner = get_banner(prefix)
        print('\n%s' % banner)
        print(prefix)
        print(banner)
        print('%s' % json.dumps(updates, indent=1))
