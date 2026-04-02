# Quality Rubric

Rubric version: 1.0
Reference this file from the Delivery Evaluator agent and any scoring logic.

## Grade bands

| Grade | Range | Gate meaning |
|---|---|---|
| A | 93–100 | Excellent |
| A- | 90–92 | |
| B+ | 87–89 | |
| B | 83–86 | |
| B- | 80–82 | **Pass threshold** |
| C+ | 77–79 | |
| C | 73–76 | Hard-floor cap |
| C- | 70–72 | Conditional threshold |
| D | 60–69 | |
| F | <60 | |

## Hard floors

Apply before grading:

| Condition | Effect |
|---|---|
| Correctness, Reliability, or Security **< 60** | Cap overall at C (73) |
| Correctness, Reliability, or Security **< 40** | Automatic FAIL regardless of overall |

## Delivery categories and weights

| Category | Weight | Key dimensions |
|---|---|---|
| Correctness | 30 | requirement coverage, behavioral correctness, edge cases, regression avoidance, contract preservation |
| Design Quality | 15 | decomposition, cohesion, coupling, interface clarity, locality of reasoning |
| Testability & Verification | 15 | test coverage of changed behavior, test quality, build/lint health, observability |
| Reliability & Operational Safety | 10 | error handling, retry/idempotency, migration safety, failure isolation, logging |
| Security & Data Safety | 10 | authn/authz correctness, input validation, secret handling, least privilege |
| Readability & Maintainability | 10 | naming, control-flow clarity, density, docs usefulness, pattern consistency |
| Change Discipline | 10 | scope control, patch minimality, churn avoidance, artifact hygiene, AC traceability |

## Maintenance/restructure weight shift

When run mode is maintenance or restructure:

| Category | Weight |
|---|---|
| Correctness | 20 |
| Design Quality | 25 |
| Testability & Verification | 10 |
| Reliability & Operational Safety | 5 |
| Security & Data Safety | 5 |
| Readability & Maintainability | 20 |
| Change Discipline | 15 |

## Verdict gates

- **PASS**: overall ≥ 80 (B-) and no hard floor breach below 40
- **CONDITIONAL**: 70–79 and no hard floor breach below 40
- **FAIL**: < 70 or any hard floor category < 40 or hard mechanical block (critical regression, policy violation)

## Score families

**Change Score** — per run. Produced by the Delivery Evaluator agent.
Updated by: every delivery / maintenance / restructure run.

**Module Health Score** — persistent, slow-moving.
Tracked in: `.harness/docs/quality/scorecards/<module>.yaml`
Updated by: scheduled audits, restructure reviews, incident postmortems — **not** individual delivery runs.
Module health update requires: evidence refs + confidence + explicit rationale.

Module categories tracked: Design Quality, Readability, Testability, Reliability, Security.

## Routing rules (informational)

- Module health **A/B**: normal delivery flow
- Module health **C**: delivery + mandatory broad review
- Module health **D/F**: delivery + maintenance follow-up or restructure consideration before major feature work
- Category score low (e.g. Security < 60): escalate to relevant specialist subagent
- Category score trend downward: flag in planning
