from collections import defaultdict
import sys

from src.db import database
from src.db.entities.artist import Artist
from src.db.entities.artist_track import ArtistTrack
from src.db.entities.track import Track
from src.utils.errors import handle_error


def update_artist_counts(session, artist_ids_to_update):
    errors = False
    artist_ids = set(artist_ids_to_update.keys())

    try:
        for aid in artist_ids:
            artist = session.query(Artist).filter_by(id=aid).first()
            artist.track_count -= artist_ids_to_update[artist.id]
            if artist.track_count == 0:
                session.delete(artist)

    except Exception as e:
        handle_error(e)
        errors = True

    finally:
        if errors:
            session.rollback()

        return errors


def delete_artist_tracks(session, track_ids):
    errors = False
    artist_ids_to_update = defaultdict(int)

    try:
        for track_id in track_ids:
            artist_tracks = session.query(ArtistTrack).filter_by(track_id=track_id).all()
            for at in artist_tracks:
                artist_ids_to_update[at.artist_id] += 1
                session.delete(at)

    except Exception as e:
        handle_error(e)
        errors = True

    finally:
        if errors:
            session.rollback()

        return errors, artist_ids_to_update


def delete_tracks(track_ids):
    session = database.create_session()
    errors = False

    try:
        errors, artist_ids_to_update = delete_artist_tracks(session, track_ids)
        if errors:
            return

        errors = update_artist_counts(session, artist_ids_to_update)
        if errors:
            return

        for track_id in track_ids:
            track = session.query(Track).filter_by(id=track_id).first()
            session.delete(track)

    except Exception as e:
        handle_error(e)
        errors = True

    finally:
        if not errors:
            session.commit()

        session.close()


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Scripts requires IDs of tracks to delete')
        sys.exit(1)

    track_ids_to_delete = set([int(x) for x in sys.argv[1:]])
    delete_tracks(track_ids_to_delete)
