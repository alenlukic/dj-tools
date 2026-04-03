import multiprocessing
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

_REPO_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(_REPO_ROOT / ".env")


def _str(key: str, default: str = "") -> str:
    return os.getenv(key, default)


def _int(key: str, default: int) -> int:
    try:
        return int(os.environ[key])
    except (KeyError, ValueError):
        return default


def _float(key: str, default: float) -> float:
    try:
        return float(os.environ[key])
    except (KeyError, ValueError):
        return default


CONFIG = {
    "DATA": {
        "ROOT": _str("DATA_ROOT"),
        "BACKUP_RESTORE_MUSIC_DIR": _str("DATA_BACKUP_RESTORE_MUSIC_DIR"),
        "FILE_STAGING_DIR": _str("DATA_FILE_STAGING_DIR"),
    },
    "DB": {
        "NAME": _str("DB_NAME"),
        "USER": _str("DB_USER"),
        "PASSWORD": _str("DB_PASSWORD"),
        "HOST": _str("DB_HOST", "localhost"),
        "PORT": _str("DB_PORT", "5432"),
    },
    "FEATURE_EXTRACTION": {},
    "HARMONIC_MIXING": {
        "TRANSITION_MATCH_WEIGHTS": {
            "SIMILARITY": _float("HM_WEIGHT_SIMILARITY", 0.18),
            "CAMELOT": _float("HM_WEIGHT_CAMELOT", 0.2),
            "BPM": _float("HM_WEIGHT_BPM", 0.2),
            "FRESHNESS": _float("HM_WEIGHT_FRESHNESS", 0.08),
            "GENRE_SIMILARITY": _float("HM_WEIGHT_GENRE_SIMILARITY", 0.08),
            "MOOD_CONTINUITY": _float("HM_WEIGHT_MOOD_CONTINUITY", 0.06),
            "VOCAL_CLASH": _float("HM_WEIGHT_VOCAL_CLASH", 0.05),
            "DANCEABILITY": _float("HM_WEIGHT_DANCEABILITY", 0.07),
            "ENERGY": _float("HM_WEIGHT_ENERGY", 0.04),
            "TIMBRE": _float("HM_WEIGHT_TIMBRE", 0.04),
            "INSTRUMENT_SIMILARITY": _float("HM_WEIGHT_INSTRUMENT_SIMILARITY", 0.02),
        },
        "MAX_RESULTS": _int("HM_MAX_RESULTS", 50),
        "SCORE_THRESHOLD": _int("HM_SCORE_THRESHOLD", 25),
        "RESULT_THRESHOLD": _int("HM_RESULT_THRESHOLD", 20),
    },
    "INGESTION_PIPELINE": {
        "ROOT": _str("INGESTION_PIPELINE_ROOT"),
        "UNPROCESSED": _str("INGESTION_PIPELINE_UNPROCESSED", "unprocessed"),
        "PROCESSING": _str("INGESTION_PIPELINE_PROCESSING", "processing"),
        "FINALIZED": _str("INGESTION_PIPELINE_FINALIZED", "finalized"),
        "REKORDBOX_TAG_FILE": _str("INGESTION_PIPELINE_REKORDBOX_TAG_FILE", "rekordbox_tags.txt"),
        "PROCESSED_MUSIC_DIR": _str("INGESTION_PIPELINE_PROCESSED_MUSIC_DIR"),
    },
    "TRACK_METADATA": {
        "DOWNLOAD_DIR": _str("TRACK_METADATA_DOWNLOAD_DIR"),
        "PROCESSING_DIR": _str("TRACK_METADATA_PROCESSING_DIR", "processing"),
        "AUGMENTED_DIR": _str("TRACK_METADATA_AUGMENTED_DIR", "augmented"),
        "LOG_DIR": _str("TRACK_METADATA_LOG_DIR", "logs"),
    },
    "LOG_LOCATION": _str("LOG_LOCATION", "logs/logs.txt"),
}

LOG_LOCATION = CONFIG["LOG_LOCATION"]
PROCESSED_MUSIC_DIR = CONFIG["INGESTION_PIPELINE"]["PROCESSED_MUSIC_DIR"]

IS_UNIX = sys.platform.startswith("darwin") or sys.platform.startswith("linux")
NUM_CORES = _int("NUM_CORES", multiprocessing.cpu_count())

TIMESTAMP_FORMAT = "%a %b %d %H:%M:%S %Y"
