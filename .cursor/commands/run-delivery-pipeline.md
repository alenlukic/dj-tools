Run the repo-local delivery pipeline for a coding task.

Arguments:
- task: a plain-English description of the task and requirements

Execution rules:
1. Use the Delivery Supervisor agent.
2. Create a new run directory under `.local/cursor-meta/runs/`.
3. Write `TASK.md` and `PLAN.md`.
4. Delegate implementation to the Coding Agent.
5. Delegate review to the Review Agent.
6. Iterate coder/reviewer until review verdict is APPROVE or max review rounds is reached.
7. Delegate validation to the QA Agent.
8. If QA fails, return to the Coding Agent with the QA findings.
9. End with a concise final summary.

When running verification or collecting artifacts, use:
`python3 .local/cursor-meta/bin/pipeline.py`

Before making substantial edits, prefer a brief plan.
Keep context focused on the relevant files.