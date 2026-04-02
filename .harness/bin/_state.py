"""State layer: read/write for .harness/state/ artifacts."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


def _state_dir(repo_root: str) -> Path:
    return Path(repo_root) / ".harness" / "state"


def _ensure_state_dir(repo_root: str) -> Path:
    d = _state_dir(repo_root)
    d.mkdir(parents=True, exist_ok=True)
    return d


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# repo-profile.yaml
# ---------------------------------------------------------------------------

REPO_PROFILE_TEMPLATE = {
    "schema_version": "1",
    "repo": {"name": "", "root": "", "description": ""},
    "languages": [],
    "frameworks": [],
    "modules": [],
    "commands": {},
    "runtime_surfaces": [],
    "high_risk_domains": [],
    "docs_map": [],
    "instruction_surfaces": {},
    "confidence": {},
    "last_scanned": None,
    "last_verified": None,
}


def write_yaml(path: Path, data: Any) -> None:
    try:
        import yaml
        with open(path, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
    except ImportError:
        _write_yaml_fallback(path, data)


def read_yaml(path: Path) -> Any:
    try:
        import yaml
        with open(path) as f:
            return yaml.safe_load(f) or {}
    except ImportError:
        return _read_yaml_fallback(path)


def write_json(path: Path, data: Any) -> None:
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)
        f.write("\n")


def read_json(path: Path) -> Any:
    with open(path) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Minimal YAML fallback (no external dependency)
# ---------------------------------------------------------------------------

def _yaml_serialize(obj, indent=0):
    # type: (Any, int) -> str
    prefix = "  " * indent
    if obj is None:
        return "null"
    if isinstance(obj, bool):
        return "true" if obj else "false"
    if isinstance(obj, (int, float)):
        return str(obj)
    if isinstance(obj, str):
        if any(c in obj for c in ":{}\n[]#&*!|>'\"%@`"):
            escaped = obj.replace("\\", "\\\\").replace('"', '\\"')
            return f'"{escaped}"'
        if obj == "" or obj.strip() != obj:
            return f'"{obj}"'
        return obj
    if isinstance(obj, list):
        if not obj:
            return "[]"
        lines = []
        for item in obj:
            val = _yaml_serialize(item, indent + 1)
            if isinstance(item, dict):
                first_line, *rest = val.split("\n")
                lines.append(f"{prefix}- {first_line}")
                lines.extend(rest)
            else:
                lines.append(f"{prefix}- {val}")
        return "\n".join(lines)
    if isinstance(obj, dict):
        if not obj:
            return "{}"
        lines = []
        for k, v in obj.items():
            key_str = _yaml_serialize(str(k))
            if isinstance(v, (dict, list)) and v:
                lines.append(f"{prefix}{key_str}:")
                lines.append(_yaml_serialize(v, indent + 1))
            else:
                val = _yaml_serialize(v, indent + 1)
                lines.append(f"{prefix}{key_str}: {val}")
        return "\n".join(lines)
    return str(obj)


def _write_yaml_fallback(path: Path, data: Any) -> None:
    with open(path, "w") as f:
        f.write(_yaml_serialize(data))
        f.write("\n")


def _read_yaml_fallback(path):
    # type: (Path) -> dict
    """Fallback when PyYAML is unavailable. Returns empty dict to avoid silent corruption."""
    import sys
    print(
        f"WARNING: PyYAML not installed — cannot parse {path}. "
        "Install it with: pip install pyyaml",
        file=sys.stderr,
    )
    return {}


# ---------------------------------------------------------------------------
# State file paths
# ---------------------------------------------------------------------------

def profile_path(repo_root: str) -> Path:
    return _state_dir(repo_root) / "repo-profile.yaml"


def inventory_path(repo_root: str) -> Path:
    return _state_dir(repo_root) / "repo-inventory.json"


def module_map_path(repo_root: str) -> Path:
    return _state_dir(repo_root) / "module-map.yaml"


def command_registry_path(repo_root: str) -> Path:
    return _state_dir(repo_root) / "command-registry.json"


def docs_sync_path(repo_root: str) -> Path:
    return _state_dir(repo_root) / "docs-sync-state.json"


def pending_updates_path(repo_root: str) -> Path:
    return _state_dir(repo_root) / "pending-doc-updates.yaml"


def open_items_path(repo_root: str) -> Path:
    return Path(repo_root) / ".harness" / "docs" / "quality" / "findings" / "open-items.yaml"
