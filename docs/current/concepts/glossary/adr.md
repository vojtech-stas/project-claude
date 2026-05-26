---
title: ADR — Architecture Decision Record
summary: An Architecture Decision Record stored as `decisions/NNNN-<slug>.md`, immutable after acceptance and superseded by a new ADR rather than edited in place.
tags: [glossary, architecture, external-standard, decisions]
type: concept
last_updated: 2026-05-26
sources:
  - decisions/README.md
  - decisions/0001-foundational-design.md
  - CLAUDE.md
---

# ADR

An **ADR** (Architecture Decision Record) is a numbered, dated, immutable file under [`decisions/`](../../../decisions/) capturing ONE architectural decision: the context that forced it, the decision itself (one or more `D-N:` numbered claims), the alternatives considered, and the consequences. ADRs are the project's authoritative source of truth for architectural state — when CLAUDE.md, a skill body, or a subagent body conflicts with an ADR, the ADR wins.

**Edges**

- **related-to:** [[concepts/glossary/bootstrap-mode]]
- **related-to:** [[concepts/glossary/prd]]
- **part-of:** [[topics/decisions]]

## What

An ADR is a Markdown file named `decisions/NNNN-<kebab-slug>.md` where `NNNN` is a zero-padded monotonic integer assigned at acceptance time. Each ADR follows the project's adopted template (context → decision → alternatives → consequences) and embeds one or more numbered decision claims (`D-1`, `D-2`, …) that downstream artifacts cite by `D-ID`.

ADRs are **immutable** after the PR that introduced them merges. Subsequent changes happen via **supersession**: a new ADR is written, and the old ADR gets a single-line "Superseded by ADR-NNNN" note (the only post-merge edit permitted per [`decisions/README.md`](../../../decisions/README.md)). This append-only history preserves the audit trail: future readers see exactly what was decided when, what alternatives were rejected, and which subsequent decisions revised it.

New ADRs in this project are surfaced via the joint-APPROVE gate when shipped alongside a PRD per [ADR-0004](../../../decisions/0004-bypass-prevention.md) D1, and via the R-META reviewer rule (every new `decisions/NNNN-*.md` file must show subagent provenance through a `Closes #N` link or a `Co-Authored-By: Claude` commit trailer per [ADR-0004](../../../decisions/0004-bypass-prevention.md) D4).

## Why

ADRs exist because **architectural decisions decay in private memory**. Without a written record, the same alternative gets reconsidered six months later; the original constraints that forced the decision get forgotten; new contributors re-litigate settled questions. The ADR-as-permanent-record pattern is the standard answer (Michael Nygard's 2011 essay; widely adopted across the industry) and binds the project's autonomous pipeline together: `adr-critic` judges ADR drafts, `prd-critic` enforces that PRDs cite the ADRs they execute, and the reviewer's R-META rule prevents new ADRs from landing through main-agent meta-output bypass paths.

The immutability rule is the load-bearing half. Mutable ADRs would defeat their own purpose — a reader could not trust that what the ADR says today is what it said when the cited downstream work shipped. Supersession-by-new-ADR keeps the historical record intact while still permitting the architecture to evolve.

## Examples from this project

- **[ADR-0001](../../../decisions/0001-foundational-design.md)** — the foundational ADR that established the supersession discipline (D8) and the `decisions/` directory layout.
- **[ADR-0031](../../../decisions/0031-knowledge-architecture-v2.md)** — the grandparent of this slice's parent PRD #245; sequences a 9-PRD migration program to realize second-brain architecture v2.
- **[ADR-0009](../../../decisions/0009-discipline-tightening.md)** — supersedes [ADR-0004](../../../decisions/0004-bypass-prevention.md) D4's enumerated-path scope (D1) and supersedes [ADR-0006](../../../decisions/0006-backlog-and-session-continuity.md) D4's discretionary phrasing (D2) — a textbook supersession-via-new-ADR pattern.

## Anti-patterns

- **Editing an accepted ADR in place.** Defeats immutability; the reader can no longer trust the historical record. Write a new ADR that supersedes it instead.
- **ADR that decides nothing.** Pure description without a numbered `D-N:` claim — there's nothing for downstream artifacts to cite. The `adr-critic` rubric BLOCKs.
- **Multi-decision ADR without numbered D-IDs.** Forces downstream consumers to cite "ADR-NNNN" without a specific decision — ambiguous and brittle when the ADR is later partially superseded.

## Scope

(b) external standard adopted

## Authority

[`decisions/README.md`](../../../decisions/README.md) "What an ADR is"

## References

- [`decisions/README.md`](../../../decisions/README.md) — canonical project policy for ADR shape, immutability, and supersession.
- [ADR-0001](../../../decisions/0001-foundational-design.md) D8 — supersession-via-new-ADR rule.
- [ADR-0004](../../../decisions/0004-bypass-prevention.md) D1 — joint-APPROVE gate for ADRs shipped alongside PRDs.
- [ADR-0004](../../../decisions/0004-bypass-prevention.md) D4 — R-META subagent-provenance requirement on new ADR files.
- [`.claude/agents/adr-critic.md`](../../../.claude/agents/adr-critic.md) — the critic that judges ADR drafts.
- Michael Nygard, "Documenting Architecture Decisions" (2011): https://www.cognitect.com/blog/2011/11/15/documenting-architecture-decisions
