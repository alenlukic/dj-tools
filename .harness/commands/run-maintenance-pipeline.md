# Run Maintenance Pipeline

DEVDSL-1
MODE: STRICT
FLAGS: NO_EARLY_STOP PATCH_ONLY TEST_GATE(full) SCOPE_LOCK(explicit) OUTPUT_SCHEMA(default)

## COMMAND

Run the repo-local maintenance pipeline for one scoped maintenance/refactor task, then perform a dedicated review of the resulting change set.

## INPUT

Required:
- `scope`: target area, package, module, or maintenance objective

Optional:
- `review`: `true` by default; if omitted, perform review

## SCOPE

Execute one scoped maintenance/refactor run for the provided target.

Maintenance work must remain:
- narrow
- low-risk
- behavior-preserving unless explicitly required otherwise
- structurally justified

Do not perform:
- opportunistic rewrites
- unrelated cleanup
- speculative abstraction
- broad architectural changes unless explicitly required by scope

## DELEGATION

Each step that names an agent must be delegated via `Task(subagent_type="<Agent Name>")`.
You are the orchestrator — do not perform agent work directly.
Pass the run directory path and relevant artifacts as context to each subagent.

## DO

1. Initialize run under `.harness/runs/`.
2. Delegate the change to `Maintenance Coder`.
3. Run scoped verification via `python3 .harness/bin/pipeline.py`.
4. Delegate post-maintenance review to `Maintenance Reviewer`.
5. Run policy validation and evaluation.
6. If evaluation or regression gates fail, use bounded remediation with `SECOND_PASS_PLAN.md`.

## ACCEPTANCE

Complete only if:
- maintenance remained narrow
- tests/build were run as appropriate
- policy/eval/regression gates were satisfied or explicitly blocked
