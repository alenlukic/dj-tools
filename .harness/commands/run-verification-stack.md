# Run Verification Stack

DEVDSL-1
MODE: STRICT
FLAGS: NO_EARLY_STOP TEST_GATE(full) SCOPE_LOCK(explicit) OUTPUT_SCHEMA(default)

## COMMAND

Run the repo-local verification stack for an existing delivery run.

## INPUT

Required:
- `run_dir`: existing run directory under `.harness/runs/`

## DO

1. Capture current diff
- `python3 .harness/bin/pipeline.py diff --run-dir <run_dir>`

2. Run required intents as needed
- `python3 .harness/bin/pipeline.py run --run-dir <run_dir> --intent test`
- `python3 .harness/bin/pipeline.py run --run-dir <run_dir> --intent build`

3. Validate policy
- `python3 .harness/bin/pipeline.py validate --run-dir <run_dir>`

4. Build verification
- delegate to `Delivery Build Verifier`

5. Evaluation
- `python3 .harness/bin/pipeline.py evaluate --run-dir <run_dir>`
- delegate to `Delivery Evaluator`

6. Regression detection
- delegate to `Delivery Regression Detector`

## ACCEPTANCE

Complete only if:
- `PATCH.diff` is current
- `TEST_REPORT.json` exists
- `POLICY_REPORT.json` exists
- `EVAL_REPORT.json` exists
- `REGRESSION_REPORT.json` exists
