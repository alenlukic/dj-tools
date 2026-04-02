#!/usr/bin/env bash
set -euo pipefail

# Create .cursor/ symlinks for Cursor IDE compatibility.
# Run once after clone from the repo root:
#   bash .harness/bin/setup.sh

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO_ROOT"

mkdir -p .cursor

ln -sfn ../.harness/agents .cursor/agents
ln -sfn ../.harness/commands .cursor/commands
ln -sfn ../.harness/rules .cursor/rules

echo "Cursor symlinks created:"
echo "  .cursor/agents   -> .harness/agents/"
echo "  .cursor/commands -> .harness/commands/"
echo "  .cursor/rules    -> .harness/rules/"
