import json
import multiprocessing
import sys

CONFIG = json.load(open('config/config.json', 'r'))
BACKUP_MUSIC_DIR = CONFIG['BACKUP_MUSIC_DIR']
LOG_LOCATION = CONFIG['LOG_LOCATION']
PROCESSED_MUSIC_DIR = CONFIG['PROCESSED_MUSIC_DIR']
TMP_MUSIC_DIR = CONFIG['TMP_MUSIC_DIR']

IS_UNIX = sys.platform.startswith('darwin') or sys.platform.startswith('linux')
NUM_CORES = multiprocessing.cpu_count()
