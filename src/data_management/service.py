from collections import defaultdict
import json
from os.path import join
from shutil import copyfile

from src.data_management.mapping_registry import MappingRegistry

from src.db import database
from src.models.artist import Artist
from src.models.artist_track import ArtistTrack
from src.models.tag_record import (
    InitialTagRecord,
    PostMIKTagRecord,
    PostRekordboxTagRecord,
    FinalTagRecord,
)
from src.models.track import Track
from src.config import PROCESSED_MUSIC_DIR
from src.data_management.config import (
    ALL_TRACK_DB_COLS,
    ArtistFields,
    COMMENT_FIELDS,
    DBUpdateType,
    ID3_COMMENT_FIELDS,
    METADATA_KEY_TO_ID3,
    TrackDBCols,
)
from src.data_management.audio_file import AudioFile
from src.errors import handle
from src.utils.common import get_banner
from src.data_management.utils import (
    dedupe_title,
    extract_unformatted_title,
    load_comment,
    normalize_tag_text,
    split_artist_string,
)
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
    MappingRegistry.load(session)

    try:
        input_files = get_audio_files(input_dir)
        tracks_to_save = {}

        for file_name in input_files:
            old_path = join(input_dir, file_name)

            try:
                track = AudioFile(file_name, input_dir)
            except Exception as e:
                handle(e, "Couldn't read ID3 tags for %s" % old_path)
                continue

            new_path = join(target_dir, file_name)
            try:
                print("\nCopying:\t%s\nto:\t\t%s" % (old_path, new_path))
                copyfile(old_path, new_path)
            except Exception as e:
                handle(e, "Couldn't copy %s to target directory" % new_path)
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
            comment = load_comment(track_metadata.get(TrackDBCols.COMMENT.value), "{}")
            artist_updates_result = update_artists(session, comment)
            artist_updates[title] = artist_updates_result

            # Add artist tracks
            track_id = session.query(Track).filter_by(file_name=file_name).first().id
            successful_artist_ids = [
                a
                for a, s in artist_updates_result.items()
                if s != DBUpdateType.FAILURE.value
            ]
            artist_track_updates[title] = insert_artist_tracks(
                session, track_id, successful_artist_ids
            )

        print_database_operation_statuses("Artist updates", artist_updates)
        print_database_operation_statuses("Artist track updates", artist_track_updates)

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
                session.add(Artist(**{"name": a, "track_count": 1}))
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
            session.add(ArtistTrack(**{"track_id": track_id, "artist_id": artist_id}))
            session.commit()

            artist_track_row = (
                session.query(ArtistTrack).filter_by(artist_id=artist_id).first()
            )
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
        deletion_statuses, artist_ids_to_update = delete_artist_tracks(
            session, track_ids
        )
        print_database_operation_statuses(
            "Artist track deletion statuses", deletion_statuses
        )

        # Update artist track count column
        update_statuses = update_artist_counts(session, artist_ids_to_update)
        print_database_operation_statuses(
            "Artist track count update statuses", update_statuses
        )

        # Remove references from the ingestion pipeline tables
        tag_record_deletion_statuses = defaultdict(lambda: {})
        for track_id in track_ids:
            try:
                initial_tr = (
                    session.query(InitialTagRecord).filter_by(track_id=track_id).first()
                )
                tag_record_deletion_statuses["Initial Record"][track_id] = (
                    _get_deletion_status(session, initial_tr)
                )
            except Exception as e:
                handle(e)
                tag_record_deletion_statuses["Initial Record"][track_id] = (
                    DBUpdateType.FAILURE.value
                )
                continue

            try:
                post_mik_tr = (
                    session.query(PostMIKTagRecord).filter_by(track_id=track_id).first()
                )
                tag_record_deletion_statuses["Post-MIK Record"][track_id] = (
                    _get_deletion_status(session, post_mik_tr)
                )
            except Exception as e:
                handle(e)
                tag_record_deletion_statuses["Post-MIK Record"][track_id] = (
                    DBUpdateType.FAILURE.value
                )
                continue

            try:
                post_rb_tr = (
                    session.query(PostRekordboxTagRecord)
                    .filter_by(track_id=track_id)
                    .first()
                )
                tag_record_deletion_statuses["Post-RB Record"][track_id] = (
                    _get_deletion_status(session, post_rb_tr)
                )
            except Exception as e:
                handle(e)
                tag_record_deletion_statuses["Post-RB Record"][track_id] = (
                    DBUpdateType.FAILURE.value
                )
                continue

            try:
                final_tr = (
                    session.query(FinalTagRecord).filter_by(track_id=track_id).first()
                )
                tag_record_deletion_statuses["Final Record"][track_id] = (
                    _get_deletion_status(session, final_tr)
                )
            except Exception as e:
                handle(e)
                tag_record_deletion_statuses["Final Record"][track_id] = (
                    DBUpdateType.FAILURE.value
                )
                continue

        print_database_operation_statuses(
            "Tag record update statuses", tag_record_deletion_statuses
        )

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

        print_database_operation_statuses(
            "Track deletion statuses", track_deletion_statuses
        )

        session.commit()

    except Exception as e:
        handle(e)
        session.rollback()

    finally:
        session.close()


def delete_artist_tracks(session, track_ids):
    artist_ids_to_update = {}
    deletion_statuses = {}

    for track_id in track_ids:
        try:
            artist_tracks = (
                session.query(ArtistTrack).filter_by(track_id=track_id).all()
            )
            for at in artist_tracks:
                artist_ids_to_update[at.artist_id] = (
                    artist_ids_to_update.get(at.artist_id, 0) + 1
                )
                deletion_statuses[at.id] = _get_deletion_status(session, at)
        except Exception as e:
            handle(e)
            deletion_statuses[track_id] = DBUpdateType.FAILURE.value
            continue

    return deletion_statuses, artist_ids_to_update


def update_artist_counts(session, artist_id_decrement_map):
    update_statuses = {}

    for artist_id, decrement in artist_id_decrement_map.items():
        try:
            artist = session.query(Artist).filter_by(id=artist_id).first()
            if artist is not None:
                artist.track_count -= decrement
                update_statuses[artist_id] = DBUpdateType.UPDATE.value
        except Exception as e:
            handle(e)
            update_statuses[artist_id] = DBUpdateType.FAILURE.value
            continue

    return update_statuses


def sync_track_fields(tracks):
    for track in tracks:
        try:
            audio_file = AudioFile(track.file_name)
            metadata = audio_file.get_metadata()
            for col, val in metadata.items():
                if col != TrackDBCols.COMMENT.value:
                    setattr(track, col, val)
        except Exception as e:
            handle(e, "Exception occurred syncing fields for %s" % track.file_name)
            continue


def sync_track_tags(tracks):
    for track in tracks:
        try:
            audio_file = AudioFile(track.file_name)
            audio_file.write_tags()
        except Exception as e:
            handle(e, "Exception occurred syncing tags for %s" % track.file_name)
            continue


def _get_deletion_status(session, entity):
    if entity is None:
        return DBUpdateType.NOOP.value

    try:
        session.delete(entity)
        return DBUpdateType.DELETE.value
    except Exception as e:
        handle(e)
        return DBUpdateType.FAILURE.value


def print_database_operation_statuses(operation_name, statuses):
    print("\n%s:\n" % operation_name)
    for k, v in statuses.items():
        print("%s: %s" % (str(k), str(v)))
