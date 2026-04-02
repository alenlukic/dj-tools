# HUMANS.md

## For humans only

This file is an **operator manual for humans**.

It is **not** the primary runtime instruction surface for agents.

Use it to decide:

- which pipeline to use
- how to initialize a run
- how to write the task contract
- which tool-specific instruction surface should carry the actual agent instructions

Responsibility is split cleanly:

- `HUMANS.md` → human/operator documentation
- `AGENTS.md` → shared agent-facing repository contract
- `.harness/rules/` → scoped rules (symlinked to `.cursor/rules/` for Cursor)
- `.harness/agents/` → agent definitions (symlinked to `.cursor/agents/` for Cursor)
- `.harness/commands/` → pipeline commands (symlinked to `.cursor/commands/` for Cursor)
- `CLAUDE.md` → Claude Code project memory (auto-loaded at project open)
- `.agents/skills/` + `.codex/hooks.json` → Codex-native workflow packaging and deterministic enforcement

Do **not** assume agents will read `HUMANS.md` automatically.
Do **not** use this file as a substitute for the IDE or agent's native instruction-loading surface.

---

## First-time setup

This repository uses the standard agentic delivery harness. All required files for your chosen IDE are in place.

If you are a **new team member** cloning this repo, or need to re-run setup:


| IDE         | Setup                                                          |
| ----------- | -------------------------------------------------------------- |
| Cursor      | `bash .harness/bin/setup.sh` — recreates `.cursor/` symlinks   |
| Claude Code | No setup required — `CLAUDE.md` is auto-loaded at project open |
| Codex       | No setup required                                              |


---

## Purpose

This repository uses an **agentic harness**, not ad hoc one-off prompts.

Every task should enter through the appropriate **pipeline**, create a **run directory immediately**, and include explicit **acceptance criteria**, **non-goals**, and **scope constraints**.

---

## Default entrypoint for any new task

1. Choose the correct pipeline:
  - `delivery` — product/code changes, bug fixes, features
  - `maintenance` — scoped cleanup / hygiene
  - `verification` — run gates on an existing run
2. Start the pipeline using your IDE:
  - **Cursor:** slash command (`/run-delivery-pipeline`, `/run-maintenance-pipeline`, `/run-verification-stack`)
  - **Claude Code / Codex:** provide a structured prompt (see "Standard task brief template" below) and include the run initialization command
3. Provide the task contract: what to do, acceptance criteria, and non-goals.

---

## Which pipeline to use


| Pipeline      | When to use                                               | Cursor                      | Claude Code / Codex                                  |
| ------------- | --------------------------------------------------------- | --------------------------- | ---------------------------------------------------- |
| Delivery      | Bug fixes, features, behavior changes, API/UI work        | `/run-delivery-pipeline`    | Load `.harness/commands/run-delivery-pipeline.md`    |
| Maintenance   | Low-risk cleanup, hygiene, behavior-preserving refactors  | `/run-maintenance-pipeline` | Load `.harness/commands/run-maintenance-pipeline.md` |
| Verification  | Run build/test/eval/regression on an existing run         | `/run-verification-stack`   | Load `.harness/commands/run-verification-stack.md`   |
| Restructure   | Scoped structural improvement, module reorganization      | `/run-restructure-pipeline` | Load `.harness/commands/run-restructure-pipeline.md` |
| Repo research | Read-only codebase exploration and architecture questions | `/run-repo-research`        | Load `.harness/commands/run-repo-research.md`        |


CLI (any IDE): `python3 .harness/bin/pipeline.py start --mode <delivery|maintenance|restructure> --task "..."`

---

## Standard task brief template

For Cursor, append this after the slash command. For Claude Code and Codex, use it as the full startup prompt:

```md
Read AGENTS.md and .harness/docs/core-beliefs.md.
Load .harness/commands/run-delivery-pipeline.md.
Initialize a run first: python3 .harness/bin/pipeline.py start --mode delivery --task "<TASK>"

Task: <plain-English task>

Acceptance criteria:
- <criterion 1>
- <criterion 2>

Non-goals:
- <non-goal 1>

Constraints:
- patch-only
- no scope expansion without explicit justification
- preserve unrelated behavior
```

---

## Harness structure

```text
.harness/                         # git-tracked canonical source
├── agents/                       # agent definitions
├── commands/                     # pipeline command definitions
├── rules/                        # scoped rules (.mdc)
├── docs/                         # harness knowledge base
├── pipeline.yaml                 # allowed commands, stages, policy limits
├── bin/
│   ├── pipeline.py               # deterministic runner and artifact helper
│   └── setup.sh                  # Cursor IDE symlink bootstrapper
├── runs/                         # ephemeral run artifacts (gitignored)
├── change_summaries/             # gitignored
└── pr_descriptions/              # gitignored

.cursor/                          # Cursor only — gitignored; created by setup.sh
├── agents/  -> ../.harness/agents
├── commands/ -> ../.harness/commands
└── rules/   -> ../.harness/rules

CLAUDE.md                         # Claude Code only — project memory; auto-loaded
.agents/skills/                   # Codex only — portable workflow skill packages
.codex/                           # Codex only — hooks and config
```


| IDE         | Instruction surface                      | Agent definitions                                | Rules / triggers                               |
| ----------- | ---------------------------------------- | ------------------------------------------------ | ---------------------------------------------- |
| Cursor      | `AGENTS.md` + `.cursor/rules/` (symlink) | `.cursor/agents/` (symlink → `.harness/agents/`) | `.cursor/rules/` (symlink → `.harness/rules/`) |
| Claude Code | `CLAUDE.md` → `AGENTS.md`                | In-context via `AGENTS.md`                       | `.harness/docs/core-beliefs.md`                |
| Codex       | `AGENTS.md`                              | In-context via `AGENTS.md`                       | `.agents/skills/`, `.codex/hooks.json`         |


---

## Bootstrap and Docs Sync

The harness includes a bootstrap system that scans the repo, infers state, and manages generated documentation sections.

### How to bootstrap

```bash
# 1. Scan the repo to generate state files
python3 .harness/bin/bootstrap.py scan

# 2. Review proposed doc updates
python3 .harness/bin/bootstrap.py plan

# 3. Apply approved changes (only generated sections, never manual prose)
python3 .harness/bin/bootstrap.py apply

# 4. Verify everything is consistent
python3 .harness/bin/bootstrap.py doctor
```

### Incremental sync

When the repo evolves, run `sync` to detect drift and queue doc updates:

```bash
python3 .harness/bin/bootstrap.py sync
```

### Generated vs manual docs

Generated sections use explicit markers:

```
<!-- BEGIN GENERATED: <section-id> source=<path> ... -->
content here
<!-- END GENERATED: <section-id> -->
```

Rules:

- Content inside markers is machine-managed — edits will be overwritten on next apply
- Content outside markers is manual and preserved byte-for-byte
- Auto-apply only triggers when confidence >= 0.85 and no high-risk domains are touched
- Low-confidence updates are queued in `pending-doc-updates.yaml` for human review

### IDE instruction surfaces


| Surface            | Purpose                                 | Who reads it  |
| ------------------ | --------------------------------------- | ------------- |
| `AGENTS.md`        | Shared agent-facing repo contract       | All agents    |
| `HUMANS.md`        | Human/operator manual                   | Humans only   |
| `CLAUDE.md`        | Claude Code shim (references AGENTS.md) | Claude Code   |
| `.harness/rules/`  | Scoped rules (Cursor via symlink)       | Cursor agents |
| `.harness/agents/` | Agent definitions                       | All pipelines |


### State files

All state lives under `.harness/state/`. These are generated artifacts — safe to regenerate with `scan`.

For details, see `.harness/docs/bootstrap-usage.md` and `.harness/docs/design-docs/bootstrap-docs-sync.md`.

---

## Human operator checklist

Before starting work:

- choose the correct pipeline mode
- initialize the run immediately
- provide acceptance criteria
- provide non-goals

Before accepting output:

- run artifacts were created
- validation and evaluation ran
- regression checks ran
- any retries were bounded and justified
