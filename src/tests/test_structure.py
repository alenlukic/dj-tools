"""Structural tests enforcing module dependency direction.

Validates the layer hierarchy defined in docs/ARCHITECTURE.md:

  L1 (Foundation): models, db, config, errors, utils
  L2 (Domain Services): track_metadata, data_management, feature_extraction, postprocessing
  L3 (Orchestration): harmonic_mixing, ingestion_pipeline
  L4 (Entry Points): assistant, scripts

Rules:
  - L1 must not import from L2, L3, or L4
  - L2 may import from L1 only
  - L3 may import from L1 and L2
  - L4 may import from any layer
  - scripts/ files are leaf nodes (never imported by non-script code)
"""

import ast
import os
from pathlib import Path

import pytest

SRC_ROOT = Path(__file__).resolve().parent.parent

LAYER_1 = {"models", "db", "config", "errors", "utils"}
LAYER_2 = {"track_metadata", "data_management", "feature_extraction", "postprocessing"}
LAYER_3 = {"harmonic_mixing", "ingestion_pipeline"}
LAYER_4 = {"assistant", "scripts"}

ALL_MODULES = LAYER_1 | LAYER_2 | LAYER_3 | LAYER_4

MODULE_TO_LAYER = {}
for mod in LAYER_1:
    MODULE_TO_LAYER[mod] = 1
for mod in LAYER_2:
    MODULE_TO_LAYER[mod] = 2
for mod in LAYER_3:
    MODULE_TO_LAYER[mod] = 3
for mod in LAYER_4:
    MODULE_TO_LAYER[mod] = 4

ALLOWED_IMPORTS = {
    1: {1},
    2: {1, 2},
    3: {1, 2, 3},
    4: {1, 2, 3, 4},
}

KNOWN_VIOLATIONS = {
    ("harmonic_mixing", "assistant"),
}


def _get_src_module(import_path: str):
    """Extract the top-level src module from an import path like 'src.foo.bar'."""
    parts = import_path.split(".")
    if len(parts) >= 2 and parts[0] == "src":
        return parts[1]
    return None


def _extract_imports(filepath: Path):
    """Parse a Python file and return all src-internal import targets."""
    try:
        tree = ast.parse(filepath.read_text(), filename=str(filepath))
    except SyntaxError:
        return []

    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                mod = _get_src_module(alias.name)
                if mod:
                    imports.append(mod)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                mod = _get_src_module(node.module)
                if mod:
                    imports.append(mod)
    return imports


def _get_module_for_file(filepath: Path):
    """Determine which top-level src module a file belongs to."""
    rel = filepath.relative_to(SRC_ROOT)
    parts = rel.parts
    if not parts:
        return None
    first = parts[0]
    if first.endswith(".py"):
        name = first[:-3]
        if name in ALL_MODULES:
            return name
        return None
    if first in ALL_MODULES:
        return first
    return None


def _collect_python_files(root: Path):
    """Collect all .py files under root, excluding tests and __pycache__."""
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [
            d for d in dirnames if d not in ("__pycache__", "tests", ".pytest_cache")
        ]
        for f in filenames:
            if f.endswith(".py"):
                yield Path(dirpath) / f


def test_layer_dependency_direction():
    """Verify that no module imports from a higher layer than allowed."""
    violations = []

    for filepath in _collect_python_files(SRC_ROOT):
        source_module = _get_module_for_file(filepath)
        if not source_module:
            continue

        source_layer = MODULE_TO_LAYER.get(source_module)
        if not source_layer:
            continue

        allowed = ALLOWED_IMPORTS[source_layer]
        imported_modules = _extract_imports(filepath)

        for target_module in imported_modules:
            if target_module == source_module:
                continue
            target_layer = MODULE_TO_LAYER.get(target_module)
            if target_layer is None:
                continue
            if target_layer not in allowed:
                pair = (source_module, target_module)
                if pair not in KNOWN_VIOLATIONS:
                    rel_path = filepath.relative_to(SRC_ROOT)
                    violations.append(
                        f"{rel_path}: {source_module} (L{source_layer}) "
                        f"imports {target_module} (L{target_layer})"
                    )

    if violations:
        msg = "Layer dependency violations found:\n" + "\n".join(
            f"  - {v}" for v in violations
        )
        pytest.fail(msg)


def test_scripts_are_leaf_nodes():
    """Verify that no non-script module imports from src.scripts."""
    violations = []

    for filepath in _collect_python_files(SRC_ROOT):
        source_module = _get_module_for_file(filepath)
        if source_module == "scripts":
            continue

        imported_modules = _extract_imports(filepath)
        if "scripts" in imported_modules:
            rel_path = filepath.relative_to(SRC_ROOT)
            violations.append(f"{rel_path}: imports from scripts/")

    if violations:
        msg = "Scripts should be leaf nodes but are imported by:\n" + "\n".join(
            f"  - {v}" for v in violations
        )
        pytest.fail(msg)


def test_no_circular_same_layer_imports():
    """Check for circular import chains between modules at the same layer."""
    graph = {}

    for filepath in _collect_python_files(SRC_ROOT):
        source_module = _get_module_for_file(filepath)
        if not source_module:
            continue

        source_layer = MODULE_TO_LAYER.get(source_module)
        if not source_layer:
            continue

        imported_modules = _extract_imports(filepath)
        for target_module in set(imported_modules):
            if target_module == source_module:
                continue
            target_layer = MODULE_TO_LAYER.get(target_module)
            if target_layer == source_layer:
                graph.setdefault(source_module, set()).add(target_module)

    cycles = []
    for mod_a, targets in graph.items():
        for mod_b in targets:
            if mod_b in graph and mod_a in graph.get(mod_b, set()):
                pair = tuple(sorted([mod_a, mod_b]))
                if pair not in cycles:
                    cycles.append(pair)

    if cycles:
        msg = "Circular same-layer imports found:\n" + "\n".join(
            f"  - {a} <-> {b}" for a, b in cycles
        )
        pytest.fail(msg)


def test_known_violations_documented():
    """Ensure known violations list stays accurate.

    If a known violation is fixed, remove it from KNOWN_VIOLATIONS so the
    list doesn't silently grow stale.
    """
    still_present = set()

    for filepath in _collect_python_files(SRC_ROOT):
        source_module = _get_module_for_file(filepath)
        if not source_module:
            continue

        source_layer = MODULE_TO_LAYER.get(source_module)
        if not source_layer:
            continue

        allowed = ALLOWED_IMPORTS[source_layer]
        imported_modules = _extract_imports(filepath)

        for target_module in imported_modules:
            if target_module == source_module:
                continue
            target_layer = MODULE_TO_LAYER.get(target_module)
            if target_layer is None:
                continue
            if target_layer not in allowed:
                pair = (source_module, target_module)
                if pair in KNOWN_VIOLATIONS:
                    still_present.add(pair)

    stale = KNOWN_VIOLATIONS - still_present
    if stale:
        msg = (
            "Known violations that no longer exist (remove from KNOWN_VIOLATIONS):\n"
            + "\n".join(f"  - {a} -> {b}" for a, b in stale)
        )
        pytest.fail(msg)
