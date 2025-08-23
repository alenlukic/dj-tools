from src.utils.common import join_config_paths

AUDIO_TYPES = {".mp3", ".wav", ".flac", ".ogg", ".aif", ".aiff", ".m3u"}
FILE_STAGING_DIR = join_config_paths([["DATA", "ROOT"], ["DATA", "FILE_STAGING_DIR"]])
