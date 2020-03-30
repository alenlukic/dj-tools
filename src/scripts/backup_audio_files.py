from datetime import datetime
from os import listdir, remove
from os.path import getmtime, isfile, join, splitext
from shutil import copyfile
from time import ctime

from src.definitions.common import *
from src.definitions.file_operations import *
from src.definitions.harmonic_mixing import TIMESTAMP_FORMAT
from src.utils.errors import handle_error
from src.utils import logging


def get_audio_file_name_map(input_dir):
    """
    Gets all the audio files in the given directory.

    :param input_dir: Directory to search for audio files.
    """
    name_map = {}

    for file_basename in listdir(input_dir):
        try:
            full_path = join(input_dir, file_basename)
            if isfile(full_path) and splitext(file_basename)[-1].lower() in AUDIO_TYPES:
                name_map[file_basename] = full_path
        except Exception as e:
            handle_error(e, 'Error occured while building audio file maps', logging.error)
            continue

    return name_map


def get_modified_date(file_path):
    """
    Get file's last modified date as numeric timestamp.

    :param file_path: Path to file.
    """
    return datetime.strptime(ctime(getmtime(file_path)), TIMESTAMP_FORMAT).timestamp()


def should_backup_file(source_file_path, backup_file_path):
    """
    Returns whether file should be backed up, based on modification date.

    :param source_file_path: Original file's path.
    :param backup_file_path: Backup file's path.
    """
    return get_modified_date(source_file_path) > get_modified_date(backup_file_path)


def run_backup():
    """ Backup new and modified files. """
    logging.info('Running music collection backup')

    source_map = get_audio_file_name_map(PROCESSED_MUSIC_DIR)
    backup_map = get_audio_file_name_map(BACKUP_MUSIC_DIR)

    # Add new tracks + update existing modified tracks
    upsert_map = {}
    for source_name, source_path in source_map.items():
        try:
            if source_name not in backup_map:
                upsert_map[source_path] = join(BACKUP_MUSIC_DIR, source_name)
            elif should_backup_file(source_path, backup_map[source_name]):
                upsert_map[source_path] = backup_map[source_name]
        except Exception as e:
            handle_error(e, 'Error occurred during upsert phase of audio files backup', logging.error)
            continue

    formatted_upserts = []
    for source, target in upsert_map.items():
        copyfile(source, target)
        formatted_upserts.append('%s -> %s' % (source, target))

    # Delete tracks no longer present in source directory
    formatted_deletions = []
    for backup_name, backup_path in backup_map.items():
        try:
            if backup_name not in source_map:
                remove(backup_path)
                formatted_deletions.append(backup_path)
        except Exception as e:
            handle_error(e, 'Error occurred during delete phase of audio files backup', logging.error)
            continue

    logging.info('Upserted tracks:')
    logging.info('\n'.join(formatted_upserts))
    logging.info('Deleted tracks:')
    logging.info('\n'.join(formatted_deletions))


if __name__ == '__main__':
    run_backup()
