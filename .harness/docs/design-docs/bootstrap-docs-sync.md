# Design Doc: Bootstrap and Docs-Sync System

## Overview

A repo-aware bootstrap and continuous docs-sync system for the agentic delivery harness. Scans the repository, infers normalized state, and manages generated documentation sections with explicit confidence tracking and conservative auto-apply policies.

## State Model

All inferred state lives under `.harness/state/`. These are generated artifacts — safe to delete and regenerate via `bootstrap.py scan`.

### Schema Versioning

Every state file includes a `schema_version` field. Breaking changes to the schema increment this version. Consumers should check version compatibility before reading.

### Files

| File | Format | Purpose |
|---|---|---|
| `repo-profile.yaml` | YAML | Canonical repo profile: name, languages, frameworks, modules, commands, instruction surfaces |
| `repo-inventory.json` | JSON | Raw traversal output: every manifest, doc, script, entrypoint, and framework marker found |
| `module-map.yaml` | YAML | Module/workspace boundaries with ownership, confidence, and evidence |
| `command-registry.json` | JSON | Normalized command catalog with kind, scope, confidence, and evidence |
| `docs-sync-state.json` | JSON | Tracks generated sections: what exists, source fields, content hashes |
| `pending-doc-updates.yaml` | YAML | Queued proposed doc deltas awaiting review or auto-apply |

### Confidence Model

Every inference carries a `confidence` score (0.0–1.0):
- **>= 0.85**: High confidence — eligible for auto-apply
- **0.5–0.84**: Medium — queued for human review
- **< 0.5**: Low — recorded as finding in `open-items.yaml`, not acted on

### Findings

Ambiguities and low-confidence items go to `.harness/docs/quality/findings/open-items.yaml` rather than being guessed. Findings include type, detail, evidence, and confidence.

## Generated-Section Merge Model

### Marker Format

```
<!-- BEGIN GENERATED: <section-id> source=<path> generated_at=<iso> confidence=<0.0-1.0> edit_policy=preserve-manual -->
content
<!-- END GENERATED: <section-id> -->
```

### Merge Rules

1. Content inside markers is machine-managed. Edits inside markers will be overwritten on next `apply`.
2. Content outside markers is manual and preserved byte-for-byte — never touched by the tool.
3. Sections are replaced atomically (entire marker block), not line-merged.
4. New sections are appended; they never reorder existing content.

## Auto-Apply Policy

Auto-apply ONLY when ALL conditions hold:
- confidence >= 0.85
- target section has generated markers (is not manual prose)
- no duplicate-source conflict (same section_id in multiple files)
- no high-risk domain touched (infra, auth, deploy, migration, secrets)
- no unresolved finding blocks the change

Otherwise: queue in `pending-doc-updates.yaml` for human review.

## High-Risk Conservative Treatment

These domains get conservative treatment — lower auto-apply thresholds, explicit findings, and mandatory human review:
- Infrastructure / Terraform
- Secrets / credentials
- Deployment configuration
- Auth / security modules
- Database migrations
- External provider configuration
- Anything documented as source-of-truth in existing repo docs

## Subcommand Model

| Command | Mutates docs? | Mutates state? | Description |
|---|---|---|---|
| `scan` | No | Yes | Full repo traversal; writes all state files |
| `plan` | No | Yes (pending only) | Computes proposed doc updates |
| `apply` | Yes (generated only) | Yes | Applies approved changes |
| `sync` | No | Yes | Incremental drift detection |
| `doctor` | No | Yes (report only) | Validates consistency |

## Design Decisions

1. **State before docs**: Scan always runs first. Docs are never updated without current state.
2. **Queue by default**: Unknown or medium-confidence changes are queued, not applied.
3. **No full-file rewrites**: The system patches generated sections only.
4. **Idempotent scan**: Running scan twice with no repo changes produces identical state.
5. **PyYAML optional**: The system includes a fallback YAML serializer for environments without PyYAML installed.
