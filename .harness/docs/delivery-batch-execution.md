# Delivery Batch Execution

The delivery pipeline supports executing multiple task-definition files in a single invocation via `MODE=multi`. Each task receives a fully isolated delivery run; a batch-level report tracks ordered outcomes.

## Single-Task Example (unchanged)

```
/run-delivery-pipeline
```

Provide the task inline. The pipeline creates one run directory under `.harness/runs/<run_id>/` with standard artifacts.

## Multi-Task Example

```
/run-delivery-pipeline MODE=multi tasks/add-auth.txt tasks/update-api.txt
```

This processes `add-auth.txt` first, then `update-api.txt`. Each gets its own isolated delivery run.

## Ordering Semantics

Task files are processed strictly in the order provided on the command line. The batch report preserves this order via a zero-based `index` field.

## Isolation Semantics

Each task in a batch receives:

- Its own run directory: `.harness/runs/<run_id>/`
- Its own full set of standard delivery artifacts (`TASK.md`, `PLAN.md`, `PATCH.diff`, `REVIEW_NOTES.md`, `QA_REPORT.md`, etc.)
- Independent planning, review, QA, and evaluation cycles

No task reuses planning, review, or implementation context from a prior batch item beyond the normal persisted repo state after previous runs complete.

## Failure Semantics

The default failure policy is **fail-fast** (`on_failure: fail_fast`):

- If a task's delivery run results in an irrecoverable failure (final eval verdict is not PASS), the batch stops immediately.
- All remaining tasks are marked as `skip` in the batch report.
- The batch is finalized with status `failed`.

A future `continue` policy may be added. The batch model supports this without redesign — the `on_failure` field in `BATCH_REPORT.json` controls the behavior.

## Artifact Locations

### Batch directory

```
.harness/runs/batch-<timestamp>/
  BATCH_REPORT.json
```

### Per-task run directories

```
.harness/runs/<run_id_1>/
  TASK.md, PLAN.md, PATCH.diff, TEST_REPORT.json, ...
.harness/runs/<run_id_2>/
  TASK.md, PLAN.md, PATCH.diff, TEST_REPORT.json, ...
```

## BATCH_REPORT.json Schema

```json
{
  "batch_id": "batch-20260402T170000Z",
  "batch_dir": ".harness/runs/batch-20260402T170000Z",
  "started_at": "2026-04-02T17:00:00+00:00",
  "finished_at": "2026-04-02T17:45:00+00:00",
  "status": "complete",
  "on_failure": "fail_fast",
  "tasks": [
    {
      "index": 0,
      "source_file": "tasks/add-auth.txt",
      "task_content": "Add authentication ...",
      "run_id": "20260402T170001Z",
      "run_dir": ".harness/runs/20260402T170001Z",
      "status": "pass",
      "started_at": "2026-04-02T17:00:01+00:00",
      "finished_at": "2026-04-02T17:20:00+00:00",
      "eval_score": 92,
      "eval_verdict": "PASS",
      "summary": "Authentication added successfully"
    },
    {
      "index": 1,
      "source_file": "tasks/update-api.txt",
      "task_content": "Update API endpoints ...",
      "run_id": "20260402T172001Z",
      "run_dir": ".harness/runs/20260402T172001Z",
      "status": "pass",
      "started_at": "2026-04-02T17:20:01+00:00",
      "finished_at": "2026-04-02T17:45:00+00:00",
      "eval_score": 88,
      "eval_verdict": "PASS",
      "summary": "API endpoints updated"
    }
  ]
}
```

### Task status values

| Status | Meaning |
|---|---|
| `pending` | Not yet started |
| `pass` | Delivery run completed successfully |
| `fail` | Delivery run failed irrecoverably |
| `skip` | Not started due to a prior task failure (fail-fast) |

### Top-level batch status values

| Status | Meaning |
|---|---|
| `running` | Batch is currently executing |
| `complete` | All tasks finished successfully |
| `failed` | At least one task failed; remaining were skipped |
| `partial` | Some tasks completed, some failed or were skipped |

## Pipeline Runner Commands

| Command | Purpose |
|---|---|
| `batch-start --task-files f1 f2 ...` | Initialize batch, validate files, create `BATCH_REPORT.json` |
| `batch-record-outcome --batch-dir <dir> --index <N> --run-dir <dir> --status <pass\|fail\|skip>` | Record outcome for one task |
| `batch-finalize --batch-dir <dir> --status <complete\|failed\|partial>` | Mark batch as finished |
