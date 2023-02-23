from src.db import database
from src.db.entities.artist import Artist
from src.db.entities.artist_track import ArtistTrack
from src.db.entities.track import Track
from src.definitions.data_management import ArtistFields, TrackDBCols
from src.lib.data_management.definitions.audio_file import AudioFile
from src.utils.common import is_empty
from src.utils.data_management import load_comment
from src.lib.error_management.service import handle


def find_artist_disparities():
    session = database.create_session()

    try:
        for track in session.query(Track).all():
            # Generate comment
            track_comment = track.comment
            if track_comment is None:
                try:
                    track_model = AudioFile(track.file_name)
                    track_metadata = track_model.get_metadata()
                    track_comment = track_metadata.get(TrackDBCols.COMMENT.value, '{}')
                except Exception:
                    track_comment = '{}'
            track_comment = load_comment(track_comment)

            # Extract artist names from comment
            artist_str = track_comment.get(ArtistFields.ARTISTS.value, '')
            remixer_str = track_comment.get(ArtistFields.REMIXERS.value, '')
            comment_artists = set([ca for ca in [a.strip() for a in artist_str.split(',')] +
                                   [r.strip() for r in remixer_str.split(',')] if not is_empty(ca)])

            # Get artist names in DB
            artist_tracks = session.query(ArtistTrack).filter_by(track_id=track.id).all()
            artist_rows = set()
            for artist_track in artist_tracks:
                artist_row = session.query(Artist).filter_by(id=artist_track.artist_id).first()
                artist_rows.add(artist_row.name)

            # Find diff between comment and DB entries
            if len(comment_artists.difference(artist_rows)) > 0:
                print('Artist disparity for track %s' % track.title)
                print('Comment artist entry: %s' % str(comment_artists))
                print('DB artist entries: %s' % str(artist_rows))
                print('-------\n')

    except Exception as e:
        handle(e, 'Top-level exception occurred while syncing track fields')
        session.rollback()
    finally:
        session.close()


if __name__ == '__main__':
    find_artist_disparities()
