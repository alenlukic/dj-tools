#!/usr/bin/env python3
"""Smoke tests for bootstrap.py subcommands."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import shutil

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
BOOTSTRAP = os.path.join(REPO_ROOT, ".harness", "bin", "bootstrap.py")


def run_bootstrap(subcmd, repo_root=None):
    root = repo_root or REPO_ROOT
    result = subprocess.run(
        [sys.executable, BOOTSTRAP, subcmd, "--repo-root", root],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    return result


def test_scan_runs_without_error():
    """bootstrap.py scan runs successfully on the current repo."""
    r = run_bootstrap("scan")
    assert r.returncode == 0, f"scan failed: {r.stderr}"
    assert "[scan] Complete." in r.stdout

    state_dir = os.path.join(REPO_ROOT, ".harness", "state")
    for f in ["repo-profile.yaml", "repo-inventory.json", "module-map.yaml",
              "command-registry.json", "docs-sync-state.json", "pending-doc-updates.yaml"]:
        assert os.path.exists(os.path.join(state_dir, f)), f"Missing state file: {f}"


def test_doctor_detects_stale_reference():
    """bootstrap.py doctor can detect a stale command reference."""
    run_bootstrap("scan")

    reg_path = os.path.join(REPO_ROOT, ".harness", "state", "command-registry.json")
    with open(reg_path) as f:
        registry = json.load(f)

    registry.append({
        "command_id": "stale-test-cmd",
        "kind": "test",
        "canonical": "bash nonexistent-script.sh",
        "alternates": [],
        "scope": "repo",
        "confidence": 0.5,
        "evidence": "nonexistent-file-for-test.sh",
        "last_verified": None,
    })
    with open(reg_path, "w") as f:
        json.dump(registry, f, indent=2)

    r = run_bootstrap("doctor")

    registry = [c for c in registry if c["command_id"] != "stale-test-cmd"]
    with open(reg_path, "w") as f:
        json.dump(registry, f, indent=2)

    assert "stale-test-cmd" in r.stdout or "nonexistent-file-for-test.sh" in r.stdout, \
        f"Doctor did not detect stale reference: {r.stdout}"


def test_plan_produces_stable_output():
    """bootstrap.py plan produces stable output on a second run."""
    run_bootstrap("scan")

    r1 = run_bootstrap("plan")
    assert r1.returncode == 0, f"plan (1st) failed: {r1.stderr}"

    r2 = run_bootstrap("plan")
    assert r2.returncode == 0, f"plan (2nd) failed: {r2.stderr}"

    lines1 = [l for l in r1.stdout.strip().split("\n") if "proposed updates" in l or "No updates" in l]
    lines2 = [l for l in r2.stdout.strip().split("\n") if "proposed updates" in l or "No updates" in l]
    assert lines1 == lines2, f"Plan output not stable:\n  1st: {lines1}\n  2nd: {lines2}"


def test_apply_noop_without_generated_section():
    """apply is a no-op when no pending updates exist (file stays unchanged)."""
    run_bootstrap("scan")

    test_file = os.path.join(REPO_ROOT, "AGENTS.md")
    original = open(test_file).read()

    pu_path = os.path.join(REPO_ROOT, ".harness", "state", "pending-doc-updates.yaml")
    try:
        import yaml
        with open(pu_path, "w") as f:
            yaml.dump({"pending_updates": [], "last_computed": "2026-01-01T00:00:00+00:00"},
                      f, default_flow_style=False)
    except ImportError:
        with open(pu_path, "w") as f:
            f.write("pending_updates: []\nlast_computed: '2026-01-01T00:00:00+00:00'\n")

    r = run_bootstrap("apply")
    assert r.returncode == 0, f"apply failed: {r.stderr}"

    after = open(test_file).read()
    assert original == after, "apply modified AGENTS.md when there were no pending updates"


def test_sync_runs_without_error():
    """bootstrap.py sync runs without error on the current repo."""
    run_bootstrap("scan")
    r = run_bootstrap("sync")
    assert r.returncode == 0, f"sync failed: {r.stderr}"
    assert "[sync] Complete." in r.stdout


def main():
    tests = [
        ("scan_runs_without_error", test_scan_runs_without_error),
        ("doctor_detects_stale_reference", test_doctor_detects_stale_reference),
        ("plan_produces_stable_output", test_plan_produces_stable_output),
        ("apply_noop_without_generated_section", test_apply_noop_without_generated_section),
        ("sync_runs_without_error", test_sync_runs_without_error),
    ]

    results = []
    for name, fn in tests:
        try:
            fn()
            results.append((name, "PASS", ""))
            print(f"  PASS  {name}")
        except Exception as e:
            results.append((name, "FAIL", str(e)))
            print(f"  FAIL  {name}: {e}")

    passed = sum(1 for _, s, _ in results if s == "PASS")
    total = len(results)
    print(f"\n{passed}/{total} tests passed.")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
