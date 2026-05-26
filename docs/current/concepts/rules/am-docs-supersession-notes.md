---
title: AM-DOCS-SUPERSESSION-NOTES — audit-meta docs check, decisions/README.md Status column carries "superseded by ADR-NNNN" notes (DOCS-8)
summary: The audit-meta docs-subcommand mechanical check that for every ADR D-ID carrying a supersession header, the decisions/README.md Status column has the matching "superseded by ADR-NNNN" annotation.
tags: [rule, audit-meta-rubric, docs]
type: concept
last_updated: 2026-05-27
sources:
  - .claude/skills/audit-meta/SKILL.md DOCS-8
  - decisions/0017-audit-meta-consolidation.md D3
---

# AM-DOCS-SUPERSESSION-NOTES

**AM-DOCS-SUPERSESSION-NOTES** is the [`/audit-meta`](../../entities/skills/audit-meta.md) `--docs` subcommand check (DOCS-8) that enforces the `decisions/README.md` Status column carries an explicit "superseded by ADR-NNNN" annotation for every ADR D-ID whose body declares a `Supersedes:` header. Per [ADR-0017](../../../decisions/0017-audit-meta-consolidation.md) D3.

Emits WARN (not FAIL) on missing annotation — the supersession chain in the ADR bodies themselves is the source of truth; the README annotation is a discoverability convenience that lags by convention.

## What

The check fires under the `docs` subcommand. Mechanics:

- Enumerate every `Supersedes:` header across `decisions/*.md` ADR files; extract each superseded D-ID (e.g., "ADR-0004 D4 superseded by ADR-0009 D1" → superseded = `ADR-0004 D4`, superseder = `ADR-0009`).
- For each superseded D-ID, grep the `decisions/README.md` Status column for the literal `superseded by` annotation referencing the superseder.
- If all annotations are present → **PASS**.
- If any are missing → **WARN** (list the missing annotations with their canonical superseder).

The WARN level reflects that supersession is **dual-tracked**: the ADR body has the authoritative declaration (`Supersedes:` header), and the README index has a discoverability hint. A missing hint reduces discoverability but doesn't invalidate the supersession itself.

## Why

ADR supersession is the project's primary mechanism for evolving decisions without losing history (per [ADR-0001](../../../decisions/0001-foundational-design.md) D8 immutability rule). Readers landing on a superseded ADR need a clear "this has been replaced by ADR-NNNN" pointer at the top of the file AND in the index, so they don't waste effort treating a deprecated decision as current.

The README annotation is the **discoverability layer**: a reader scanning the index sees "STATUS: superseded by ADR-0009" and skips to the current one without opening the deprecated file. Missing the annotation forces the reader to open every ADR to check its status — death by a thousand clicks at scale.

WARN-level (not FAIL) because:
- The ADR body has the authoritative `Supersedes:` header (source of truth).
- Adding the README annotation is a recurring micro-task that's easy to defer, not a hard contract violation.
- A FAIL here would noise-up the audit on every supersession PR until the README is updated, which is anti-flow.

## How to check

When `--docs` is active:

1. Grep every `decisions/*.md` for `Supersedes:` headers; extract (superseded, superseder) pairs.
2. For each pair, grep `decisions/README.md` Status column for the matching `superseded by` annotation.
3. PASS if all annotations present; WARN with missing-annotation list otherwise.

## Examples

- **Every superseded ADR has a "superseded by ADR-NNNN" Status note in README** → DOCS-8 PASS.
- **ADR-0004 D4 was superseded by ADR-0009 D1 (per ADR-0009's Supersedes header) but README still shows ADR-0004 as "Accepted"** → DOCS-8 WARN.
- **A brand-new supersession landed in this PR; ADR body declares it but README not yet updated** → DOCS-8 WARN (expected; user adds annotation in follow-up).

## Edges

- **part_of:** [[entities/skills/audit-meta]]
- **related_to:** [[concepts/rules/am-docs-adr-index]]
- **related_to:** [[concepts/rules/am-docs-adr-citations]]
