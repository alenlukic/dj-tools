# Run Delivery Pipeline

DEVDSL-1
MODE: STRICT
FLAGS: NO_EARLY_STOP TEST_GATE(full) SCOPE_LOCK(explicit) OUTPUT_SCHEMA(default)

## COMMAND

Run the repo-local delivery pipeline for a coding task.

## INPUT

Required:
- `task`: plain-English description of the task and requirements

## SCOPE

Execute one scoped delivery run for the provided task using the repo-local delivery pipeline.

Do not expand scope beyond the stated task unless required to satisfy an explicit requirement or unblock correctness.

## DELEGATION

Each numbered step that names an agent must be delegated via `Task(subagent_type="<Agent Name>")`.
You are the orchestrator — do not perform agent work directly.
Pass the run directory path and relevant artifacts as context to each subagent.

## DO

1. Initialize run
- create a new run directory under `.harness/runs/`
- establish the active run context for this task

2. Intake and planning
- use the `Delivery Supervisor` agent
- restate the task into explicit requirements and acceptance criteria
- identify likely relevant files
- write:
  - `TASK.md`
  - `PLAN.md`

3. Implementation
- delegate implementation to the `Delivery Coder` agent
- keep context focused on relevant files
- before substantial edits, prefer a brief plan

4. Specific review loop
- delegate review to the `Delivery Reviewer` agent
- iterate coder/specific-reviewer until one of the following is true:
  - review verdict is `APPROVE`
  - max review rounds configured by the pipeline is reached

5. Diff-aware second pass
- once a meaningful diff exists, delegate to the `Delivery Diff Planner`
- ground the second plan in:
  - `PATCH.diff`
  - review findings
  - current test/build state
- write:
  - `SECOND_PASS_PLAN.md` if remediation or scope tightening is needed

6. QA validation
- delegate validation to the `Delivery QA` agent

7. Broad review
- only after QA verdict is `PASS`, delegate review to the `Delivery Broad Reviewer`
- assess higher-level concerns such as:
  - software design quality
  - maintainability/extensibility
  - repo pattern alignment
  - longer-term implications
  - potential impact on adjacent areas

8. Verification stack
- use `python3 .harness/bin/pipeline.py` to:
  - capture diff
  - run configured test/build intents as needed
  - write `POLICY_REPORT.json`
  - write `EVAL_REPORT.json`
- delegate to:
  - `Delivery Build Verifier`
  - `Delivery Evaluator`
  - `Delivery Regression Detector`

9. Bounded remediation loop
- if any blocking gate fails:
  - QA verdict is `FAIL`
  - build status is `FAIL`
  - policy validation fails
  - eval score is below threshold
  - regression severity is `HIGH` or `CRITICAL`
- then:
  - run `python3 .harness/bin/pipeline.py prepare-retry --run-dir <run_dir>`
  - update `SECOND_PASS_PLAN.md`
  - return only the cited failures to the `Delivery Coder`
  - perform focused remediation
  - repeat verification within configured retry limits

10. Finalize
- end with a concise final summary grounded in produced artifacts

## MODE=multi — Batch Execution

When invoked with `MODE=multi`, the delivery pipeline processes multiple task-definition files sequentially. Each task file receives a fully isolated delivery run. A batch-level summary artifact tracks ordered outcomes.

### Invocation

```
/run-delivery-pipeline MODE=multi task1.txt task2.txt [task3.txt...]
```

### Prerequisites

- At least 2 task-definition files must be provided. Fewer than 2 is a usage error — do not proceed.
- Each file must exist, be a regular file, and contain non-empty text (plain text or markdown).
- Unreadable or empty files cause a clear failure before that task begins.

### Batch Orchestration Flow

1. Validate MODE=multi and at least 2 task files.
2. Initialize the batch:
   ```
   python3 .harness/bin/pipeline.py batch-start --task-files <file1> <file2> [file3...]
   ```
   - Creates `.harness/runs/batch-<timestamp>/` with `BATCH_REPORT.json`
   - All tasks start in `pending` state
   - Outputs the batch directory path
3. For each task file in order (index 0, 1, 2, ...):
   a. Read the task content from `BATCH_REPORT.json` for this index.
   b. Initialize a delivery run:
      ```
      python3 .harness/bin/pipeline.py start --mode delivery --task "<task content>"
      ```
   c. Execute the full delivery pipeline (steps 2–9 above) for this task.
   d. Record the outcome:
      ```
      python3 .harness/bin/pipeline.py batch-record-outcome \
        --batch-dir <batch_dir> --index <N> --run-dir <run_dir> --status <pass|fail>
      ```
   e. If status is `fail` and `on_failure` is `fail_fast` (the default):
      - Mark all remaining tasks as `skip`:
        ```
        python3 .harness/bin/pipeline.py batch-record-outcome \
          --batch-dir <batch_dir> --index <M> --status skip --summary "Skipped due to prior failure"
        ```
      - Finalize the batch as failed:
        ```
        python3 .harness/bin/pipeline.py batch-finalize --batch-dir <batch_dir> --status failed
        ```
      - STOP processing.
4. After all tasks complete successfully, finalize:
   ```
   python3 .harness/bin/pipeline.py batch-finalize --batch-dir <batch_dir> --status complete
   ```
5. Report the batch summary from `BATCH_REPORT.json`.

### Failure Policy

- Default: `fail_fast` — stop after the first irrecoverable task failure and mark remaining tasks as `skip`.
- Future: `continue` policy may be added later. The batch model supports this without redesign.

### Backward Compatibility

Existing single-task `MODE` (no `MODE=multi` flag) continues to follow the standard single-run flow described above. The multi-task path is opt-in and explicit.

## VALIDATION

Before completion, verify:
- a run directory was created
- `TASK.md` and `PLAN.md` exist
- coding, specific review, QA, broad review, build verification, evaluation, and regression detection were all invoked
- retry loops never exceeded configured limits
- verification/artifact collection used the pipeline runner
- eval score and threshold are explicit
- final summary reflects actual outcomes

## OUTPUT

Produce:
- active run directory under `.harness/runs/`
- delivery artifacts generated by the pipeline
- `BUILD_VERIFICATION.md`
- `POLICY_REPORT.json`
- `EVAL_REPORT.json`
- `REGRESSION_REPORT.json`
- `SECOND_PASS_PLAN.md` when retries or scope tightening occurred
- in MODE=multi: batch directory with `BATCH_REPORT.json` mapping each task file to its run
- concise final summary including:
  - verdict
  - changed files
  - tests run
  - specific review status
  - QA status
  - broad review status
  - build status
  - eval status
  - regression status
  - unresolved caveats, if any

## ACCEPTANCE

Complete only if:
- the Delivery Supervisor coordinated the workflow
- context remained narrow and task-scoped
- coder/specific-reviewer loop ran until approval or configured cap
- QA validation was performed
- broad review was performed only after QA passed
- verification used `python3 .harness/bin/pipeline.py`
- build verification was performed
- evaluation was performed and met threshold or was explicitly blocked
- no blocking regression remained
- any failures were either resolved or explicitly documented
- final summary is evidence-backed
