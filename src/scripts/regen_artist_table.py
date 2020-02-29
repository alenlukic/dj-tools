from ast import literal_eval

from src.db import database
from src.db.entities.artist import Artist
from src.db.entities.artist_track import ArtistTrack
from src.db.entities.track import Track
from src.definitions.data_management import *
from src.tools.data_management.audio_file import AudioFile
from src.utils.common import print_progress
from src.utils.errors import handle_error
from src.utils.data_management import split_artist_string


def delete_artist_track_entries():
    session = database.create_session()
    errors = False

    try:
        artist_tracks = session.query(ArtistTrack).all()
        n = len(artist_tracks)
        for i, at in enumerate(artist_tracks):
            try:
                session.query(ArtistTrack).filter_by(id=at.id).delete()
                print_progress('artist track deletions', i, n)
            except Exception as e:
                errors = True
                handle_error(e)
                continue
    finally:
        session.close(True, errors)
        return errors


def delete_artist_entries():
    session = database.create_session()
    errors = False

    try:
        artists = session.query(Artist).all()
        n = len(artists)
        for i, artist in enumerate(artists):
            try:
                session.query(Artist).filter_by(id=artist.id).delete()
                print_progress('artist deletions', i, n)
            except Exception as e:
                errors = True
                handle_error(e)
                continue
    finally:
        session.close(True, errors)
        return errors


def regen_artist_table():
    if delete_artist_track_entries() or delete_artist_entries():
        return False

    session = database.create_session()
    errors = False
    try:
        tracks = session.query(Track).all()
        n = len(tracks)
        for i, track in enumerate(tracks):
            try:
                try:
                    comment = literal_eval(track.comment)
                except Exception:
                    comment = {}

                artists = comment.get(ArtistFields.ARTISTS.value)
                remixers = comment.get(ArtistFields.REMIXERS.value)
                if artists is None or remixers is None:
                    track_model = AudioFile(track.file_path)
                    if artists is None:
                        artists = track_model.get_tag(ID3Tag.ARTIST)
                    if remixers is None:
                        remixers = track_model.get_tag(ID3Tag.REMIXER)

                all_artists = split_artist_string(artists) + split_artist_string(remixers)
                for a in set(all_artists):
                    artist_row = session.query(Artist).filter_by(name=a).first()
                    if artist_row is None:
                        session.add(Artist(**{'name': a, 'track_count': 1}))
                    else:
                        artist_row.track_count += 1

                print_progress('track artist regenrations', i, n)

            except Exception as e:
                handle_error(e)
                errors = True
                continue

    finally:
        session.close(True, errors)
        return errors


def regen_artist_track_table():
    session = database.create_session()
    errors = False

    try:
        tracks = session.query(Track).all()
        n = len(tracks)
        for i, track in enumerate(tracks):
            try:
                track_id = track.id
                try:
                    comment = literal_eval(track.comment)
                except Exception:
                    comment = {}

                artists = comment.get(ArtistFields.ARTISTS.value)
                remixers = comment.get(ArtistFields.REMIXERS.value)
                if artists is None or remixers is None:
                    track_model = AudioFile(track.file_path)
                    if artists is None:
                        artists = track_model.get_tag(ID3Tag.ARTIST)
                    if remixers is None:
                        remixers = track_model.get_tag(ID3Tag.REMIXER)

                all_artists = split_artist_string(artists) + split_artist_string(remixers)
                for a in set(all_artists):
                    artist_row = session.query(Artist).filter_by(name=a).first()
                    session.add(ArtistTrack(**{'track_id': track_id, 'artist_id': artist_row.id}))

                print_progress('track artist_track regenrations', i, n)

            except Exception as e:
                handle_error(e)
                errors = True
                continue

    finally:
        session.close(True, errors)
        return errors


if __name__ == '__main__':
    artist_regen_errors = regen_artist_table()
    if not artist_regen_errors:
        regen_artist_track_table()
