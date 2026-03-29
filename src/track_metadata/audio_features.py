from __future__ import annotations

import importlib
import logging
from pathlib import Path

import numpy as np

from src.track_metadata.models import SimpleMetadata


def _import_attr(module: str, attr: str):
    return getattr(importlib.import_module(module), attr)


def analyze_missing_audio_features(audio_path: Path, metadata: SimpleMetadata) -> SimpleMetadata:
    needs_bpm = metadata.bpm is None
    needs_key = metadata.key is None
    if not (needs_bpm or needs_key):
        return metadata

    if needs_bpm:
        bpm_estimate: float | None = None
        try:
            bpm_estimate = _estimate_bpm(audio_path)
        except Exception as exc:  # pragma: no cover - external library behaviour
            logging.warning("BPM analysis failed for %s: %s", audio_path.name, exc)
        if bpm_estimate is not None:
            metadata.bpm = round(bpm_estimate, 2)
            logging.info("Estimated BPM for %s: %.2f", audio_path.name, metadata.bpm)

    if needs_key:
        key_estimate: str | None = None
        try:
            key_estimate = _estimate_key(audio_path)
        except Exception as exc:  # pragma: no cover - external library behaviour
            logging.warning("Key analysis failed for %s: %s", audio_path.name, exc)
        if key_estimate is not None:
            metadata.key = key_estimate
            logging.info("Estimated key for %s: %s", audio_path.name, metadata.key)

    return metadata


def _estimate_bpm(audio_path: Path) -> float | None:
    try:
        DBNBeatTrackingProcessor = _import_attr(
            "madmom.features.beats", "DBNBeatTrackingProcessor"
        )
        RNNBeatProcessor = _import_attr("madmom.features.beats", "RNNBeatProcessor")
    except ImportError as exc:
        raise RuntimeError(
            "madmom is required for BPM estimation. "
            "Install this module's requirements to enable audio analysis."
        ) from exc

    beat_processor = RNNBeatProcessor()
    activation = beat_processor(str(audio_path))
    beats = DBNBeatTrackingProcessor(fps=100)(activation)
    if len(beats) < 2:
        return None

    intervals = np.diff(beats)  # type: ignore[arg-type]
    if intervals.size == 0:  # type: ignore[attr-defined]
        return None

    positive_intervals = intervals[intervals > 0]
    if positive_intervals.size == 0:  # type: ignore[attr-defined]
        return None

    median_interval = float(np.median(positive_intervals))  # type: ignore[arg-type]
    if median_interval <= 0:
        return None

    return 60.0 / median_interval


def _estimate_key(audio_path: Path) -> str | None:
    try:
        CNNKeyRecognitionProcessor = _import_attr(
            "madmom.features.key", "CNNKeyRecognitionProcessor"
        )
        key_prediction_to_label = _import_attr(
            "madmom.features.key", "key_prediction_to_label"
        )
    except ImportError as exc:
        raise RuntimeError(
            "madmom is required for key estimation. "
            "Install this module's requirements to enable audio analysis."
        ) from exc

    key_processor = CNNKeyRecognitionProcessor()
    prediction = key_processor(str(audio_path))
    if prediction is None:
        return None

    label = key_prediction_to_label(prediction)
    if isinstance(label, str):
        return label

    return None
