# Run Repo Research

DEVDSL-1
MODE: STRICT
FLAGS: NO_EARLY_STOP SCOPE_LOCK(explicit) TRAVERSE_PROOF(required) OUTPUT_SCHEMA(default)

## COMMAND

Run a general repository research pass for a natural-language question.

## INPUT

Required:
- `question`: plain-English repo research question

Optional:
- `scope_paths`: comma-separated paths to constrain initial traversal
- `output_path`: override report location

## SCOPE

Perform read-only repo research to answer the provided question.

Do not modify code.
Do not perform maintenance, refactoring, or implementation.
Do not broaden scope beyond what is required to answer correctly.

## DO

1. Initialize
- use the `Research Analyst` agent
- if no explicit output path is provided, write to:
  - `.harness/docs/design-docs/REPO_RESEARCH_REPORT.md`

2. Research
- interpret the question
- determine the minimum viable traversal plan
- inspect relevant code, configs, interfaces, docs, and adjacent boundaries
- expand scope only when needed to validate dependencies, workflows, or architecture

3. Synthesize
- answer the question directly
- produce the most useful primary artifact in the `Requested View` section, such as:
  - ASCII dependency tree
  - ASCII workflow diagram
  - subsystem map
  - categorized inventory
  - implementation trace

4. Finalize
- write the report using the standard repo research output specification
- end with a concise completion summary including:
  - question answered
  - report path
  - scope examined
  - confidence level

## VALIDATION

Before completion, verify:
- the task remained read-only
- the question was answered directly
- traversal was sufficient, not superficial
- the standard output spec was used
- the `Requested View` artifact matches the nature of the question
- uncertainty was stated where evidence was incomplete

## OUTPUT

Produce:
- `.harness/docs/design-docs/REPO_RESEARCH_REPORT.md` unless overridden
- concise completion summary including:
  - question
  - report path
  - key scope examined
  - confidence

## ACCEPTANCE

Complete only if:
- the Research Analyst agent was used
- no code changes were made
- the report uses the standard repo research output specification
- the result is high-signal and evidence-backed
- the primary requested artifact is included in `Requested View`
