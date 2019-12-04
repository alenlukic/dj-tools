import json


CONFIG = json.load(open('config.json', 'r'))
PROCESSED_MUSIC_DIR = CONFIG['PROCESSED_MUSIC_DIR']
TMP_MUSIC_DIR = CONFIG['TMP_MUSIC_DIR']
