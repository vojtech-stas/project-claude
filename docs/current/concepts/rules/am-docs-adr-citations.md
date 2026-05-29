---
title: AM-DOCS-ADR-CITATIONS — audit-meta docs check, ADR citations in any tracked .md resolve (DOCS-7)
summary: The audit-meta docs-subcommand mechanical check that every [ADR-NNNN](decisions/NNNN-*.md) citation in any tracked .md file resolves to an existing file — repo-wide dangling-link detector beyond just decisions/README.md. Fake-example slugs in rule-body atomic notes are allowlisted via slug-shape regex.
tags: [rule, audit-meta-rubric, docs]
type: concept
last_updated: 2026-05-29
sources:
  - .claude/skills/audit-meta/SKILL.md DOCS-7
  - decisions/0017-audit-meta-consolidation.md D3
---

# AM-DOCS-ADR-CITATIONS

**AM-DOCS-ADR-CITATIONS** is the [`/audit-meta`](../../entities/skills/audit-meta.md) `--docs` subcommand check (DOCS-7) that enforces every ADR citation of the canonical form `[ADR-NNNN](decisions/NNNN-*.md)` in any tracked `.md` file resolves to an existing file per [ADR-0017](../../../decisions/0017-audit-meta-consolidation.md) D3.

Where [AM-DOCS-ADR-INDEX](am-docs-adr-index.md) (DOCS-1/DOCS-2) checks the `decisions/README.md` index specifically, this check is **repo-wide** — it catches dangling ADR links wherever they appear: CLAUDE.md, subagent bodies, skill bodies, other ADRs, future PRDs.

## What

The check fires under the `docs` subcommand. Mechanics:

- Extract every link target matching `decisions/[0-9]{4}-[a-z0-9-]+\.md` from any tracked `.md` file (excluding `.git/`).
- Filter out **fake-example slugs** that match the shape `decisions/00[0-9]{2}-(old-name|fictional|fictional-adr|new-adr|new-decision)\.md` — these slug shapes are never real per project convention (real ADR slugs are kebab-case descriptive nouns, not generic placeholders). This allowlist prevents rule-body atomic notes from triggering false positives when they illustrate the check with examples.
- For each remaining extracted target, run `test -f`.
- If all targets exist → **PASS**.
- If any target is missing → **FAIL** (list the dangling citation(s) with their source file).

The extraction pattern matches the canonical citation shape `decisions/NNNN-kebab-slug.md`. Citations that diverge from this shape (e.g., `decisions/0011_subagent_quality.md` with underscores) won't be extracted, but they would also fail STRUCT-8 naming, so they're caught upstream.

## Why

ADR references propagate aggressively through the codebase: subagent bodies cite ADRs as authority for their rubrics; skill bodies cite ADRs for their conventions; CLAUDE.md cites ADRs for cross-cutting rules; other ADRs cite predecessors and supersession chains. A dangling citation here means:

- A reader chasing the authority for a rule hits a 404 and loses trust in the doc.
- An agent reading its own subagent body cannot ground its behavior in the ADR.
- The supersession chain breaks silently when an old ADR is referenced after consolidation deleted it.

This is the **broadest** dangling-link check in the docs rubric (repo-wide vs the DOCS-1 narrow scope), and the most likely to surface long-tail drift after ADR renames or consolidations.

The fake-example allowlist (slug-shape regex) is necessary because rule-body atomic notes like this one intentionally embed illustrative slug strings (e.g., `0007-old-name.md`, `0099-fictional.md`) in their Examples sections. These strings match the extraction pattern but do not represent real ADR citations — they are pedagogical text. The slug-shape filter (generic placeholders: `old-name`, `fictional`, `fictional-adr`, `new-adr`, `new-decision`) is belt-and-suspenders alongside the source-file filter. Real ADR slugs are descriptive kebab nouns — `vocabulary-glossary-and-grill-me-extension`, `windows-gitbash-hardening`, `knowledge-architecture-v2` — never one of the reserved placeholder words.

## How to check

When `--docs` is active:

1. Find every tracked `.md` file (excluding `.git/`).
2. For each, extract all `decisions/[0-9]{4}-[a-z0-9-]+\.md` link targets.
3. Filter out targets matching `decisions/00[0-9]{2}-(old-name|fictional|fictional-adr|new-adr|new-decision)\.md`.
4. For each remaining unique target, run `test -f`.
5. PASS if all exist; FAIL with the (source-file, dangling-target) list otherwise.

## Examples

- **Every ADR citation across the repo resolves to an existing file** → DOCS-7 PASS.
- **`CLAUDE.md` cites `decisions/0099-fictional.md`** → DOCS-7 PASS (fake-example slug allowlisted by shape regex).
- **A rule-body atomic note uses `decisions/0007-old-name.md` as a pedagogical example** → DOCS-7 PASS (fake-example allowlisted).
- **A subagent body still references `decisions/0007-vocabulary-glossary-and-grill-me-extension.md` and that file exists** → DOCS-7 PASS.
- **A markdown file in `docs/` has a citation to a deleted ADR with a real descriptive slug** → DOCS-7 FAIL.
- **A rule references `decisions/0026-knowledge-architecture-truth-docs.md` and that file exists** → DOCS-7 PASS.
- **A rule referenced `decisions/0026-knowledge-architecture-truth-docs.md` but the file was previously cited with an incorrect slug** → DOCS-7 FAIL before the slug is corrected; PASS after correction (real dangling citation; not a fake-example slug).

## Edges

- **part_of:** [[entities/skills/audit-meta]]
- **related_to:** [[concepts/rules/am-docs-adr-index]]
- **related_to:** [[concepts/rules/am-docs-supersession-notes]]
