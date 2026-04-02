#!/usr/bin/env python3

# Copyright (c) 2026 Rational Dynamics LLC

from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import re
import subprocess
import sys
from typing import Any

import yaml


SCRIPT_PATH = pathlib.Path(__file__).resolve()
ROOT = SCRIPT_PATH.parents[2]
RUNS_DIR = ROOT / ".harness" / "runs"
CONFIG_PATH = ROOT / ".harness" / "pipeline.yaml"

GRADE_BANDS: list[tuple[int, str]] = [
    (93, "A"), (90, "A-"), (87, "B+"), (83, "B"), (80, "B-"),
    (77, "C+"), (73, "C"), (70, "C-"), (60, "D"), (0, "F"),
]
FLOOR_CATEGORIES = {"correctness", "reliability_operational_safety", "security_data_safety"}


def grade_from_score(score: float) -> str:
    for threshold, grade in GRADE_BANDS:
        if score >= threshold:
            return grade
    return "F"


def load_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"Missing config: {CONFIG_PATH}")
    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def utc_run_id() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def ensure_runs_dir() -> None:
    RUNS_DIR.mkdir(parents=True, exist_ok=True)


def write_text(path: pathlib.Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_json(path: pathlib.Path, data: Any) -> None:
    write_text(path, json.dumps(data, indent=2) + "\n")


def read_json(path: pathlib.Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def run_shell(cmd: str) -> dict[str, Any]:
    proc = subprocess.run(
        cmd,
        shell=True,
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    return {
        "cmd": cmd,
        "exit_code": proc.returncode,
        "stdout_tail": proc.stdout[-8000:],
        "stderr_tail": proc.stderr[-8000:],
        "ran_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    }


def create_run(task: str, mode: str) -> pathlib.Path:
    ensure_runs_dir()
    run_dir = RUNS_DIR / utc_run_id()
    run_dir.mkdir(parents=True, exist_ok=False)
    (RUNS_DIR / "current").unlink(missing_ok=True)
    try:
        (RUNS_DIR / "current").symlink_to(run_dir.name)
    except OSError:
        pass

    write_text(run_dir / "TASK.md", task.strip() + "\n")
    write_text(
        run_dir / "PLAN.md",
        "# Plan\n\n"
        f"Mode: {mode}\n\n"
        "## Initial plan\n"
        "- Restate requirements\n"
        "- Identify relevant files\n"
        "- Implement narrowly\n"
        "- Review\n"
        "- QA\n"
        "- Verify\n",
    )
    write_text(
        run_dir / "REVIEW_NOTES.md",
        "## Blockers\n- \n\n## Important\n- \n\n## Nits\n- \n\n## Verdict\nCHANGES_REQUESTED\n",
    )
    write_text(
        run_dir / "QA_REPORT.md",
        "# QA Report\n\n"
        "## Requirement Trace\n| Requirement | Evidence | Status | Notes |\n| --- | --- | --- | --- |\n\n"
        "## Failures\n- \n\n## Verdict\nFAIL\n",
    )
    write_text(
        run_dir / "BUILD_VERIFICATION.md",
        "# Build Verification\n\n## Status\nPENDING\n\n## Notes\n- \n",
    )
    write_json(run_dir / "TEST_REPORT.json", {"commands": [], "last_intent": None})
    write_json(run_dir / "RETRY_LOG.jsonl", [])
    return run_dir


def run_intent(config: dict[str, Any], intent: str) -> list[dict[str, Any]]:
    commands = config.get("commands", {}).get(intent, [])
    return [run_shell(cmd) for cmd in commands]


def capture_diff(run_dir: pathlib.Path) -> None:
    result = run_shell("git diff")
    write_text(run_dir / "PATCH.diff", result.get("stdout_tail", ""))

    names = run_shell("git diff --name-only")
    files = [line.strip() for line in names["stdout_tail"].splitlines() if line.strip()]

    numstat = run_shell("git diff --numstat")
    added = 0
    deleted = 0
    file_stats: list[dict[str, Any]] = []
    for line in numstat["stdout_tail"].splitlines():
        parts = line.split("\t")
        if len(parts) != 3:
            continue
        a, d, path = parts
        try:
            ai = 0 if a == "-" else int(a)
            di = 0 if d == "-" else int(d)
        except ValueError:
            continue
        added += ai
        deleted += di
        file_stats.append({"path": path, "added": ai, "deleted": di})

    write_json(
        run_dir / "DIFF_STATS.json",
        {
            "files_changed": len(files),
            "files": files,
            "added": added,
            "deleted": deleted,
            "per_file": file_stats,
        },
    )


def parse_markdown_verdict(path: pathlib.Path, patterns: list[str], default: str = "UNKNOWN") -> str:
    if not path.exists():
        return default
    text = path.read_text(encoding="utf-8")
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE)
        if match:
            return match.group(1).upper()
    return default


def test_summary(report_path: pathlib.Path) -> dict[str, Any]:
    report = read_json(report_path, {"commands": []})
    commands = report.get("commands", [])
    total = len(commands)
    failing = [c for c in commands if c.get("exit_code") != 0]
    return {
        "total": total,
        "failing": len(failing),
        "failing_commands": failing[-5:],
        "all_passed": total > 0 and not failing,
        "ran_any": total > 0,
        "applicable": report.get("applicable", True),
    }


def validate_policy(run_dir: pathlib.Path, config: dict[str, Any]) -> dict[str, Any]:
    capture_diff(run_dir)
    diff_stats = read_json(run_dir / "DIFF_STATS.json", {})
    policies = config.get("policies", {})
    violations: list[str] = []

    files = diff_stats.get("files", [])
    files_changed = diff_stats.get("files_changed", 0)
    diff_lines = diff_stats.get("added", 0) + diff_stats.get("deleted", 0)

    max_files = policies.get("max_files_changed")
    if isinstance(max_files, int) and files_changed > max_files:
        violations.append(f"files_changed_exceeds_limit:{files_changed}>{max_files}")

    max_lines = policies.get("max_diff_lines")
    if isinstance(max_lines, int) and diff_lines > max_lines:
        violations.append(f"diff_lines_exceeds_limit:{diff_lines}>{max_lines}")

    forbidden = policies.get("forbid_paths", [])
    for file in files:
        for prefix in forbidden:
            if file.startswith(prefix) or prefix in file:
                violations.append(f"forbidden_path:{file}")

    report = {
        "ok": not violations,
        "files_changed": files_changed,
        "diff_lines": diff_lines,
        "violations": violations,
        "checked_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    }
    write_json(run_dir / "POLICY_REPORT.json", report)
    return report


def evaluate(run_dir: pathlib.Path, config: dict[str, Any]) -> dict[str, Any]:
    gates = config.get("gates", {})
    threshold = int(gates.get("eval_threshold", 80))
    conditional_threshold = int(gates.get("eval_conditional_threshold", 70))
    tests = test_summary(run_dir / "TEST_REPORT.json")
    policy = read_json(run_dir / "POLICY_REPORT.json", {"ok": True, "violations": []})
    regression = read_json(run_dir / "REGRESSION_REPORT.json", {"severity": "UNKNOWN", "regressions_found": False})
    qa_verdict = parse_markdown_verdict(run_dir / "QA_REPORT.md", [r"## Verdict\s+([A-Z_]+)", r"^Verdict:\s*([A-Z_]+)$"])
    build_status = parse_markdown_verdict(run_dir / "BUILD_VERIFICATION.md", [r"## Status\s+([A-Z_]+)", r"^Status:\s*([A-Z_]+)$"])
    review_verdict = parse_markdown_verdict(run_dir / "REVIEW_NOTES.md", [r"## Verdict\s+([A-Z_]+)", r"^Verdict:\s*([A-Z_]+)$"])

    score = 100
    findings: list[str] = []

    if not tests["ran_any"]:
        if tests["applicable"]:
            score -= 20
            findings.append("no_test_evidence")
        else:
            findings.append("tests_not_applicable")
    elif not tests["all_passed"]:
        score -= 35
        findings.append("test_failures_present")

    if not policy.get("ok", True):
        score -= 20
        findings.append("policy_violations_present")

    if qa_verdict not in {"PASS", "APPROVE"}:
        score -= 15
        findings.append(f"qa_not_pass:{qa_verdict}")

    if build_status not in {"PASS", "SUCCESS"}:
        score -= 15
        findings.append(f"build_not_pass:{build_status}")

    if review_verdict in {"CHANGES_REQUESTED", "FAIL"}:
        score -= 10
        findings.append(f"review_not_approved:{review_verdict}")

    severity = str(regression.get("severity", "UNKNOWN")).upper()
    if severity == "HIGH":
        score -= 15
        findings.append("high_regression_risk")
    elif severity == "CRITICAL":
        score -= 25
        findings.append("critical_regression_risk")
    elif regression.get("regressions_found"):
        score -= 8
        findings.append("non_blocking_regression_risk")

    score = max(score, 0)

    # Apply hard floors from agent-produced category scores (if present).
    # The Delivery Evaluator agent writes categories to EVAL_REPORT.json before
    # this function is re-run during remediation, so we pick them up here.
    existing_eval = read_json(run_dir / "EVAL_REPORT.json", {})
    categories: dict[str, Any] = existing_eval.get("categories") or {}
    floor_breaches: list[str] = []
    for cat in FLOOR_CATEGORIES:
        cat_data = categories.get(cat, {})
        cat_score = cat_data.get("score") if isinstance(cat_data, dict) else None
        if cat_score is not None:
            if cat_score < 40:
                floor_breaches.append(f"{cat}:below_40")
                findings.append(f"hard_floor_breach:{cat}")
            elif cat_score < 60:
                score = min(score, 73)
                floor_breaches.append(f"{cat}:below_60")

    grade = grade_from_score(score)
    hard_block = {"critical_regression_risk", "policy_violations_present"}
    has_hard_block = bool(hard_block & set(findings))
    has_floor_fail = any("below_40" in b for b in floor_breaches)
    verdict = "PASS" if score >= threshold and not has_hard_block and not has_floor_fail else "FAIL"
    if verdict == "FAIL" and not has_hard_block and not has_floor_fail and score >= conditional_threshold:
        verdict = "CONDITIONAL"

    report: dict[str, Any] = {
        "score": score,
        "grade": grade,
        "threshold": threshold,
        "grade_threshold": "B-",
        "verdict": verdict,
        "dimensions": {
            "tests": "PASS" if tests["all_passed"] else ("N/A" if not tests["applicable"] else ("MISSING" if not tests["ran_any"] else "FAIL")),
            "policy": "PASS" if policy.get("ok", True) else "FAIL",
            "qa": qa_verdict,
            "build": build_status,
            "review": review_verdict,
            "regression": severity,
        },
        "hard_floor_breaches": floor_breaches,
        "findings": findings,
        "evaluated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    }
    if categories:
        report["categories"] = categories
    write_json(run_dir / "EVAL_REPORT.json", report)
    return report


def prepare_retry(run_dir: pathlib.Path, config: dict[str, Any], reason: str | None) -> dict[str, Any]:
    retry_log = read_json(run_dir / "RETRY_LOG.jsonl", [])
    gates = config.get("gates", {})
    max_retry_rounds = int(gates.get("max_retry_rounds", 2))
    next_round = len(retry_log) + 1

    eval_report = read_json(run_dir / "EVAL_REPORT.json", {})
    policy_report = read_json(run_dir / "POLICY_REPORT.json", {})
    diff_stats = read_json(run_dir / "DIFF_STATS.json", {})
    tests = test_summary(run_dir / "TEST_REPORT.json")

    failure_lines = []
    if reason:
        failure_lines.append(f"- Operator reason: {reason}")
    if eval_report:
        grade = eval_report.get("grade", "")
        grade_str = f" — {grade}" if grade else ""
        failure_lines.append(f"- Eval verdict: {eval_report.get('verdict')}{grade_str} ({eval_report.get('score')}/{eval_report.get('threshold')})")
        for finding in eval_report.get("findings", []):
            failure_lines.append(f"  - finding: {finding}")
    if policy_report and not policy_report.get("ok", True):
        for violation in policy_report.get("violations", []):
            failure_lines.append(f"  - policy violation: {violation}")
    for cmd in tests.get("failing_commands", []):
        failure_lines.append(f"  - failing command: {cmd.get('cmd')} (exit {cmd.get('exit_code')})")

    changed_files = diff_stats.get("files", [])
    changed_block = "\n".join(f"- {path}" for path in changed_files) if changed_files else "- none detected"

    retry_task = (
        "# Retry Task\n\n"
        f"Retry round: {next_round} / {max_retry_rounds}\n\n"
        "## Why retry is needed\n"
        + ("\n".join(failure_lines) if failure_lines else "- gate failure observed\n")
        + "\n\n## Constraints\n"
        "- Keep remediation targeted.\n"
        "- Do not broaden scope.\n"
        "- Update SECOND_PASS_PLAN.md before editing.\n"
        "- Prefer the smallest coherent patch that addresses the cited failures.\n"
    )

    second_pass = (
        "# Second Pass Plan\n\n"
        f"Retry round: {next_round}\n\n"
        "## Observed diff\n"
        f"{changed_block}\n\n"
        "## Failure-focused objectives\n"
        "- Identify the smallest set of causes behind the current failures.\n"
        "- Convert each cause into one targeted remediation step.\n"
        "- Re-run only the verification steps needed to regain confidence.\n\n"
        "## Remediation steps\n"
        "1. ...\n"
        "2. ...\n"
        "3. ...\n"
    )

    write_text(run_dir / "RETRY_TASK.md", retry_task)
    write_text(run_dir / "SECOND_PASS_PLAN.md", second_pass)
    retry_log.append({
        "round": next_round,
        "reason": reason or "gate_failure",
        "prepared_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    })
    write_json(run_dir / "RETRY_LOG.jsonl", retry_log)

    return {"round": next_round, "max_rounds": max_retry_rounds, "prepared": True}


def ensure_regression_stub(run_dir: pathlib.Path) -> None:
    path = run_dir / "REGRESSION_REPORT.json"
    if not path.exists():
        write_json(path, {
            "regressions_found": False,
            "severity": "UNKNOWN",
            "areas": [],
            "notes": ["Populate via Delivery Regression Detector agent."],
        })


def validate_task_files(paths: list[str]) -> list[dict[str, Any]]:
    """Validate task-definition files and return their metadata."""
    entries: list[dict[str, Any]] = []
    for i, p in enumerate(paths):
        fp = pathlib.Path(p)
        if not fp.exists():
            raise FileNotFoundError(f"Task file does not exist: {p}")
        if not fp.is_file():
            raise ValueError(f"Task file is not a regular file: {p}")
        try:
            content = fp.read_text(encoding="utf-8").strip()
        except OSError as e:
            raise ValueError(f"cannot read {p}: {e}") from e
        if not content:
            raise ValueError(f"Task file is empty: {p}")
        entries.append({
            "index": i,
            "source_file": str(fp),
            "task_content": content,
            "run_id": None,
            "run_dir": None,
            "status": "pending",
            "started_at": None,
            "finished_at": None,
            "eval_score": None,
            "eval_verdict": None,
            "summary": None,
        })
    return entries


def create_batch(task_entries: list[dict[str, Any]]) -> pathlib.Path:
    """Create a batch directory with BATCH_REPORT.json."""
    ensure_runs_dir()
    batch_id = f"batch-{utc_run_id()}"
    batch_dir = RUNS_DIR / batch_id
    batch_dir.mkdir(parents=True, exist_ok=False)
    report = {
        "batch_id": batch_id,
        "batch_dir": str(batch_dir),
        "started_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "finished_at": None,
        "status": "running",
        "on_failure": "fail_fast",
        "tasks": task_entries,
    }
    write_json(batch_dir / "BATCH_REPORT.json", report)
    return batch_dir


def update_batch_task(batch_dir: pathlib.Path, index: int, updates: dict[str, Any]) -> dict[str, Any]:
    """Update a specific task entry in BATCH_REPORT.json."""
    report_path = batch_dir / "BATCH_REPORT.json"
    report = read_json(report_path)
    if report is None:
        raise FileNotFoundError(f"BATCH_REPORT.json not found in {batch_dir}")
    tasks = report.get("tasks", [])
    if index < 0 or index >= len(tasks):
        raise IndexError(f"Task index {index} out of range (0..{len(tasks) - 1})")
    tasks[index].update(updates)
    write_json(report_path, report)
    return report


def finalize_batch(batch_dir: pathlib.Path, status: str) -> dict[str, Any]:
    """Mark the batch as complete/failed/partial."""
    report_path = batch_dir / "BATCH_REPORT.json"
    report = read_json(report_path)
    if report is None:
        raise FileNotFoundError(f"BATCH_REPORT.json not found in {batch_dir}")
    report["status"] = status
    report["finished_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
    write_json(report_path, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Repo-local agentic harness helper")
    subparsers = parser.add_subparsers(dest="command", required=True)

    start_parser = subparsers.add_parser("start", help="Create a new run")
    start_parser.add_argument("--mode", choices=["delivery", "maintenance", "restructure"], default="delivery")
    start_parser.add_argument("--task", required=True, help="Task description")

    run_parser = subparsers.add_parser("run", help="Run a configured intent and update TEST_REPORT.json")
    run_parser.add_argument("--run-dir", required=True, help="Path to existing run directory")
    run_parser.add_argument("--intent", choices=["format", "lint", "test", "build", "db"], required=True)

    diff_parser = subparsers.add_parser("diff", help="Capture git diff into PATCH.diff and DIFF_STATS.json")
    diff_parser.add_argument("--run-dir", required=True, help="Path to existing run directory")

    validate_parser = subparsers.add_parser("validate", help="Run policy validation against current diff")
    validate_parser.add_argument("--run-dir", required=True, help="Path to existing run directory")

    evaluate_parser = subparsers.add_parser("evaluate", help="Produce EVAL_REPORT.json from available artifacts")
    evaluate_parser.add_argument("--run-dir", required=True, help="Path to existing run directory")

    retry_parser = subparsers.add_parser("prepare-retry", help="Create remediation artifacts for a bounded retry")
    retry_parser.add_argument("--run-dir", required=True, help="Path to existing run directory")
    retry_parser.add_argument("--reason", required=False, help="Optional reason for the retry")

    batch_start_parser = subparsers.add_parser("batch-start", help="Initialize a batch run from multiple task files")
    batch_start_parser.add_argument("--task-files", nargs="+", required=True, help="Paths to task-definition files (min 2)")

    batch_record_parser = subparsers.add_parser("batch-record-outcome", help="Record outcome for a batch task")
    batch_record_parser.add_argument("--batch-dir", required=True, help="Path to batch directory")
    batch_record_parser.add_argument("--index", type=int, required=True, help="Task index in the batch")
    batch_record_parser.add_argument("--run-dir", required=False, help="Path to the task's run directory")
    batch_record_parser.add_argument("--status", required=True, choices=["pass", "fail", "skip"], help="Outcome status")
    batch_record_parser.add_argument("--started-at", required=False, help="ISO timestamp when the task started")
    batch_record_parser.add_argument("--summary", required=False, help="Optional outcome summary")

    batch_finalize_parser = subparsers.add_parser("batch-finalize", help="Finalize a batch run")
    batch_finalize_parser.add_argument("--batch-dir", required=True, help="Path to batch directory")
    batch_finalize_parser.add_argument("--status", required=True, choices=["complete", "failed", "partial"], help="Final batch status")

    args = parser.parse_args()
    config = load_config()

    if args.command == "start":
        run_dir = create_run(task=args.task, mode=args.mode)
        ensure_regression_stub(run_dir)
        print(str(run_dir))
        return 0

    if args.command == "batch-start":
        task_files = args.task_files
        if len(task_files) < 2:
            print("batch-start requires at least 2 task files", file=sys.stderr)
            return 1
        try:
            entries = validate_task_files(task_files)
        except (FileNotFoundError, ValueError) as exc:
            print(f"Task file validation failed: {exc}", file=sys.stderr)
            return 1
        batch_dir = create_batch(entries)
        print(str(batch_dir))
        return 0

    if args.command == "batch-record-outcome":
        batch_dir = pathlib.Path(args.batch_dir)
        if not batch_dir.exists():
            print(f"Batch directory does not exist: {batch_dir}", file=sys.stderr)
            return 1
        updates: dict[str, Any] = {
            "status": args.status,
            "finished_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        }
        if args.started_at:
            updates["started_at"] = args.started_at
        if args.run_dir:
            run_path = pathlib.Path(args.run_dir)
            updates["run_id"] = run_path.name
            updates["run_dir"] = str(run_path)
            eval_path = run_path / "EVAL_REPORT.json"
            eval_data = read_json(eval_path)
            if eval_data:
                updates["eval_score"] = eval_data.get("score")
                updates["eval_verdict"] = eval_data.get("verdict")
        if args.summary:
            updates["summary"] = args.summary
        try:
            report = update_batch_task(batch_dir, args.index, updates)
        except (FileNotFoundError, IndexError) as exc:
            print(f"Failed to record outcome: {exc}", file=sys.stderr)
            return 1
        print(json.dumps(report, indent=2))
        return 0

    if args.command == "batch-finalize":
        batch_dir = pathlib.Path(args.batch_dir)
        if not batch_dir.exists():
            print(f"Batch directory does not exist: {batch_dir}", file=sys.stderr)
            return 1
        try:
            report = finalize_batch(batch_dir, args.status)
        except FileNotFoundError as exc:
            print(f"Failed to finalize batch: {exc}", file=sys.stderr)
            return 1
        print(json.dumps(report, indent=2))
        return 0

    run_dir = pathlib.Path(args.run_dir)
    if not run_dir.exists():
        print(f"Run directory does not exist: {run_dir}", file=sys.stderr)
        return 1

    if args.command == "run":
        results = run_intent(config, args.intent)
        report_path = run_dir / "TEST_REPORT.json"
        existing = read_json(report_path, {"commands": [], "last_intent": None})
        existing.setdefault("commands", [])
        existing["commands"].extend(results)
        existing["last_intent"] = args.intent
        write_json(report_path, existing)
        capture_diff(run_dir)
        print(str(report_path))
        return 0

    if args.command == "diff":
        capture_diff(run_dir)
        print(str(run_dir / "PATCH.diff"))
        return 0

    if args.command == "validate":
        report = validate_policy(run_dir, config)
        print(json.dumps(report, indent=2))
        return 0

    if args.command == "evaluate":
        ensure_regression_stub(run_dir)
        report = evaluate(run_dir, config)
        print(json.dumps(report, indent=2))
        return 0

    if args.command == "prepare-retry":
        report = prepare_retry(run_dir, config, args.reason)
        print(json.dumps(report, indent=2))
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
