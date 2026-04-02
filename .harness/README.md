# Harness

This directory contains the repo-local engine for agentic delivery.

## Purpose

Provide a thin, deterministic layer around model-driven work:
- command allowlist
- run artifact conventions
- retry/eval policy
- lightweight automation for evidence capture

The harness does not replace model reasoning.
It standardizes how work is staged, validated, and recorded.

## Key files

| File | Purpose |
|---|---|
| `pipeline.yaml` | Allowed commands, stages, policy limits, retry gates |
| `bin/pipeline.py` | Deterministic runner and artifact helper |
| `agents/` | Specialized role prompts |
| `commands/` | Repo-local command prompts / workflows |
| `runs/` | Ephemeral task artifacts |

## Typical use

```bash
python3 .harness/bin/pipeline.py start --mode delivery --task "..."
python3 .harness/bin/pipeline.py run --run-dir .harness/runs/<run_id> --intent test
python3 .harness/bin/pipeline.py validate --run-dir .harness/runs/<run_id>
python3 .harness/bin/pipeline.py evaluate --run-dir .harness/runs/<run_id>
```
