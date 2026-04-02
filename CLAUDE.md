# Claude Code Project Memory

Use the repository agent harness.

Read:
- @AGENTS.md
- @.harness/docs/core-beliefs.md

Use the appropriate command under `.harness/commands/`.
Initialize a run before substantive work:
`python3 .harness/bin/pipeline.py start --mode <mode> --task "<task>"`

If `.harness/state/` is missing or stale, run:
`python3 .harness/bin/bootstrap.py scan`
