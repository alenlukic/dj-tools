# Run Prompt Decomposer

DEVDSL-1
MODE: STRICT
FLAGS: NO_EARLY_STOP SCOPE_LOCK(explicit) OUTPUT_SCHEMA(default)

## COMMAND

Analyze a DEVDSL prompt and either confirm it is atomic or decompose it into a minimal set of well-scoped child prompts.

## INPUT

Required:
- `prompt`: one complete DEVDSL prompt (inline text or path to a file)

Optional:
- `output_dir`: filesystem path to write child prompt files; if omitted, child prompts are emitted as markdown blocks in chat

## SCOPE

Operate only on the provided prompt.

Do not modify the repo, run the pipeline, or implement any work described in the source prompt.

## DO

1. Delegate to the `Prompt Decomposer` agent
   - pass the full source prompt
   - pass `output_dir` if provided

2. Return the result
   - if `decision: no_decompose`: report the decision and rationale
   - if `decision: decompose`: report the manifest and child prompts per the agent output spec

## VALIDATION

Before completion, verify:
- the Prompt Decomposer agent was invoked
- no code changes were made to the repo
- the decomposition decision is explicitly justified
- if decomposed, child prompts are valid DEVDSL-1 and collectively cover the original scope

## OUTPUT

Produce:
- `decision: no_decompose` with rationale, or
- `decision: decompose` with:
  - `child_count`
  - `dependency_summary`
  - manifest of child prompts
  - child prompt files written to `output_dir` (if provided), or child prompt markdown blocks (if omitted)

## ACCEPTANCE

Complete only if:
- the Prompt Decomposer agent was used
- no repo modifications were made
- the decomposition decision is evidence-backed and explicitly stated
- if decomposed, each child prompt is independently executable DEVDSL-1
