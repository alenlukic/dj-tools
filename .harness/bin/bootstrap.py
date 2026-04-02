#!/usr/bin/env python3
"""
Repo-aware bootstrap and docs-sync tool.

Subcommands:
    scan    — traverse repo, build inventory, infer profile/module-map/command-registry
    plan    — compute proposed doc updates from current state
    apply   — apply only approved/high-confidence generated changes
    sync    — incremental refresh: detect drift, update state, queue doc deltas
    doctor  — verify docs and instruction surfaces against reality

Usage:
    python3 .harness/bin/bootstrap.py <subcommand> [--repo-root <path>]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

BIN_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BIN_DIR))

from _state import (
    _ensure_state_dir, write_yaml, write_json, read_yaml, read_json,
    now_iso, profile_path, inventory_path, module_map_path,
    command_registry_path, docs_sync_path, pending_updates_path,
    open_items_path, REPO_PROFILE_TEMPLATE,
)
from _discovery import scan_repo, infer_profile, infer_module_map, content_hash
from _merge import (
    parse_generated_sections, replace_generated_section,
    insert_generated_section_at_end, has_section,
    make_generated_block, can_auto_apply,
)
from _validate import doctor_check, validate_profile_schema


def find_repo_root(start=None):
    # type: (str | None) -> str
    p = Path(start) if start else Path.cwd()
    while p != p.parent:
        if (p / ".harness").is_dir():
            return str(p)
        p = p.parent
    return str(Path(start) if start else Path.cwd())


# ---------------------------------------------------------------------------
# scan
# ---------------------------------------------------------------------------

def cmd_scan(args: argparse.Namespace) -> int:
    repo_root = args.repo_root
    print(f"[scan] Scanning repository: {repo_root}")

    _ensure_state_dir(repo_root)

    inventory = scan_repo(repo_root)
    write_json(inventory_path(repo_root), inventory)
    print(f"  -> wrote repo-inventory.json ({len(inventory.get('docs', []))} docs, "
          f"{len(inventory.get('manifests', []))} manifests)")

    profile = infer_profile(inventory, repo_root)
    write_yaml(profile_path(repo_root), profile)
    print(f"  -> wrote repo-profile.yaml (languages: {len(profile.get('languages', []))})")

    modules = infer_module_map(inventory, repo_root)
    module_data = {
        "schema_version": "1",
        "modules": modules,
        "scanned_at": now_iso(),
    }
    write_yaml(module_map_path(repo_root), module_data)
    print(f"  -> wrote module-map.yaml ({len(modules)} modules)")

    cmd_reg_path = command_registry_path(repo_root)
    from _discovery import _infer_commands
    cmd_list = _infer_commands(inventory, repo_root)
    write_json(cmd_reg_path, cmd_list)
    print(f"  -> wrote command-registry.json ({len(cmd_list)} commands)")

    docs_sync = _build_docs_sync_state(repo_root)
    write_json(docs_sync_path(repo_root), docs_sync)
    print(f"  -> wrote docs-sync-state.json")

    pending = {"pending_updates": [], "last_computed": now_iso()}
    write_yaml(pending_updates_path(repo_root), pending)
    print(f"  -> wrote pending-doc-updates.yaml")

    findings = _compute_findings(profile, inventory, repo_root)
    oi_path = open_items_path(repo_root)
    oi_path.parent.mkdir(parents=True, exist_ok=True)
    write_yaml(oi_path, {"open_items": findings, "last_updated": now_iso()})
    print(f"  -> wrote open-items.yaml ({len(findings)} findings)")

    print("[scan] Complete.")
    return 0


def _build_docs_sync_state(repo_root: str) -> dict:
    """Build docs-sync-state.json from current instruction surfaces."""
    root = Path(repo_root)
    state: dict = {"sections": {}, "last_sync": now_iso()}

    for surface in ("AGENTS.md", "HUMANS.md", "CLAUDE.md"):
        fp = root / surface
        if not fp.exists():
            continue
        text = fp.read_text()
        sections = parse_generated_sections(text)
        for s in sections:
            state["sections"][s.section_id] = {
                "file": surface,
                "source": s.source,
                "last_sync": s.generated_at or now_iso(),
                "last_verification": None,
                "content_hash": content_hash(s.content),
            }

    return state


def _compute_findings(profile: dict, inventory: dict, repo_root: str) -> list[dict]:
    """Identify low-confidence or ambiguous items."""
    findings = []

    for lang in profile.get("languages", []):
        if isinstance(lang, dict) and lang.get("confidence", 1.0) < 0.7:
            findings.append({
                "type": "low_confidence_language",
                "detail": f"Language '{lang['name']}' detected with low confidence ({lang['confidence']})",
                "evidence": "file extension count",
                "confidence": lang["confidence"],
            })

    conf = profile.get("confidence", {})
    if isinstance(conf, dict) and conf.get("commands", 1.0) < 0.7:
        findings.append({
            "type": "low_confidence_commands",
            "detail": "Command inference has low confidence — pipeline.yaml uses placeholder commands",
            "evidence": ".harness/pipeline.yaml",
            "confidence": conf["commands"],
        })

    if not inventory.get("entrypoints"):
        findings.append({
            "type": "no_entrypoints",
            "detail": "No standard entrypoints detected (main.py, index.ts, etc.)",
            "evidence": "traversal",
            "confidence": 0.5,
        })

    if not inventory.get("ci_configs"):
        findings.append({
            "type": "no_ci",
            "detail": "No CI/CD configuration detected",
            "evidence": "traversal",
            "confidence": 0.8,
        })

    return findings


# ---------------------------------------------------------------------------
# plan
# ---------------------------------------------------------------------------

def _generate_repo_identity_content(profile: dict) -> str:
    """Build the one-liner repo identity from the current profile."""
    repo_name = profile.get("repo", {}).get("name", "unknown")
    langs = [
        lang["name"] if isinstance(lang, dict) else str(lang)
        for lang in profile.get("languages", [])
    ]
    lang_str = ", ".join(langs[:5]) if langs else "unknown"
    return f"**Repo:** {repo_name} | **Primary tooling:** agentic delivery harness | **Languages:** {lang_str}"


def cmd_plan(args: argparse.Namespace) -> int:
    repo_root = args.repo_root
    print(f"[plan] Computing doc update plan for: {repo_root}")

    root = Path(repo_root)
    state_dir = root / ".harness" / "state"

    if not (state_dir / "repo-profile.yaml").exists():
        print("  ERROR: Run 'scan' first — no state files found.")
        return 1

    profile = read_yaml(profile_path(repo_root))
    pending_items: list[dict] = []

    content_payload = _generate_repo_identity_content(profile)

    for surface in ("AGENTS.md", "HUMANS.md"):
        fp = root / surface
        if not fp.exists():
            continue
        text = fp.read_text()
        section_id = f"{surface.replace('.md', '').lower()}-repo-identity"
        if not has_section(text, section_id):
            pending_items.append({
                "target_file": surface,
                "section_id": section_id,
                "reason": f"Add repo identity section to {surface}",
                "confidence": 0.9,
                "evidence": "repo-profile.yaml",
                "auto_apply_allowed": False,
                "content": content_payload,
                "source": ".harness/state/repo-profile.yaml",
            })
        else:
            existing = parse_generated_sections(text)
            for s in existing:
                if s.section_id == section_id and s.content.strip() != content_payload.strip():
                    pending_items.append({
                        "target_file": surface,
                        "section_id": section_id,
                        "reason": f"Update repo identity section in {surface}",
                        "confidence": 0.9,
                        "evidence": "repo-profile.yaml",
                        "auto_apply_allowed": True,
                        "content": content_payload,
                        "source": ".harness/state/repo-profile.yaml",
                    })

    pending = {
        "pending_updates": pending_items,
        "last_computed": now_iso(),
    }
    write_yaml(pending_updates_path(repo_root), pending)

    if pending_items:
        print(f"  -> {len(pending_items)} proposed updates queued:")
        for item in pending_items:
            print(f"     - {item['target_file']}: {item['reason']} (confidence: {item['confidence']})")
    else:
        print("  -> No updates needed — docs are in sync.")

    print("[plan] Complete.")
    return 0


# ---------------------------------------------------------------------------
# apply
# ---------------------------------------------------------------------------

HIGH_RISK_KINDS = {"infra", "deploy", "migration"}


def _check_has_blocking_finding(repo_root: str) -> bool:
    oi = open_items_path(repo_root)
    if not oi.exists():
        return False
    try:
        data = read_yaml(oi)
    except Exception:
        return False
    for item in data.get("open_items", []):
        if isinstance(item, dict) and item.get("type") == "blocking":
            return True
    return False


def _check_touches_high_risk(repo_root: str, target_file: str) -> bool:
    reg_path = command_registry_path(repo_root)
    if not reg_path.exists():
        return False
    try:
        registry = read_json(reg_path)
    except Exception:
        return False
    for cmd in registry:
        if isinstance(cmd, dict) and cmd.get("kind", "") in HIGH_RISK_KINDS:
            evidence = cmd.get("evidence", "")
            if evidence and target_file in evidence:
                return True
    return False


def _check_has_duplicate_source(repo_root: str, section_id: str) -> bool:
    ds_path = docs_sync_path(repo_root)
    if not ds_path.exists():
        return False
    try:
        state = read_json(ds_path)
    except Exception:
        return False
    sections = state.get("sections", {})
    if section_id not in sections:
        return False
    source = sections[section_id].get("source", "")
    if not source:
        return False
    for sid, info in sections.items():
        if sid != section_id and info.get("source") == source:
            return True
    return False


def cmd_apply(args: argparse.Namespace) -> int:
    repo_root = args.repo_root
    print(f"[apply] Applying approved generated changes for: {repo_root}")

    root = Path(repo_root)
    pu_path = pending_updates_path(repo_root)

    if not pu_path.exists():
        print("  No pending updates found. Run 'plan' first.")
        return 0

    pending = read_yaml(pu_path)
    updates = pending.get("pending_updates", [])
    if not updates:
        print("  No pending updates to apply.")
        return 0

    has_blocking = _check_has_blocking_finding(repo_root)

    applied = []
    skipped = []

    for update in updates:
        conf = update.get("confidence", 0.0)
        if isinstance(conf, str):
            conf = float(conf)

        target = update.get("target_file", "")
        fp = root / target
        section_id = update.get("section_id", "")
        content = update.get("content", "")

        is_generated = True
        if fp.exists():
            text = fp.read_text()
            is_generated = has_section(text, section_id) if section_id else False
        else:
            text = ""

        touches_high_risk = _check_touches_high_risk(repo_root, target)
        has_duplicate = _check_has_duplicate_source(repo_root, section_id)

        auto_ok = can_auto_apply(
            confidence=conf,
            is_generated_only=is_generated,
            has_duplicate_source=has_duplicate,
            touches_high_risk=touches_high_risk,
            has_blocking_finding=has_blocking,
        )

        if auto_ok and content:
            source = update.get("source", "")
            if is_generated:
                text = replace_generated_section(text, section_id, content, source, conf)
            else:
                text = insert_generated_section_at_end(text, section_id, content, source, conf)
            fp.write_text(text)
            applied.append(update)
            print(f"  [auto-apply] {target} / {section_id}")
        else:
            if auto_ok and not content:
                print(f"  [skipped] {target} / {section_id} (no content payload)")
            else:
                print(f"  [queued] {target} / {section_id} (confidence={conf}, needs review)")
            skipped.append(update)

    remaining = {"pending_updates": skipped, "last_computed": now_iso()}
    write_yaml(pu_path, remaining)

    print(f"[apply] Complete: {len(applied)} applied, {len(skipped)} remain queued.")
    return 0


# ---------------------------------------------------------------------------
# sync
# ---------------------------------------------------------------------------

def cmd_sync(args: argparse.Namespace) -> int:
    repo_root = args.repo_root
    print(f"[sync] Incremental sync for: {repo_root}")

    root = Path(repo_root)
    state_dir = root / ".harness" / "state"

    if not state_dir.exists():
        print("  No state directory — running full scan first.")
        ns = argparse.Namespace(repo_root=repo_root)
        cmd_scan(ns)

    old_inventory_path = inventory_path(repo_root)
    old_inventory = {}
    if old_inventory_path.exists():
        old_inventory = read_json(old_inventory_path)

    new_inventory = scan_repo(repo_root)

    drift = _detect_drift(old_inventory, new_inventory)

    if drift:
        print(f"  Drift detected in {len(drift)} areas:")
        for d in drift:
            print(f"    - {d['area']}: {d['detail']}")

        write_json(inventory_path(repo_root), new_inventory)
        profile = infer_profile(new_inventory, repo_root)
        write_yaml(profile_path(repo_root), profile)

        modules = infer_module_map(new_inventory, repo_root)
        write_yaml(module_map_path(repo_root), {
            "schema_version": "1",
            "modules": modules,
            "scanned_at": now_iso(),
        })

        from _discovery import _infer_commands
        write_json(command_registry_path(repo_root), _infer_commands(new_inventory, repo_root))

        pu_path = pending_updates_path(repo_root)
        existing_pending = read_yaml(pu_path) if pu_path.exists() else {}
        existing_items = existing_pending.get("pending_updates", [])
        for d in drift:
            existing_items.append({
                "target_file": d.get("affected_surface", ""),
                "section_id": d.get("section_id", ""),
                "reason": f"Drift: {d['detail']}",
                "confidence": 0.6,
                "evidence": d["area"],
                "auto_apply_allowed": False,
            })
        write_yaml(pu_path, {"pending_updates": existing_items, "last_computed": now_iso()})
    else:
        print("  No drift detected — state is current.")
        write_json(inventory_path(repo_root), new_inventory)

    docs_sync = _build_docs_sync_state(repo_root)
    write_json(docs_sync_path(repo_root), docs_sync)

    print("[sync] Complete.")
    return 0


def _detect_drift(old: dict, new: dict) -> list[dict]:
    drift = []
    old_docs = set(old.get("docs", []))
    new_docs = set(new.get("docs", []))
    added_docs = new_docs - old_docs
    removed_docs = old_docs - new_docs

    if added_docs:
        drift.append({
            "area": "docs",
            "detail": f"New docs added: {', '.join(sorted(added_docs)[:5])}",
            "affected_surface": "AGENTS.md",
            "section_id": "agents-repo-identity",
        })
    if removed_docs:
        drift.append({
            "area": "docs",
            "detail": f"Docs removed: {', '.join(sorted(removed_docs)[:5])}",
            "affected_surface": "AGENTS.md",
            "section_id": "agents-repo-identity",
        })

    old_manifests = set(old.get("manifests", []))
    new_manifests = set(new.get("manifests", []))
    if old_manifests != new_manifests:
        drift.append({
            "area": "manifests",
            "detail": "Manifest files changed",
            "affected_surface": "AGENTS.md",
            "section_id": "agents-repo-identity",
        })

    old_dirs = set(old.get("major_directories", []))
    new_dirs = set(new.get("major_directories", []))
    if old_dirs != new_dirs:
        drift.append({
            "area": "structure",
            "detail": f"Top-level directory structure changed: added={new_dirs - old_dirs}, removed={old_dirs - new_dirs}",
            "affected_surface": "AGENTS.md",
            "section_id": "agents-repo-identity",
        })

    return drift


# ---------------------------------------------------------------------------
# doctor
# ---------------------------------------------------------------------------

def cmd_doctor(args: argparse.Namespace) -> int:
    repo_root = args.repo_root
    print(f"[doctor] Verifying docs and surfaces for: {repo_root}")

    report = doctor_check(repo_root)

    for check in report["checks"]:
        status = "PASS" if check["passed"] else "FAIL"
        print(f"  [{status}] {check['name']}")
        for detail in check.get("details", []):
            print(f"         {detail}")

    if report["warnings"]:
        print(f"\n  Warnings ({len(report['warnings'])}):")
        for w in report["warnings"]:
            print(f"    - {w}")

    if report["errors"]:
        print(f"\n  Errors ({len(report['errors'])}):")
        for e in report["errors"]:
            print(f"    - {e}")

    print(f"\n[doctor] Status: {report['status'].upper()}")

    return 0 if report["status"] != "fail" else 1


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        prog="bootstrap",
        description="Repo-aware bootstrap and docs-sync tool",
    )
    sub = parser.add_subparsers(dest="command")

    for name, hlp in [
        ("scan", "Traverse repo, build inventory, infer state"),
        ("plan", "Compute proposed doc updates"),
        ("apply", "Apply approved/high-confidence generated changes"),
        ("sync", "Incremental drift detection and state refresh"),
        ("doctor", "Verify docs and surfaces against reality"),
    ]:
        sp = sub.add_parser(name, help=hlp)
        sp.add_argument("--repo-root", default=None, help="Repository root")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    if args.repo_root is None:
        args.repo_root = find_repo_root()

    handlers = {
        "scan": cmd_scan,
        "plan": cmd_plan,
        "apply": cmd_apply,
        "sync": cmd_sync,
        "doctor": cmd_doctor,
    }

    return handlers[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
