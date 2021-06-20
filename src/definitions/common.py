import json
import multiprocessing
import sys

CONFIG = json.load(open('config/config.json', 'r'))
LOG_LOCATION = CONFIG['LOG_LOCATION']
PROCESSED_MUSIC_DIR = CONFIG['INGESTION_PIPELINE']['PROCESSED_MUSIC_DIR']

IS_UNIX = sys.platform.startswith('darwin') or sys.platform.startswith('linux')
NUM_CORES = CONFIG.get('NUM_CORES', multiprocessing.cpu_count())
