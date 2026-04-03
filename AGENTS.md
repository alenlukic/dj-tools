# dj-tools Agent Guide

This repository uses the standard agentic delivery harness — a deterministic, multi-agent
workflow for software delivery with narrow patches, explicit planning, structured review/QA,
eval gates, and bounded remediation.

## Repository

dj-tools is a Python toolkit for DJ library management: ingestion, feature extraction,
harmonic mixing analysis, metadata hydration, and an interactive CLI assistant.
Backed by PostgreSQL via SQLAlchemy.

## Getting Oriented


| What                   | Where                                                          |
| ---------------------- | -------------------------------------------------------------- |
| Operating principles   | [.harness/docs/core-beliefs.md](.harness/docs/core-beliefs.md) |
| Harness knowledge base | [.harness/docs/index.md](.harness/docs/index.md)               |
| Architecture           | [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)                   |
| Conventions            | [docs/CONVENTIONS.md](docs/CONVENTIONS.md)                     |
| Golden principles      | [docs/golden-principles.md](docs/golden-principles.md)         |


## Execution Contract

The execution contract (DEVDSL-1.1) is defined in [.harness/docs/core-beliefs.md](.harness/docs/core-beliefs.md).

Repo-local harness engine:

- allowed commands + policy: [.harness/pipeline.yaml](.harness/pipeline.yaml)
- pipeline runner: `python3 .harness/bin/pipeline.py`
- IDE bootstrap: `bash .harness/bin/setup.sh`

## Subagent Delegation

When running any pipeline, you are the **orchestrator**. Each step that names an agent must be
delegated via `Task(subagent_type="<Agent Name>")`. Do not perform agent work directly — spawn
the named subagent and pass run artifacts as context. Each subagent reads its own definition
from `.harness/agents/` and operates independently.

## Agent Roles

Delivery pipeline agents:


| Agent                        | File                                                                                               | Role                                             |
| ---------------------------- | -------------------------------------------------------------------------------------------------- | ------------------------------------------------ |
| Delivery Supervisor          | [.harness/agents/delivery-supervisor.md](.harness/agents/delivery-supervisor.md)                   | Orchestration, task intake, flow control         |
| Delivery Coder               | [.harness/agents/delivery-coder.md](.harness/agents/delivery-coder.md)                             | Implementation with narrow patches               |
| Delivery Reviewer            | [.harness/agents/delivery-reviewer.md](.harness/agents/delivery-reviewer.md)                       | Diff-focused correctness review                  |
| Delivery Broad Reviewer      | [.harness/agents/delivery-broad-reviewer.md](.harness/agents/delivery-broad-reviewer.md)           | Design and maintainability review                |
| Delivery QA                  | [.harness/agents/delivery-qa.md](.harness/agents/delivery-qa.md)                                   | Requirement-trace validation                     |
| Delivery Build Verifier      | [.harness/agents/delivery-build-verifier.md](.harness/agents/delivery-build-verifier.md)           | Build health verification                        |
| Delivery Diff Planner        | [.harness/agents/delivery-diff-planner.md](.harness/agents/delivery-diff-planner.md)               | Second-pass planning from actual diff + failures |
| Delivery Evaluator           | [.harness/agents/delivery-evaluator.md](.harness/agents/delivery-evaluator.md)                     | Quality scoring and completion gating            |
| Delivery Regression Detector | [.harness/agents/delivery-regression-detector.md](.harness/agents/delivery-regression-detector.md) | Detect unintended drift and adjacent risk        |


Maintenance agents:


| Agent                        | File                                                                                               | Role                         |
| ---------------------------- | -------------------------------------------------------------------------------------------------- | ---------------------------- |
| Maintenance Coder            | [.harness/agents/maintenance-coder.md](.harness/agents/maintenance-coder.md)                       | Scoped refactors and hygiene |
| Maintenance Comment Scrubber | [.harness/agents/maintenance-comment-scrubber.md](.harness/agents/maintenance-comment-scrubber.md) | Remove non-useful comments   |
| Maintenance Reviewer         | [.harness/agents/maintenance-reviewer.md](.harness/agents/maintenance-reviewer.md)                 | Post-maintenance review      |


Restructure, research, and PR agents:


| Agent                    | File                                                                                       | Role                          |
| ------------------------ | ------------------------------------------------------------------------------------------ | ----------------------------- |
| Restructure Coder        | [.harness/agents/restructure-coder.md](.harness/agents/restructure-coder.md)               | Scoped structural improvement |
| Research Analyst         | [.harness/agents/research-analyst.md](.harness/agents/research-analyst.md)                 | Read-only codebase research   |
| PR Change Summarizer     | [.harness/agents/pr-change-summarizer.md](.harness/agents/pr-change-summarizer.md)         | Merge-commit summaries        |
| PR Description Generator | [.harness/agents/pr-description-generator.md](.harness/agents/pr-description-generator.md) | Branch PR descriptions        |


## Pipeline Commands

Commands live in `.harness/commands/`. In Cursor they are available as slash commands via the
`.cursor/commands/` symlink.


| Command              | File                                                                                           | Cursor slash command        |
| -------------------- | ---------------------------------------------------------------------------------------------- | --------------------------- |
| Delivery pipeline    | [.harness/commands/run-delivery-pipeline.md](.harness/commands/run-delivery-pipeline.md)       | `/run-delivery-pipeline`    |
| Verification stack   | [.harness/commands/run-verification-stack.md](.harness/commands/run-verification-stack.md)     | `/run-verification-stack`   |
| Maintenance pipeline | [.harness/commands/run-maintenance-pipeline.md](.harness/commands/run-maintenance-pipeline.md) | `/run-maintenance-pipeline` |
| PR description       | [.harness/commands/run-pr-description.md](.harness/commands/run-pr-description.md)             | `/run-pr-description`       |
| Change summarizer    | [.harness/commands/run-change-summarizer.md](.harness/commands/run-change-summarizer.md)       | `/run-change-summarizer`    |
| Repo research        | [.harness/commands/run-repo-research.md](.harness/commands/run-repo-research.md)               | `/run-repo-research`        |
| Restructure pipeline | [.harness/commands/run-restructure-pipeline.md](.harness/commands/run-restructure-pipeline.md) | `/run-restructure-pipeline` |


## Run Artifacts

Ephemeral run artifacts live under `.harness/runs/<run_id>/`.

Standard artifacts:

- `TASK.md`
- `PLAN.md`
- `PATCH.diff`
- `TEST_REPORT.json`
- `REVIEW_NOTES.md`
- `QA_REPORT.md`
- `BUILD_VERIFICATION.md`
- `POLICY_REPORT.json`
- `EVAL_REPORT.json`
- `REGRESSION_REPORT.json`

Retry / remediation artifacts:

- `SECOND_PASS_PLAN.md`
- `RETRY_TASK.md`
- `RETRY_LOG.jsonl`

## Workflow Defaults

Delivery work uses this default flow:

1. intake + requirements + first plan
2. implementation
3. specific review loop
4. diff-aware second planning pass
5. QA validation
6. broad review
7. build verification
8. policy validation + evaluation + regression detection
9. bounded remediation loop if gates fail
10. finalize with evidence-backed verdict

## Repo State and Bootstrap

The harness includes a repo-aware bootstrap and docs-sync system under `.harness/state/` and `.harness/bin/bootstrap.py`.


| What                | Where                                              |
| ------------------- | -------------------------------------------------- |
| Repo profile        | `.harness/state/repo-profile.yaml`                 |
| Raw inventory       | `.harness/state/repo-inventory.json`               |
| Module map          | `.harness/state/module-map.yaml`                   |
| Command registry    | `.harness/state/command-registry.json`             |
| Docs sync state     | `.harness/state/docs-sync-state.json`              |
| Pending doc updates | `.harness/state/pending-doc-updates.yaml`          |
| Open findings       | `.harness/docs/quality/findings/open-items.yaml`   |
| Bootstrap tool      | `python3 .harness/bin/bootstrap.py <scan           |
| Design doc          | `.harness/docs/design-docs/bootstrap-docs-sync.md` |
| Usage guide         | `.harness/docs/bootstrap-usage.md`                 |


Generated doc sections use explicit markers. See `.harness/docs/bootstrap-usage.md` for the marker model.

## dj-tools Knowledge Base


| Document                                                                                   | Purpose                                 |
| ------------------------------------------------------------------------------------------ | --------------------------------------- |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)                                               | Domain map, layering, dependency rules  |
| [docs/CONVENTIONS.md](docs/CONVENTIONS.md)                                                 | Coding conventions and patterns         |
| [docs/golden-principles.md](docs/golden-principles.md)                                     | Opinionated rules for agent consistency |
| [docs/conventions/devdsl-macros.md](docs/conventions/devdsl-macros.md)                     | DEVDSL macro reference                  |
| [docs/conventions/agent-contract-template.md](docs/conventions/agent-contract-template.md) | Agent prompt contract pattern           |
| [docs/quality/QUALITY_SCORE.md](docs/quality/QUALITY_SCORE.md)                             | Per-module quality grades               |
| [docs/quality/tech-debt-tracker.md](docs/quality/tech-debt-tracker.md)                     | Known technical debt                    |
| [docs/references/index.md](docs/references/index.md)                                       | External dependency guides              |


## Anti-Drift

- Keep working context narrow
- Prefer diff-first review
- Prefer requirement-trace QA
- Prefer artifact handoff over re-deriving context
- Do not broaden scope without declaring it under SCOPE_LOCK

