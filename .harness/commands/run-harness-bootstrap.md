# Run Harness Bootstrap

DEVDSL-1
MODE: STRICT
FLAGS: NO_EARLY_STOP SCOPE_LOCK(explicit) OUTPUT_SCHEMA(default)

## COMMAND

Configure the harness for this project's technology stack. Run this after the IDE-specific
bootstrap script has been executed and the repo is ready to use.

The harness is fully functional before this command runs — agents, commands, rules, and docs
are all present. This command wires the project-specific lint/test/build/format commands
into `.harness/pipeline.yaml` and cleans up source-project-specific files.

## INPUT

Optional:
- `tech_stack`: comma-separated list of languages/frameworks (e.g. "Go, Python, React")

If not provided, infer from the repo's files (package.json, go.mod, pyproject.toml, etc.)
or ask the user.

## SCOPE

Modify only:
- `.harness/pipeline.yaml` — replace `true` placeholders with real commands
- `docs/` — stub/remove per MANIFEST `replace` entries
- `.harness/rules/30-client-ui.mdc` — remove per MANIFEST if applicable
- `.harness/docs/design-docs/` — reset per MANIFEST if applicable

Do not modify:
- `AGENTS.md`, `HUMANS.md`, `CLAUDE.md` — these are correct as-is
- `.harness/bin/pipeline.py`, `.harness/agents/`, `.harness/commands/`
- `.harness/docs/core-beliefs.md`, `.harness/docs/quality/`, `.template/`

## DO

### 1. Detect tech stack

Read the repo for stack indicators:
- `go.mod` → Go
- `pyproject.toml` / `setup.py` / `requirements.txt` → Python
- `package.json` → Node.js / JavaScript / TypeScript
- `Dockerfile` → containerized build

Confirm with the user if uncertain or multi-stack.

### 2. Configure .harness/pipeline.yaml commands

Read `.harness/pipeline.yaml`. For each `commands` entry that still contains `true  # configure:`:
- Replace with the actual command(s) for the detected stack
- Support multiple commands per intent (e.g. both Go and Python test commands)
- Keep all other config unchanged (gates, retry, artifacts, policies)

### 3. Clean up source-project files

For each entry in `.template/MANIFEST.yaml` under `replace`:
- If the file/directory exists, remove it
- If a `stub` is provided, write the stub file in its place

### 4. Verify and summarize

Confirm:
- `.harness/pipeline.yaml` has real commands (no remaining `true` placeholders)
- `replace` items were addressed
- No other files were modified

## OUTPUT

Produce a configuration summary:
- Tech stack detected
- Commands configured per intent (lint, test, build, format)
- Files removed / stubbed
- Remaining TODOs if any stack commands could not be inferred

## ACCEPTANCE

Complete only if:
- `.harness/pipeline.yaml` has real commands or the user explicitly accepted leaving some as `true`
- All `replace` items were addressed
- No harness infrastructure files were modified
