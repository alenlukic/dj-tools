from __future__ import annotations

import re

from src.track_metadata.models import SimpleMetadata


def _normalize_label_value(label: str | None) -> str | None:
    if label is None:
        return None

    return label.strip() or None


def _apply_label_fallback(metadata: SimpleMetadata) -> None:
    label = _normalize_label_value(metadata.label)
    if label is None:
        metadata.label = "CDR"
        return

    simplified = re.sub(r"[\s\-]+", " ", label).lower()
    if (
        "white label" in simplified
        or simplified == "whitelabel"
        or "self release" in simplified
        or "self released" in simplified
        or simplified == "self"
    ):
        metadata.label = "CDR"
    else:
        metadata.label = label
