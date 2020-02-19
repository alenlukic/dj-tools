import logging
import os
from os.path import basename
from shutil import copyfile
import sys

from src.db import database
from src.db.entities.artist import Artist as ArtistEntity
from src.db.entities.artist_track import ArtistTrack as ArtistTrackEntity
from src.db.entities.track import columns, Track as TrackEntity
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

    def __init__(self, audio_dir=PROCESSED_MUSIC_DIR):
        """
        Initializes class with music directory info.

        :param audio_dir - directory containing processed (e.g. renamed) tracks.
        """

        self.audio_dir = audio_dir
        self.database = database
        self.audio_files = get_audio_files(self.audio_dir)

    def load_tracks(self):
        """ Loads tracks from the database into memory. """

        session = self.database.create_session()
        tracks = session.query(TrackEntity).all()
        self.database.close_sessions([session])

        return tracks

    def generate_track_metadata(self, track_path):
        """
        Generate formatted metadata for a track.

        :param track_path - Qualified path to the track.
        """

        track = Track(track_path)
        tag_dict = track.get_tag_dict()
        id3_data = track.get_id3_data()
        try:
            return (self._generate_metadata_heuristically(track) if is_empty(tag_dict) else
                    track.generate_metadata_from_id3()), id3_data
        except Exception as e:
            print('Error while generating metadata for track %s: %s' % (track_path, e))
            return None, None

    def write_track_metadata(self, track_path):
        """
        Generate formatted metadata for a track and write it to its comment field.

        :param track_path - Qualified path to the track.
        """

        try:
            track_metadata, id3_data = self.generate_track_metadata(track_path)
            if track_metadata is None:
                return None
            track_metadata.write_tags(track_path, id3_data)
            return track_metadata
        except Exception as e:
            print('Error while writing metadata for track %s: %s' % (track_path, e))
            return None

    def insert_tracks(self, tracks):
        """
        Inserts new track rows to the database.

        :param tracks - dictionary mapping track name to its metadata
        """
        session = self.database.create_session()

        try:
            for track_name, track_metadata in tracks.items():
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

        except Exception as e:
            session.rollback()
            raise e

        finally:
            session.commit()
            session.close()

    def upsert_tracks(self, tracks):
        """
        Upserts new metadata to existing track rows.

        :param tracks - dictionary mapping track name to its metadata
        """

        session = self.database.create_session()
        columns_to_update = list(filter(lambda c: not (c == 'id' or c == 'file_path' or c == 'date_added'), columns))

        try:
            for track_name, track_metadata in tracks.items():
                # Get existing row
                existing_track = session.query(TrackEntity).filter_by(file_path=track_name).first()
                if existing_track is None:
                    raise Exception('Could not find track associated with file path %s in DB' % track_name)

                # Update row with new metadata values
                for col in columns_to_update:
                    new_val = getattr(track_metadata, col)
                    if new_val is not None:
                        setattr(existing_track, col, new_val)

        except Exception as e:
            session.rollback()
            raise e

        finally:
            session.commit()
            session.close()

    def update_database(self, tracks, upsert):
        """
        Updates the database with tracks' info.

        :param tracks - dictionary mapping track name to its metadata
        :param upsert - indicates whether to update existing tracks
        """
        self.upsert_tracks(tracks) if upsert else self.insert_tracks(tracks)

    def rename_songs(self, input_dir=TMP_MUSIC_DIR, target_dir=None, upsert=False):
        """
        Standardizes song names and copy them to library.

        :param input_dir - directory containing audio files to rename.
        :param target_dir - directory where updated audio files should be saved
        :param upsert - if True, tracks are upserted into the DB and original base names are retained
        """

        target_dir = target_dir or self.audio_dir
        input_files = get_audio_files(input_dir)
        tracks_to_save = {}

        for f in input_files:
            old_name = join(input_dir, f)
            old_base_name = basename(old_name)
            file_ext = old_name.split('.')[-1].strip()
            track = Track(old_name)
            id3_data = track.get_tag_dict()

            if is_empty(id3_data) or not REQUIRED_ID3_TAGS.issubset(set(id3_data.keys())):
                # All non-mp3 audio files (and some mp3 files) won't have requisite ID3 metadata for automatic renaming.
                # User will need to enter new name manually.
                print('Can\'t automatically rename this track: %s' % old_base_name)
                print('Enter the new name here:')
                new_name = join(target_dir, input())
                copyfile(old_name, new_name)
            else:
                # Generate formatted track name
                formatted_name = ('.'.join([x.strip() for x in old_base_name.split('.')[0:-1]]) if upsert
                                  else track.format_track_name())
                new_name = (join(target_dir, old_base_name) if upsert
                            else ''.join([join(target_dir, formatted_name).strip(), '.', file_ext]))

                # Copy track to user audio directory
                copyfile(old_name, new_name)
                # new_track = load(new_name).tag
                # new_track.title = formatted_name
                # new_track.save()

                # Create metadata
                metadata = self.write_track_metadata(new_name)
                tracks_to_save[new_name] = metadata

            new_base_name = basename(new_name)
            try:
                print('\nRenaming:\t%s\nto:\t\t%s' % (old_base_name, new_base_name))
            except Exception as e:
                print('Could not rename %s to %s (exception: %s)' % (old_base_name, new_base_name, str(e)))

        # Update database
        self.update_database(tracks_to_save, upsert)

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
        artists = split_basename[0].split(' and ' if ' and ' in split_basename[0] else ' & ')
        artists.extend([] if featured is None else [featured])

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
