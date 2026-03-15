Run the repo-local maintenance pipeline.

Arguments:
- scope: the target area, package, module, or maintenance objective

Execution rules:
1. Use the Maintenance Agent.
2. Create a new run directory under `.local/cursor-meta/runs/`.
3. Write a short maintenance scope note.
4. Make narrow, low-risk maintenance changes only.
5. Run relevant verification via:
   `python3 .local/cursor-meta/bin/pipeline.py`
6. Write `MAINTENANCE_REPORT.md`.
7. End with a concise summary of changes, verification, and risk.

Keep changes scoped.
Avoid opportunistic rewrites.