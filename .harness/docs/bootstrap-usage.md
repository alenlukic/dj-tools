# Bootstrap Usage Guide

## Quick Start

```bash
# Scan the repo and generate state files
python3 .harness/bin/bootstrap.py scan

# Review what docs updates are proposed
python3 .harness/bin/bootstrap.py plan

# Apply approved/high-confidence changes
python3 .harness/bin/bootstrap.py apply

# Verify everything is consistent
python3 .harness/bin/bootstrap.py doctor
```

## Subcommands

### `scan`

Full repo traversal. Detects manifests, docs, scripts, framework markers, instruction surfaces, and entrypoints. Writes all state files under `.harness/state/`.

```bash
python3 .harness/bin/bootstrap.py scan
python3 .harness/bin/bootstrap.py scan --repo-root /path/to/repo
```

Does NOT modify any user-facing docs. Safe to run at any time.

**Output files:**
- `.harness/state/repo-profile.yaml`
- `.harness/state/repo-inventory.json`
- `.harness/state/module-map.yaml`
- `.harness/state/command-registry.json`
- `.harness/state/docs-sync-state.json`
- `.harness/state/pending-doc-updates.yaml`
- `.harness/docs/quality/findings/open-items.yaml`

### `plan`

Compares inferred state to current instruction surfaces and computes proposed doc updates. Writes to `pending-doc-updates.yaml`.

```bash
python3 .harness/bin/bootstrap.py plan
```

### `apply`

Applies queued changes that meet auto-apply criteria:
- confidence >= 0.85
- target section has generated markers
- no duplicate-source conflict
- no high-risk domain touched
- no unresolved blocking finding

Changes that don't meet all criteria remain in the queue.

```bash
python3 .harness/bin/bootstrap.py apply
```

### `sync`

Incremental drift detection. Compares current repo state to previous scan and queues updates for any differences found.

```bash
python3 .harness/bin/bootstrap.py sync
```

### `doctor`

Validates:
- All expected state files exist
- Command registry references point to real files
- Generated marker integrity (matched BEGIN/END, no nesting)
- No duplicate truth (same section_id in multiple surfaces)
- Module map paths exist on disk

```bash
python3 .harness/bin/bootstrap.py doctor
```

## Generated Section Markers

All generated doc content uses explicit markers:

```markdown
<!-- BEGIN GENERATED: <section-id> source=<path> generated_at=<iso-timestamp> confidence=<0.0-1.0> edit_policy=preserve-manual -->
content here
<!-- END GENERATED: <section-id> -->
```

**Rules:**
- Content inside markers is machine-managed — will be overwritten on next apply
- Content outside markers is manual — preserved byte-for-byte, never touched
- To prevent a section from being auto-updated, remove the markers (making it manual)

## State Files

| File | Purpose |
|---|---|
| `repo-profile.yaml` | Canonical repo profile with confidence scores |
| `repo-inventory.json` | Raw traversal data |
| `module-map.yaml` | Module/workspace boundaries |
| `command-registry.json` | Known commands with evidence |
| `docs-sync-state.json` | Tracks generated section hashes |
| `pending-doc-updates.yaml` | Queued proposed changes |

## Architecture

The bootstrap tool is structured as:
- `bootstrap.py` — thin CLI dispatcher
- `_discovery.py` — repo traversal and inference
- `_state.py` — state model read/write
- `_merge.py` — generated-section marker model
- `_validate.py` — doctor checks and validation
