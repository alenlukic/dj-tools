import json


CONFIG = json.load(open('config.json', 'r'))
DATA_DIR = CONFIG['DATA_DIR']
PROCESSED_MUSIC_DIR = CONFIG['PROCESSED_MUSIC_DIR']
TMP_MUSIC_DIR = CONFIG['TMP_MUSIC_DIR']

AUDIO_TYPES = {'mp3', 'wav', 'flac', 'ogg', 'aif', 'aiff', 'm3u'}
LOSSLESS = {'wav', 'flac', 'aif', 'aiff'}
