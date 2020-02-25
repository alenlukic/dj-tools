from os.path import join

from src.definitions.common import CONFIG
from src.tools.data_management.formats.aiff_file import AudioFile
from src.utils.errors import handle_error
from src.utils.file_operations import get_audio_files


SOURCE_DIR = CONFIG['SANDBOX_SOURCE']
TARGET_DIR = CONFIG['SANDBOX_TARGET']


def test_mutagen():
    audio_files = get_audio_files(SOURCE_DIR)
    for af in audio_files:
        track_path = join(SOURCE_DIR, af)
        print('Processing %s' % track_path)

        try:
            mg_model = AudioFile(track_path)
            print(str(mg_model.read_tags()))
            print('\n')
        except Exception as e:
            handle_error(e)
            continue


if __name__ == '__main__':
    test_mutagen()
