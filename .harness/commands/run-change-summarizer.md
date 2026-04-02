# Summarize Merged Change

DEVDSL-1
MODE: STRICT
FLAGS: NO_EARLY_STOP SCOPE_LOCK(explicit) TRAVERSE_PROOF(required) OUTPUT_SCHEMA(default)

## COMMAND

Run the change summarization pipeline for a merged PR.

## INPUT

Required:
- `merge_commit`: merge commit SHA to summarize

Optional:
- `output_path`: override output location for the summary report

## SCOPE

Summarize only the merged change represented by the provided merge commit.

Source of truth:
- landed change set = `MERGE_COMMIT^1..MERGE_COMMIT`

Do not switch to branch-wide or non-merge summarization if the input is invalid.

## DO

1. Validate input
- use the `PR Change Summarizer` agent
- confirm the commit exists
- confirm it is a merge commit
- stop and report invalid input if it is not

2. Initialize output location
- default output path:
  - `.harness/change_summaries/${MERGE_COMMIT}_PR_CHANGE_SUMMARY.md`

3. Analyze landed change
- inspect the landed diff from first parent to merge commit
- identify functionality added, edited, and removed
- analyze broader repo impact
- detect whether architecture changed materially

4. Architectural reporting
- include an ASCII system diagram when architecture was moderately or fundamentally reshaped
- especially highlight introduced or removed components

5. Finalize
- write the summary report
- end with a concise completion summary including:
  - commit summarized
  - output path
  - architectural classification
  - confidence level

## VALIDATION

Before completion, verify:
- merge-commit validation succeeded
- the summary is based on landed code
- added / edited / removed are separated
- broader repo impact is analyzed
- ASCII diagram is present only when warranted
- output file was written successfully

## OUTPUT

Produce:
- `.harness/change_summaries/${MERGE_COMMIT}_PR_CHANGE_SUMMARY.md` unless overridden
- concise completion summary including:
  - summarized commit
  - report path
  - impact classification
  - confidence

## ACCEPTANCE

Complete only if:
- the PR Change Summarizer agent was used
- input commit was validated as a merge commit
- landed merge result was the analysis basis
- broader impact is included, not just change listing
- ASCII diagram is included when architecture changed materially
- output is high-signal and human-readable
