import json


CONFIG = json.load(open('config.json', 'r'))
BACKUP_MUSIC_DIR = CONFIG['BACKUP_MUSIC_DIR']
LOG_LOCATION = CONFIG['LOG_LOCATION']
PROCESSED_MUSIC_DIR = CONFIG['PROCESSED_MUSIC_DIR']
TMP_MUSIC_DIR = CONFIG['TMP_MUSIC_DIR']
