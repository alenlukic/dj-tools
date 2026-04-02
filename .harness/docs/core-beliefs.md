# Core Beliefs and Execution Contract

This document is the in-repo source of truth for the platform's execution contract and operating principles.

## Execution Contract (DEVDSL-1.1)

DSL_VERSION: DEVDSL-1.1

All execution tasks must follow DEVDSL syntax.
If not provided, infer safest STRICT defaults.

MODE: STRICT

FLAGS (default):
  NO_EARLY_STOP
  PATCH_ONLY(require_file_read=true)
  TEST_GATE(full, flake_policy=rerun_once, extend_on_new_failure=true)
  SCOPE_LOCK(inferred)
  OUTPUT_SCHEMA(default)
  CONFIRMATION_BLOCK(required=true)

TASK_KIND (optional):
  code_change | ui_change | refactor | audit | prompt_design | ops | pr_description

TASK_KIND defaults:
  code_change:
    MODE=STRICT
    PATCH_ONLY
    TEST_GATE(full)
    EVAL_GATE(metric=quality, threshold=85)

  ui_change:
    MODE=STRICT
    PATCH_ONLY
    TEST_GATE(full)
    UI_BASELINE(affected)
    EVAL_GATE(metric=quality, threshold=85)

  refactor:
    MODE=FLEX
    TEST_GATE(full)
    MINIMALIST_OPT(api_change=false)
    REGRESSION_CHECK(block_on=high)

  audit:
    MODE=STRICT
    TRAVERSE_PROOF(light)
    OUTPUT_SCHEMA(audit)

  prompt_design:
    MODE=STRICT
    OUTPUT_SCHEMA(default)

  pr_description:
    MODE=STRICT
    OUTPUT_SCHEMA(pr_description)

## Macros

NO_EARLY_STOP
  Complete execution cycle unless blocked.

PATCH_ONLY(require_file_read=true)
  Minimal diffs only.
  No full-file rewrites.
  No formatting churn.
  No whitespace-only edits.
  Must read file before patching.
  Output preference: diff > edit blocks > minimal instructions.

SCOPE_LOCK(files=explicit|inferred, allow_adjacent=false, max_files=0)
  Modify only in-scope files.
  If allow_adjacent=true:
    may modify up to max_files additional directly related files.
  Must declare scope expansion before editing.

DISCOVERY(readonly=true)
  Allows read-only inspection outside scope.
  No edits outside scope.

TEST_GATE(mode=full|targeted,
          flake_policy=none|rerun_once|rerun_twice,
          extend_on_new_failure=true|false)
  Run tests.
  If none: "NO TESTS PRESENT".
  Retry cap: 3 per category (tests/build/lint/visual).
  Each attempt:
    cite error
    state 1-sentence hypothesis
    minimal change
  If flake_policy active:
    rerun failing target before counting.
  If extend_on_new_failure=true:
    allow +1 attempt if failure signature changes.
  After cap:
    STOP
    output diagnostic summary
    set next step to information gathering.
  Block completion while failing.

TRAVERSE_PROOF(level=full|light, limit=scope|repo)
  full: list dirs + files + counts.
  light: list files + count.
  Default limit=scope.

UI_BASELINE(views=affected|listed)
  Capture baseline before change.
  After change: check visual drift.
  No unintended layout/spacing/typography regressions.
  Visual failures count under TEST_GATE visual category.

MINIMALIST_OPT(api_change=false, ui_drift=false, evidence_required=false)
  Maximize deletion/simplification.
  Constraints:
    tests pass
    no regression
    no API change unless allowed
    no UI drift unless allowed
  If evidence_required=true:
    require proof before deletions.

ABSTRACT_IF(dupes>=3, indirection<=1)
  Extract shared logic only if thresholds satisfied.

CLARIFY_IF(risk=high)
  May pause for clarification only if:
    destructive migration
    auth/security
    payments/financial logic
    data loss risk
  Must state:
    "BLOCKED BY HIGH-RISK AMBIGUITY: <reason>"

EVAL_GATE(metric=quality, threshold=85, source=EVAL_REPORT.json)
  Completion is blocked until evaluation is produced.
  Threshold must be explicit.
  Verdict below threshold requires bounded remediation or explicit block.

REGRESSION_CHECK(block_on=high|critical, source=REGRESSION_REPORT.json)
  Detect unintended drift outside nominal task scope.
  Completion is blocked on configured severity or higher.

DIFF_PLAN(required=true, source=PATCH.diff)
  After first meaningful diff, perform a second planning pass grounded in actual changes.
  Use this to tighten scope, update risk, and convert findings into targeted remediation work.

RETRY_LOOP(max_rounds=2, strategy=targeted, require_second_pass_plan=true)
  Allowed only after explicit gate failure.
  Each retry must:
    cite failure evidence
    update SECOND_PASS_PLAN.md
    constrain remediation to the minimal set of causes
  No open-ended retries.

PROJECT_CONVENTIONS
  Follow established project patterns.
  Prefer clarity over cleverness.
  Complete implementations only.
  No pseudocode unless requested.

OUTPUT_SCHEMA(schema=default|audit|pr_description)
  Enforce output blocks for the chosen schema.
  If schema=pr_description:
    Output must be exactly one fenced code block containing markdown with:
      ## Overview
      ## Summary of Changes
    No additional text outside the code block.

## Execution Order (default)

  1) Code edits
  2) TEST_GATE
  3) Build/deploy
  4) Visual verification (if applicable)
  5) Lint/format
  6) DIFF_PLAN
  7) EVAL_GATE
  8) REGRESSION_CHECK
  9) Confirmation block

## Stop Conditions

  Stop only if:
    task complete AND tests pass (or waived) AND
    no visual drift AND
    no blocking regressions AND
    eval threshold met AND
    no remaining work AND
    confirmation emitted
  OR retry cap exceeded
  OR hard platform limit reached
  OR CLARIFY_IF triggered

## Confirmation Block (required)

  Files modified
  Lines added/deleted (estimate allowed)
  TEST STATUS
  Scope confirmation
  UI drift status (if applicable)
  Eval score / threshold
  Regression status
  Remaining: empty or next step if blocked

## Priority Order

  1. Explicit DEVDSL task spec
  2. Macro semantics
  3. Scope lock
  4. Test gate
  5. Diff plan
  6. Eval gate
  7. Regression check
  8. Minimalist optimization
  9. Execution order

## Anti-Redundancy

  Do not restate macro behavior in prose.
  Reference macros only.

## Golden Principles

These are the repo-specific operating principles that apply to all agent work:

1. Repository knowledge is the system of record.
   All context an agent needs must be discoverable in-repo. If it is not in the repo, it does not exist for agents.

2. Prefer boring technology.
   Composable, stable, well-documented tools are preferred over novel ones. Agents reason better about well-established patterns.

3. Parse at the boundary, trust inside.
   Validate data shapes at system boundaries. Internal code operates on validated types.

4. Enforce invariants mechanically, not by convention.
   Linters, tests, and structural checks over documentation-only rules.

5. Keep scope narrow.
   Every change should be the smallest coherent unit. Broad rewrites introduce compounding risk.

6. Separate persistent knowledge from ephemeral artifacts.
   Design docs and research belong in .harness/docs/. Run artifacts belong in .harness/runs/.

7. Optimize for agent legibility.
   Code, docs, and structure should be navigable by agents without requiring external context.

8. Capture taste as tooling.
   When a pattern matters, encode it in a linter, test, structural check, or evaluation gate rather than prose.
