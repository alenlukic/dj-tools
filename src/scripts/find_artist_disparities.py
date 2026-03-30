from src.db import database
from src.models.artist import Artist
from src.models.artist_track import ArtistTrack
from src.models.track import Track
from src.data_management.config import ArtistFields
from src.utils.common import is_empty
from src.data_management.utils import load_comment
from src.errors import handle


def find_artist_disparities():
    session = database.create_session()

    try:
        tracks = session.query(Track).all()
        for track in tracks:
            comment = track.comment
            if not comment:
                continue

            track_comment = load_comment(comment)
            artists_str = track_comment.get(ArtistFields.ARTISTS.value, "")
            if is_empty(artists_str):
                continue

            db_artist_tracks = session.query(ArtistTrack).filter_by(track_id=track.id).all()
            db_artist_ids = {at.artist_id for at in db_artist_tracks}
            db_artists = {
                session.query(Artist).filter_by(id=aid).first().name
                for aid in db_artist_ids
                if session.query(Artist).filter_by(id=aid).first() is not None
            }

            comment_artists = set([a.strip() for a in artists_str.split(",") if a.strip()])
            if db_artists != comment_artists:
                print(
                    "Disparity for track %d (%s): DB=%s, comment=%s"
                    % (track.id, track.title, db_artists, comment_artists)
                )

    except Exception as e:
        handle(e)

    finally:
        session.close()


if __name__ == "__main__":
    find_artist_disparities()
