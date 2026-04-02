#!/usr/bin/env bash
set -euo pipefail

# IDE bootstrap: create .cursor/ symlinks and validate harness structure.
# Run once after clone from the repo root:
#   bash .harness/bin/setup.sh

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO_ROOT"

# --- Cursor symlinks (existing behavior) ---
mkdir -p .cursor

ln -sfn ../.harness/agents .cursor/agents
ln -sfn ../.harness/commands .cursor/commands
ln -sfn ../.harness/rules .cursor/rules

echo "Cursor symlinks created:"
echo "  .cursor/agents   -> .harness/agents/"
echo "  .cursor/commands -> .harness/commands/"
echo "  .cursor/rules    -> .harness/rules/"

# --- Validate expected harness structure ---
MISSING=()
for f in .harness/pipeline.yaml .harness/bin/pipeline.py AGENTS.md; do
  [ -f "$f" ] || MISSING+=("$f")
done
for d in .harness/agents .harness/commands .harness/rules .harness/docs; do
  [ -d "$d" ] || MISSING+=("$d/")
done

if [ ${#MISSING[@]} -gt 0 ]; then
  echo ""
  echo "WARNING: Missing expected files/directories:"
  for m in "${MISSING[@]}"; do
    echo "  - $m"
  done
fi

# --- Bootstrap guidance ---
if [ ! -d ".harness/state" ]; then
  echo ""
  echo "Next steps — repo state not yet initialized:"
  echo "  python3 .harness/bin/bootstrap.py scan    # scan repo and generate state"
  echo "  python3 .harness/bin/bootstrap.py plan    # review proposed doc updates"
  echo "  python3 .harness/bin/bootstrap.py doctor  # verify consistency"
else
  echo ""
  echo "Repo state exists at .harness/state/. To refresh:"
  echo "  python3 .harness/bin/bootstrap.py sync"
fi
