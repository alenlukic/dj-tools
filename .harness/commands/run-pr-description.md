# Generate PR Description

DEVDSL-1
MODE: STRICT
FLAGS: NO_EARLY_STOP SCOPE_LOCK(explicit) OUTPUT_SCHEMA(pr_description)

## COMMAND

Generate a high-signal PR description for the current branch.

## INPUT

Optional:
- `base`: base branch to compare against; default `main`
- `output_path`: override output location
- `notes`: free-form context the user wants the agent to consider (e.g. motivation, audience, related issues, things to highlight or downplay)

## SCOPE

Summarize only the changes on the current branch relative to `origin/<base>`.

Do not summarize landed merge results.
Do not expand beyond the current branch diff.

## DO

1. Validate repo state
- use the `PR Description Generator` agent
- identify the current branch
- fetch `origin`
- confirm `origin/<base>` exists

2. Initialize output
- default: `.harness/pr_descriptions/${CURRENT_BRANCH}_PR_DESCRIPTION.md`

3. Generate description
- delegate to the `PR Description Generator` agent
- if `notes` were provided, pass them to the agent as additional context
- ensure the output separates what changed, why it matters, and where reviewers should focus
- suppress file-by-file narration

## VALIDATION

Before completion, verify:
- `origin` was fetched
- `origin/<base>` exists
- description is based on current branch vs `origin/<base>`
- output is high-signal and human-readable
- output file was written successfully

## OUTPUT

Produce:
- `.harness/pr_descriptions/${CURRENT_BRANCH}_PR_DESCRIPTION.md` unless overridden
- concise completion summary including:
  - current branch
  - base branch
  - report path
  - PR classification

## ACCEPTANCE

Complete only if:
- the PR Description Generator agent was used
- description reflects actual branch changes
- output is signal-optimized for human readability
- `PR_DESCRIPTION.md` was successfully written
