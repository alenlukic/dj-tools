from os.path import join

from src.db import database
from src.definitions.common import CONFIG
from src.tools.data_management.data_manager import DataManager
from src.tools.data_management.audio_file import AudioFile
from src.utils.errors import handle_error
from src.utils.file_operations import get_audio_files


SOURCE_DIR = CONFIG['SANDBOX_SOURCE']
TARGET_DIR = CONFIG['SANDBOX_TARGET']


def test_mutagen():
    database.enable_dry_run()
    dm = DataManager()

    audio_files = get_audio_files(SOURCE_DIR)
    for af in audio_files:
        track_path = join(SOURCE_DIR, af)
        print('\nProcessing %s\n' % track_path)

        try:
            mg_model = AudioFile(track_path)
            print('ID3 tags:\n' + str(mg_model.read_tags()))
            print('\n')
        except Exception as e:
            handle_error(e)
            continue

    try:
        dm.rename_songs(SOURCE_DIR, TARGET_DIR)
    except Exception as e:
        handle_error(e)
    finally:
        database.disable_dry_run()
        database.close_all_sessions()







if __name__ == '__main__':
    test_mutagen()
