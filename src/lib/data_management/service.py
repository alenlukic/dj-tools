from collections import defaultdict
import json
from shutil import copyfile
from sqlalchemy import or_

from src.db import database
from src.db.entities.artist import Artist
from src.db.entities.artist_track import ArtistTrack
from src.db.entities.feature_value import FeatureValue
from src.db.entities.tag_record import InitialTagRecord, PostMIKTagRecord, PostRekordboxTagRecord, FinalTagRecord
from src.db.entities.track import Track
from src.db.entities.transition_match import TransitionMatch
from src.definitions.common import PROCESSED_MUSIC_DIR
from src.lib.data_management.definitions.audio_file import AudioFile
from src.lib.error_management.service import handle
from src.utils.common import *
from src.utils.data_management import *
from src.utils.file_operations import delete_track_files, get_audio_files


def load_tracks(sesh=None):
    session = sesh or database.create_session()
    try:
        return session.query(Track).all()
    finally:
        if sesh is None:
            session.close()


def ingest_tracks(input_dir, target_dir=PROCESSED_MUSIC_DIR):
    session = database.create_session()

    try:
        input_files = get_audio_files(input_dir)
        tracks_to_save = {}

        for file_name in input_files:
            old_path = join(input_dir, file_name)

            try:
                track = AudioFile(file_name, input_dir)
            except Exception as e:
                handle(e, 'Couldn\'t read ID3 tags for %s' % old_path)
                continue

            new_path = join(target_dir, file_name)
            try:
                print('\nCopying:\t%s\nto:\t\t%s' % (old_path, new_path))
                copyfile(old_path, new_path)
            except Exception as e:
                handle(e, 'Couldn\'t copy %s to target directory' % new_path)
                continue

            tracks_to_save[file_name] = track

        insert_tracks(tracks_to_save)

    except Exception as e:
        handle(e)

    finally:
        session.close()


def insert_tracks(tracks):
    session = database.create_session()

    try:
        artist_updates = {}
        artist_track_updates = {}

        for file_name, track in tracks.items():
            # Create new row
            track_metadata = track.get_metadata()
            db_row = {k: v for k, v in track_metadata.items() if k in ALL_TRACK_DB_COLS}
            db_row[TrackDBCols.FILE_NAME.value] = file_name
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
            artist_updates_result = update_artists(session, comment)
            artist_updates[title] = artist_updates_result

            # Add artist tracks
            track_id = session.query(Track).filter_by(file_name=file_name).first().id
            successful_artist_ids = [a for a, s in artist_updates_result.items() if s != DBUpdateType.FAILURE.value]
            artist_track_updates[title] = insert_artist_tracks(session, track_id, successful_artist_ids)

        print_database_operation_statuses('Artist updates', artist_updates)
        print_database_operation_statuses('Artist track updates', artist_track_updates)

    except Exception as e:
        handle(e)
        session.rollback()
        raise e

    finally:
        session.close()


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


def delete_tracks(track_ids):
    session = database.create_session()

    try:
        # Delete entries from artist_track tables
        deletion_statuses, artist_ids_to_update = delete_artist_tracks(session, track_ids)
        print_database_operation_statuses('Artist track deletion statuses', deletion_statuses)

        # Update artist track count column
        update_statuses = update_artist_counts(session, artist_ids_to_update)
        print_database_operation_statuses('Artist track count update statuses', update_statuses)

        # Remove references from the ingestion pipeline tables
        tag_record_deletion_statuses = defaultdict(lambda: {})
        for track_id in track_ids:
            try:
                initial_tr = session.query(InitialTagRecord).filter_by(track_id=track_id).first()
                tag_record_deletion_statuses['Initial Record'][track_id] = _get_deletion_status(
                    session, initial_tr)
            except Exception as e:
                handle(e)
                tag_record_deletion_statuses['Initial Record'][track_id] = DBUpdateType.FAILURE.value
                continue

            try:
                post_mik_tr = session.query(PostMIKTagRecord).filter_by(track_id=track_id).first()
                tag_record_deletion_statuses['Post-MIK Record'][track_id] = _get_deletion_status(
                    session, post_mik_tr)
            except Exception as e:
                handle(e)
                tag_record_deletion_statuses['Post-MIK Record'][track_id] = DBUpdateType.FAILURE.value
                continue

            try:
                post_rb_tr = session.query(PostRekordboxTagRecord).filter_by(track_id=track_id).first()
                tag_record_deletion_statuses['Post-RB Record'][track_id] = _get_deletion_status(
                    session, post_rb_tr)
            except Exception as e:
                handle(e)
                tag_record_deletion_statuses['Post-RB Record'][track_id] = DBUpdateType.FAILURE.value
                continue

            try:
                final_tr = session.query(FinalTagRecord).filter_by(track_id=track_id).first()
                tag_record_deletion_statuses['Final Record'][track_id] = _get_deletion_status(
                    session, final_tr)
            except Exception as e:
                handle(e)
                tag_record_deletion_statuses['Final Record'][track_id] = DBUpdateType.FAILURE.value
                continue

        print_database_operation_statuses('Tag record update statuses', tag_record_deletion_statuses)

        # Delete transition match data
        tm_deletion_statuses = delete_transition_matches(session, track_ids)
        print_database_operation_statuses('Transition match deletion statuses', tm_deletion_statuses)

        # Delete feature value data
        fv_deletion_statuses = delete_feature_values(session, track_ids)
        print_database_operation_statuses('Feature value deletion statuses', fv_deletion_statuses)

        # Delete the tracks themselves
        track_deletion_statuses = {}
        for track_id in track_ids:
            try:
                track = session.query(Track).filter_by(id=track_id).first()
                session.delete(track)
                delete_track_files(track)
                track_deletion_statuses[track_id] = DBUpdateType.DELETE.value
            except Exception as e:
                handle(e)
                track_deletion_statuses[track_id] = DBUpdateType.FAILURE.value
                continue

        print_database_operation_statuses('Track deletion statuses', track_deletion_statuses)
        print('Committing session')
        session.commit()

    except Exception as e:
        handle(e)
        print('Session not committed')

    finally:
        session.close()


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


def delete_feature_values(session, track_ids):
    deletion_statuses = {}

    for track_id in track_ids:
        feature_values = session.query(FeatureValue).filter_by(track_id=track_id).first()

        try:
            deletion_statuses[str(track_id)] = _get_deletion_status(session, feature_values)
        except Exception as e:
            handle(e)
            deletion_statuses[str(track_id)] = DBUpdateType.FAILURE.value
            continue

    return deletion_statuses


def delete_transition_matches(session, track_ids):
    deletion_statuses = {}
    deletion_queue = set()

    for track_id in track_ids:
        matches = session.query(TransitionMatch)\
            .filter(or_(TransitionMatch.on_deck_id == track_id, TransitionMatch.candidate_id == track_id)).all()

        for match in matches:
            deletion_queue.add((match.on_deck_id, match.candidate_id))

    for (on_deck_id, candidate_id) in deletion_queue:
        match = session.query(TransitionMatch).filter_by(on_deck_id=on_deck_id, candidate_id=candidate_id).first()

        try:
            deletion_statuses[str((on_deck_id, candidate_id))] = _get_deletion_status(session, match)
        except Exception as e:
            handle(e)
            deletion_statuses[str((on_deck_id, candidate_id))] = DBUpdateType.FAILURE.value
            continue

    return deletion_statuses


def update_artist_counts(session, artist_ids_to_update):
    update_statuses = {}

    for aid, update_count in artist_ids_to_update.items():
        try:
            artist = session.query(Artist).filter_by(id=aid).first()
            artist.track_count -= update_count

            if artist.track_count == 0:
                update_statuses[aid] = _get_deletion_status(session, artist)
            else:
                update_statuses[aid] = DBUpdateType.UPDATE.value

        except Exception as e:
            handle(e)
            update_statuses[aid] = DBUpdateType.FAILURE.value
            continue

    return update_statuses


def sync_track_fields(tracks):
    sync_statuses = {}
    update_msg = 'Updating %s field \'%s\' using %s value: %s -> %s'

    for track in tracks:
        af = AudioFile(track.file_name)
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


def sync_track_tags(tracks):
    for track in tracks:
        af = AudioFile(track.file_name)
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


def print_database_operation_statuses(prefix, updates):
    banner = get_banner(prefix)
    print('\n%s' % banner)
    print(prefix)
    print(banner)
    print('%s' % json.dumps(updates, indent=1))


def _get_deletion_status(session, entity):
    return DBUpdateType.DELETE.value if session.safe_delete(entity) is True else DBUpdateType.NOOP.value

