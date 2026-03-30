"""ONNX model manager for trait extraction.

Downloads Essentia pre-trained ONNX models from essentia.upf.edu on first use
and caches them in models/traits/ (gitignored). Returns onnxruntime
InferenceSession objects; sessions are cached in-process after first load.

Usage:
    from src.feature_extraction.model_manager import load_model
    session = load_model("discogs-effnet-bsdynamic")
"""

import os
import urllib.request
from typing import Dict, Optional

import onnxruntime as ort

from src.feature_extraction.config import TRAIT_MODELS_DIR


_BASE_URL = "https://essentia.upf.edu/models"

# ONNX magic bytes — first 4 bytes of any valid ONNX file
_ONNX_MAGIC = b"\x08\x06"  # protobuf field 1 (varint), ModelProto starts with this

# Minimum reasonable ONNX file size (reject gateway-error HTML pages)
_MIN_ONNX_BYTES = 10_000

# Manifest: model name -> (relative URL path, local filename)
_MANIFEST: Dict[str, tuple] = {
    # EffNet backbone (outputs both embeddings and 400-class genre predictions)
    "discogs-effnet-bsdynamic": (
        "feature-extractors/discogs-effnet/discogs-effnet-bsdynamic-1.onnx",
        "discogs-effnet-bsdynamic-1.onnx",
    ),
    # MAEST standalone backbone — 519-class Discogs genre (30s context window)
    "discogs-maest-30s-pw-519l": (
        "feature-extractors/maest/discogs-maest-30s-pw-519l-2.onnx",
        "discogs-maest-30s-pw-519l-2.onnx",
    ),
    # EffNet classification heads
    "mtg_jamendo_moodtheme-discogs-effnet-1": (
        "classification-heads/mtg_jamendo_moodtheme/mtg_jamendo_moodtheme-discogs-effnet-1.onnx",
        "mtg_jamendo_moodtheme-discogs-effnet-1.onnx",
    ),
    "voice_instrumental-discogs-effnet-1": (
        "classification-heads/voice_instrumental/voice_instrumental-discogs-effnet-1.onnx",
        "voice_instrumental-discogs-effnet-1.onnx",
    ),
    "danceability-discogs-effnet-1": (
        "classification-heads/danceability/danceability-discogs-effnet-1.onnx",
        "danceability-discogs-effnet-1.onnx",
    ),
    "timbre-discogs-effnet-1": (
        "classification-heads/timbre/timbre-discogs-effnet-1.onnx",
        "timbre-discogs-effnet-1.onnx",
    ),
    "nsynth_acoustic_electronic-discogs-effnet-1": (
        "classification-heads/nsynth_acoustic_electronic/nsynth_acoustic_electronic-discogs-effnet-1.onnx",
        "nsynth_acoustic_electronic-discogs-effnet-1.onnx",
    ),
    "tonal_atonal-discogs-effnet-1": (
        "classification-heads/tonal_atonal/tonal_atonal-discogs-effnet-1.onnx",
        "tonal_atonal-discogs-effnet-1.onnx",
    ),
    "nsynth_reverb-discogs-effnet-1": (
        "classification-heads/nsynth_reverb/nsynth_reverb-discogs-effnet-1.onnx",
        "nsynth_reverb-discogs-effnet-1.onnx",
    ),
    "mtg_jamendo_instrument-discogs-effnet-1": (
        "classification-heads/mtg_jamendo_instrument/mtg_jamendo_instrument-discogs-effnet-1.onnx",
        "mtg_jamendo_instrument-discogs-effnet-1.onnx",
    ),
}

# In-process session cache: model name -> InferenceSession
_session_cache: Dict[str, Optional[ort.InferenceSession]] = {}


def _resolve_models_dir() -> str:
    """Return absolute path to the models/traits cache directory."""
    project_root = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    return os.path.join(project_root, TRAIT_MODELS_DIR)


def _is_valid_onnx(path: str) -> bool:
    """Return True if the file exists and looks like a valid ONNX model."""
    if not os.path.exists(path):
        return False
    if os.path.getsize(path) < _MIN_ONNX_BYTES:
        return False
    # ONNX/protobuf files start with a field tag for ModelProto.ir_version
    # The exact bytes vary, but they are never an HTML "<" character
    try:
        with open(path, "rb") as f:
            header = f.read(4)
        return header[:1] != b"<"
    except OSError:
        return False


def _download_model(name: str, url_path: str, local_filename: str) -> str:
    """Download an ONNX file if not already cached; return local path.

    Raises RuntimeError if the downloaded file is not a valid ONNX model
    (e.g. received an HTML gateway-error page instead).
    """
    models_dir = _resolve_models_dir()
    os.makedirs(models_dir, exist_ok=True)

    local_path = os.path.join(models_dir, local_filename)
    if _is_valid_onnx(local_path):
        return local_path

    # Remove stale/corrupt file before re-downloading
    if os.path.exists(local_path):
        os.remove(local_path)

    url = "%s/%s" % (_BASE_URL, url_path)
    print("Downloading %s ..." % url, flush=True)
    urllib.request.urlretrieve(url, local_path)

    if not _is_valid_onnx(local_path):
        os.remove(local_path)
        raise RuntimeError(
            "Downloaded file for '%s' is not a valid ONNX model "
            "(server may have returned an error page). "
            "Try again later." % name
        )

    return local_path


def load_model(name: str) -> ort.InferenceSession:
    """Return a cached InferenceSession for the named model.

    Downloads the ONNX file on first call if not present in models/traits/.
    Subsequent calls return the cached session.

    Args:
        name: Model name key from the manifest (e.g. "discogs-effnet-bsdynamic").

    Raises:
        KeyError: If name is not in the model manifest.
        RuntimeError: If the ONNX file cannot be downloaded or loaded.
    """
    if name in _session_cache:
        return _session_cache[name]

    if name not in _MANIFEST:
        raise KeyError(
            "Unknown model '%s'. Available: %s" % (name, list(_MANIFEST.keys()))
        )

    url_path, local_filename = _MANIFEST[name]
    try:
        local_path = _download_model(name, url_path, local_filename)
        session = ort.InferenceSession(
            local_path,
            providers=["CPUExecutionProvider"],
        )
        _session_cache[name] = session
        return session
    except Exception as exc:
        raise RuntimeError(
            "Failed to load ONNX model '%s': %s" % (name, exc)
        ) from exc


def is_cached(name: str) -> bool:
    """Return True if the named model's ONNX file exists and is valid."""
    if name not in _MANIFEST:
        return False
    _, local_filename = _MANIFEST[name]
    models_dir = _resolve_models_dir()
    return _is_valid_onnx(os.path.join(models_dir, local_filename))
