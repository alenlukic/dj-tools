"""Tests for src/config.py: env loading, key mapping, defaults, and helpers."""

import importlib
from unittest.mock import patch

import pytest

_CONFIG_VARS = [
    "DATA_ROOT", "DATA_BACKUP_RESTORE_MUSIC_DIR", "DATA_FILE_STAGING_DIR",
    "DB_NAME", "DB_USER", "DB_PASSWORD", "DB_HOST", "DB_PORT",
    "HM_WEIGHT_SIMILARITY", "HM_WEIGHT_CAMELOT", "HM_WEIGHT_BPM",
    "HM_WEIGHT_FRESHNESS", "HM_WEIGHT_GENRE_SIMILARITY",
    "HM_WEIGHT_MOOD_CONTINUITY", "HM_WEIGHT_VOCAL_CLASH",
    "HM_WEIGHT_DANCEABILITY", "HM_WEIGHT_ENERGY", "HM_WEIGHT_TIMBRE",
    "HM_WEIGHT_INSTRUMENT_SIMILARITY",
    "HM_MAX_RESULTS", "HM_SCORE_THRESHOLD", "HM_RESULT_THRESHOLD",
    "INGESTION_PIPELINE_ROOT", "INGESTION_PIPELINE_UNPROCESSED",
    "INGESTION_PIPELINE_PROCESSING", "INGESTION_PIPELINE_FINALIZED",
    "INGESTION_PIPELINE_REKORDBOX_TAG_FILE",
    "INGESTION_PIPELINE_PROCESSED_MUSIC_DIR",
    "TRACK_METADATA_DOWNLOAD_DIR", "TRACK_METADATA_PROCESSING_DIR",
    "TRACK_METADATA_AUGMENTED_DIR", "TRACK_METADATA_LOG_DIR",
    "LOG_LOCATION", "NUM_CORES",
]


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch):
    """Remove all config-relevant env vars so reloads see only what each test sets."""
    for var in _CONFIG_VARS:
        monkeypatch.delenv(var, raising=False)


def _reload_config():
    """Re-import src.config with load_dotenv disabled so only env vars set
    by the test are visible — the on-disk .env is never read."""
    with patch("dotenv.load_dotenv", return_value=None):
        import src.config as mod
        importlib.reload(mod)
        return mod


# ---------------------------------------------------------------------------
# Helper function tests
# ---------------------------------------------------------------------------

class TestHelpers:
    def test_str_returns_env_value(self, monkeypatch):
        monkeypatch.setenv("TEST_STR_VAR", "hello")
        from src.config import _str
        assert _str("TEST_STR_VAR") == "hello"

    def test_str_returns_default_when_missing(self):
        from src.config import _str
        assert _str("NONEXISTENT_VAR_XYZ", "fallback") == "fallback"

    def test_str_returns_empty_string_default(self):
        from src.config import _str
        assert _str("NONEXISTENT_VAR_XYZ") == ""

    def test_int_returns_env_value(self, monkeypatch):
        monkeypatch.setenv("TEST_INT_VAR", "42")
        from src.config import _int
        assert _int("TEST_INT_VAR", 0) == 42

    def test_int_returns_default_on_missing(self):
        from src.config import _int
        assert _int("NONEXISTENT_VAR_XYZ", 99) == 99

    def test_int_returns_default_on_invalid(self, monkeypatch):
        monkeypatch.setenv("TEST_INT_VAR", "not_a_number")
        from src.config import _int
        assert _int("TEST_INT_VAR", 7) == 7

    def test_float_returns_env_value(self, monkeypatch):
        monkeypatch.setenv("TEST_FLOAT_VAR", "3.14")
        from src.config import _float
        assert _float("TEST_FLOAT_VAR", 0.0) == pytest.approx(3.14)

    def test_float_returns_default_on_missing(self):
        from src.config import _float
        assert _float("NONEXISTENT_VAR_XYZ", 1.5) == pytest.approx(1.5)

    def test_float_returns_default_on_invalid(self, monkeypatch):
        monkeypatch.setenv("TEST_FLOAT_VAR", "abc")
        from src.config import _float
        assert _float("TEST_FLOAT_VAR", 2.5) == pytest.approx(2.5)


# ---------------------------------------------------------------------------
# CONFIG structure tests
# ---------------------------------------------------------------------------

class TestConfigStructure:
    def test_top_level_keys(self):
        mod = _reload_config()
        expected = {
            "DATA", "DB", "FEATURE_EXTRACTION", "HARMONIC_MIXING",
            "INGESTION_PIPELINE", "TRACK_METADATA", "LOG_LOCATION",
        }
        assert expected == set(mod.CONFIG.keys())

    def test_data_keys(self):
        mod = _reload_config()
        assert set(mod.CONFIG["DATA"].keys()) == {"ROOT", "BACKUP_RESTORE_MUSIC_DIR", "FILE_STAGING_DIR"}

    def test_db_keys(self):
        mod = _reload_config()
        assert set(mod.CONFIG["DB"].keys()) == {"NAME", "USER", "PASSWORD", "HOST", "PORT"}

    def test_harmonic_mixing_keys(self):
        mod = _reload_config()
        hm = mod.CONFIG["HARMONIC_MIXING"]
        assert "TRANSITION_MATCH_WEIGHTS" in hm
        assert "MAX_RESULTS" in hm
        assert "SCORE_THRESHOLD" in hm
        assert "RESULT_THRESHOLD" in hm

    def test_transition_match_weight_keys(self):
        mod = _reload_config()
        weights = mod.CONFIG["HARMONIC_MIXING"]["TRANSITION_MATCH_WEIGHTS"]
        expected = {
            "SIMILARITY", "CAMELOT", "BPM", "FRESHNESS", "GENRE_SIMILARITY",
            "MOOD_CONTINUITY", "VOCAL_CLASH", "DANCEABILITY", "ENERGY",
            "TIMBRE", "INSTRUMENT_SIMILARITY",
        }
        assert expected == set(weights.keys())

    def test_ingestion_pipeline_keys(self):
        mod = _reload_config()
        assert set(mod.CONFIG["INGESTION_PIPELINE"].keys()) == {
            "ROOT", "UNPROCESSED", "PROCESSING", "FINALIZED",
            "REKORDBOX_TAG_FILE", "PROCESSED_MUSIC_DIR",
        }

    def test_track_metadata_keys(self):
        mod = _reload_config()
        assert set(mod.CONFIG["TRACK_METADATA"].keys()) == {
            "DOWNLOAD_DIR", "PROCESSING_DIR", "AUGMENTED_DIR", "LOG_DIR",
        }


# ---------------------------------------------------------------------------
# Default value tests
# ---------------------------------------------------------------------------

class TestDefaults:
    def test_db_host_default(self):
        mod = _reload_config()
        assert mod.CONFIG["DB"]["HOST"] == "localhost"

    def test_db_port_default(self):
        mod = _reload_config()
        assert mod.CONFIG["DB"]["PORT"] == "5432"

    def test_harmonic_mixing_weight_defaults(self):
        mod = _reload_config()
        weights = mod.CONFIG["HARMONIC_MIXING"]["TRANSITION_MATCH_WEIGHTS"]
        assert weights["SIMILARITY"] == pytest.approx(0.18)
        assert weights["CAMELOT"] == pytest.approx(0.2)
        assert weights["BPM"] == pytest.approx(0.2)
        assert weights["FRESHNESS"] == pytest.approx(0.08)
        assert weights["GENRE_SIMILARITY"] == pytest.approx(0.08)
        assert weights["MOOD_CONTINUITY"] == pytest.approx(0.06)
        assert weights["VOCAL_CLASH"] == pytest.approx(0.05)
        assert weights["DANCEABILITY"] == pytest.approx(0.07)
        assert weights["ENERGY"] == pytest.approx(0.04)
        assert weights["TIMBRE"] == pytest.approx(0.04)
        assert weights["INSTRUMENT_SIMILARITY"] == pytest.approx(0.02)

    def test_harmonic_mixing_threshold_defaults(self):
        mod = _reload_config()
        hm = mod.CONFIG["HARMONIC_MIXING"]
        assert hm["MAX_RESULTS"] == 50
        assert hm["SCORE_THRESHOLD"] == 25
        assert hm["RESULT_THRESHOLD"] == 20

    def test_ingestion_pipeline_subdir_defaults(self):
        mod = _reload_config()
        ip = mod.CONFIG["INGESTION_PIPELINE"]
        assert ip["UNPROCESSED"] == "unprocessed"
        assert ip["PROCESSING"] == "processing"
        assert ip["FINALIZED"] == "finalized"
        assert ip["REKORDBOX_TAG_FILE"] == "rekordbox_tags.txt"

    def test_track_metadata_subdir_defaults(self):
        mod = _reload_config()
        tm = mod.CONFIG["TRACK_METADATA"]
        assert tm["PROCESSING_DIR"] == "processing"
        assert tm["AUGMENTED_DIR"] == "augmented"
        assert tm["LOG_DIR"] == "logs"

    def test_log_location_default(self):
        mod = _reload_config()
        assert mod.CONFIG["LOG_LOCATION"] == "logs/logs.txt"

    def test_string_vars_default_to_empty_when_unset(self):
        mod = _reload_config()
        assert mod.CONFIG["DATA"]["ROOT"] == ""
        assert mod.CONFIG["DB"]["NAME"] == ""
        assert mod.CONFIG["DB"]["USER"] == ""
        assert mod.CONFIG["DB"]["PASSWORD"] == ""
        assert mod.CONFIG["INGESTION_PIPELINE"]["ROOT"] == ""
        assert mod.CONFIG["TRACK_METADATA"]["DOWNLOAD_DIR"] == ""


# ---------------------------------------------------------------------------
# Env-to-config key mapping tests
# ---------------------------------------------------------------------------

class TestEnvMapping:
    def test_env_var_overrides_data_root(self, monkeypatch):
        monkeypatch.setenv("DATA_ROOT", "/test/data")
        mod = _reload_config()
        assert mod.CONFIG["DATA"]["ROOT"] == "/test/data"

    def test_env_var_overrides_db_host(self, monkeypatch):
        monkeypatch.setenv("DB_HOST", "db.example.com")
        mod = _reload_config()
        assert mod.CONFIG["DB"]["HOST"] == "db.example.com"

    def test_env_var_overrides_weight(self, monkeypatch):
        monkeypatch.setenv("HM_WEIGHT_BPM", "0.99")
        mod = _reload_config()
        assert mod.CONFIG["HARMONIC_MIXING"]["TRANSITION_MATCH_WEIGHTS"]["BPM"] == pytest.approx(0.99)

    def test_env_var_overrides_int_threshold(self, monkeypatch):
        monkeypatch.setenv("HM_MAX_RESULTS", "100")
        mod = _reload_config()
        assert mod.CONFIG["HARMONIC_MIXING"]["MAX_RESULTS"] == 100

    def test_env_var_overrides_log_location(self, monkeypatch):
        monkeypatch.setenv("LOG_LOCATION", "/tmp/test.log")
        mod = _reload_config()
        assert mod.CONFIG["LOG_LOCATION"] == "/tmp/test.log"
        assert mod.LOG_LOCATION == "/tmp/test.log"

    def test_num_cores_override(self, monkeypatch):
        monkeypatch.setenv("NUM_CORES", "8")
        mod = _reload_config()
        assert mod.NUM_CORES == 8

    def test_num_cores_default_is_cpu_count(self):
        import multiprocessing
        mod = _reload_config()
        assert mod.NUM_CORES == multiprocessing.cpu_count()


# ---------------------------------------------------------------------------
# Module-level convenience attribute tests
# ---------------------------------------------------------------------------

class TestModuleAttributes:
    def test_log_location_alias(self):
        mod = _reload_config()
        assert mod.LOG_LOCATION == mod.CONFIG["LOG_LOCATION"]

    def test_processed_music_dir_alias(self, monkeypatch):
        monkeypatch.setenv("INGESTION_PIPELINE_PROCESSED_MUSIC_DIR", "/music")
        mod = _reload_config()
        assert mod.PROCESSED_MUSIC_DIR == "/music"

    def test_timestamp_format(self):
        mod = _reload_config()
        assert mod.TIMESTAMP_FORMAT == "%a %b %d %H:%M:%S %Y"
