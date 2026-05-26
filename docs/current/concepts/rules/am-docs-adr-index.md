---
title: AM-DOCS-ADR-INDEX — audit-meta docs check, bidirectional sync between decisions/README.md index and decisions/NNNN-*.md files (DOCS-1 + DOCS-2)
summary: The audit-meta docs-subcommand mechanical check pair enforcing two-way ADR↔README.md sync — DOCS-1 catches dangling index rows (README references missing file) and DOCS-2 catches missing index entries (on-disk ADR not indexed).
tags: [rule, audit-meta-rubric, docs]
type: concept
last_updated: 2026-05-27
sources:
  - .claude/skills/audit-meta/SKILL.md DOCS-1
  - .claude/skills/audit-meta/SKILL.md DOCS-2
  - decisions/0017-audit-meta-consolidation.md D3
---

# AM-DOCS-ADR-INDEX

**AM-DOCS-ADR-INDEX** is the [`/audit-meta`](../../entities/skills/audit-meta.md) `--docs` subcommand check pair enforcing **bidirectional sync** between the `decisions/README.md` index and the actual `decisions/NNNN-*.md` files on disk per [ADR-0017](../../../decisions/0017-audit-meta-consolidation.md) D3:

- **DOCS-1** — every `decisions/NNNN-*.md` link referenced in `decisions/README.md` resolves to an existing file (no dangling index rows).
- **DOCS-2** — every `decisions/NNNN-*.md` on disk has a row in `decisions/README.md` (no missing index entries).

The pair together guarantees the index neither lies (DOCS-1) nor omits (DOCS-2).

## What

The checks fire under the `docs` subcommand. Mechanics:

- **DOCS-1:** extract every `(NNNN-[a-z0-9-]+\.md)` pattern from `decisions/README.md`; for each, run `test -f decisions/<m>`. All PASS → PASS. Any missing → FAIL (list the dangling refs).
- **DOCS-2:** `for f in decisions/[0-9]*.md; do grep -qF "$(basename $f)" decisions/README.md || echo MISSING $f; done` → empty → PASS; non-empty → FAIL (list the missing index entries).

Both checks run a small loop; the cost is negligible (≤30 file checks at current ADR count).

## Why

The ADR index is the **primary discovery surface** for the project's decision history. If the index links to ADRs that no longer exist (DOCS-1), readers chase 404s and lose trust in the index. If the index omits ADRs that DO exist (DOCS-2), readers don't discover them at all — the ADR's authority is silently invisible.

The bidirectional check is essential because the two failure modes have completely different causes:
- **Dangling rows (DOCS-1)** typically come from renaming or deleting an ADR file without updating the index.
- **Missing rows (DOCS-2)** typically come from creating a new ADR file but forgetting the index update (a very common slip when the slice's checklist doesn't enumerate "update decisions/README.md").

Auditing only one direction catches half the drift. Both must pass for the index to be trustworthy.

## How to check

When `--docs` is active:

1. Run DOCS-1: extract index references; check each exists. PASS if all exist; FAIL with dangling-ref list otherwise.
2. Run DOCS-2: iterate on-disk ADRs; check each is mentioned in the index. PASS if all mentioned; FAIL with missing-entry list otherwise.

## Examples

- **README index lists all 30 ADRs; all 30 exist; no extras on disk** → DOCS-1 PASS, DOCS-2 PASS.
- **README index lists `decisions/0099-fictional-adr.md` (no such file)** → DOCS-1 FAIL.
- **`decisions/0030-new-adr.md` exists but isn't in README** → DOCS-2 FAIL.
- **ADR-0011 was renamed but README still references old filename** → DOCS-1 FAIL (dangling) + DOCS-2 FAIL (new name not indexed).

## Edges

- **part_of:** [[entities/skills/audit-meta]]
- **related_to:** [[concepts/rules/am-docs-adr-citations]]
- **related_to:** [[concepts/rules/am-docs-supersession-notes]]
