"""Validation and doctor logic: schema checks, marker integrity, stale references."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List

from _merge import parse_generated_sections, MARKER_BEGIN, MARKER_END
from _state import read_yaml, read_json


def doctor_check(repo_root: str) -> dict[str, Any]:
    """Run all doctor checks and return structured report."""
    root = Path(repo_root)
    report: dict[str, Any] = {
        "status": "pass",
        "checks": [],
        "warnings": [],
        "errors": [],
    }

    _check_state_files_exist(root, report)
    _check_command_references(root, report)
    _check_generated_markers(root, report)
    _check_duplicate_truth(root, report)
    _check_stale_module_descriptions(root, report)

    if report["errors"]:
        report["status"] = "fail"
    elif report["warnings"]:
        report["status"] = "warn"

    return report


def _check_state_files_exist(root: Path, report: dict) -> None:
    state_dir = root / ".harness" / "state"
    expected = [
        "repo-profile.yaml",
        "repo-inventory.json",
        "module-map.yaml",
        "command-registry.json",
        "docs-sync-state.json",
        "pending-doc-updates.yaml",
    ]
    check = {"name": "state_files_exist", "passed": True, "details": []}
    for f in expected:
        fp = state_dir / f
        if not fp.exists():
            check["passed"] = False
            check["details"].append(f"Missing: {f}")
            report["warnings"].append(f"State file missing: .harness/state/{f}")
    report["checks"].append(check)


def _check_command_references(root: Path, report: dict) -> None:
    """Verify commands in registry point to real files/scripts."""
    reg_path = root / ".harness" / "state" / "command-registry.json"
    check = {"name": "command_references", "passed": True, "details": []}

    if not reg_path.exists():
        check["details"].append("Command registry not found — skipping")
        report["checks"].append(check)
        return

    try:
        registry = read_json(reg_path)
    except Exception as e:
        check["passed"] = False
        check["details"].append(f"Failed to read registry: {e}")
        report["errors"].append(f"Command registry unreadable: {e}")
        report["checks"].append(check)
        return

    for cmd in registry:
        evidence = cmd.get("evidence", "")
        if evidence and not (root / evidence).exists():
            check["passed"] = False
            msg = f"Stale command '{cmd.get('command_id', '?')}': evidence file missing: {evidence}"
            check["details"].append(msg)
            report["errors"].append(msg)

    report["checks"].append(check)


def _check_generated_markers(root, report):
    # type: (Path, dict) -> None
    """Verify marker integrity in instruction surfaces (skips code fences)."""
    check = {"name": "generated_markers", "passed": True, "details": []}
    surfaces = ["AGENTS.md", "HUMANS.md", "CLAUDE.md"]

    for surf in surfaces:
        fp = root / surf
        if not fp.exists():
            continue
        text = fp.read_text()
        lines = text.split("\n")

        open_markers = {}  # type: Dict[str, int]
        in_code_fence = False
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("```"):
                in_code_fence = not in_code_fence
                continue
            if in_code_fence:
                continue

            begin = MARKER_BEGIN.search(line)
            end = MARKER_END.search(line)
            if begin:
                sid = begin.group("section_id")
                if sid in open_markers:
                    check["passed"] = False
                    msg = "{}: Nested or unclosed marker for '{}' at line {}".format(surf, sid, i+1)
                    check["details"].append(msg)
                    report["errors"].append(msg)
                open_markers[sid] = i
            if end:
                sid = end.group("section_id")
                if sid not in open_markers:
                    check["passed"] = False
                    msg = "{}: END marker without BEGIN for '{}' at line {}".format(surf, sid, i+1)
                    check["details"].append(msg)
                    report["errors"].append(msg)
                else:
                    del open_markers[sid]

        for sid, line_num in open_markers.items():
            check["passed"] = False
            msg = "{}: Unclosed BEGIN marker for '{}' at line {}".format(surf, sid, line_num+1)
            check["details"].append(msg)
            report["errors"].append(msg)

    report["checks"].append(check)


def _check_duplicate_truth(root: Path, report: dict) -> None:
    """Detect if the same section_id appears in multiple surfaces."""
    check = {"name": "duplicate_truth", "passed": True, "details": []}
    surfaces = ["AGENTS.md", "HUMANS.md", "CLAUDE.md"]
    section_locations: dict[str, list[str]] = {}

    for surf in surfaces:
        fp = root / surf
        if not fp.exists():
            continue
        text = fp.read_text()
        sections = parse_generated_sections(text)
        for s in sections:
            section_locations.setdefault(s.section_id, []).append(surf)

    for sid, locs in section_locations.items():
        if len(locs) > 1:
            check["passed"] = False
            msg = f"Duplicate generated section '{sid}' in: {', '.join(locs)}"
            check["details"].append(msg)
            report["warnings"].append(msg)

    report["checks"].append(check)


def _check_stale_module_descriptions(root: Path, report: dict) -> None:
    """Check that module-map entries reference existing paths."""
    check = {"name": "stale_modules", "passed": True, "details": []}
    mm_path = root / ".harness" / "state" / "module-map.yaml"

    if not mm_path.exists():
        check["details"].append("Module map not found — skipping")
        report["checks"].append(check)
        return

    try:
        mm = read_yaml(mm_path)
    except Exception:
        check["details"].append("Module map unreadable — skipping")
        report["checks"].append(check)
        return

    modules = mm.get("modules", []) if isinstance(mm, dict) else []
    for mod in modules:
        if isinstance(mod, dict):
            p = mod.get("path", "")
            if p and not (root / p).exists():
                check["passed"] = False
                msg = f"Module '{mod.get('name', '?')}' path not found: {p}"
                check["details"].append(msg)
                report["warnings"].append(msg)

    report["checks"].append(check)


def validate_profile_schema(profile: dict) -> list[str]:
    """Basic schema validation for repo-profile.yaml."""
    errors = []
    if profile.get("schema_version") != "1":
        errors.append("schema_version must be '1'")
    if "repo" not in profile or not isinstance(profile["repo"], dict):
        errors.append("'repo' section missing or invalid")
    for field in ("languages", "frameworks", "modules"):
        if field in profile and not isinstance(profile[field], list):
            errors.append(f"'{field}' must be a list")
    return errors
