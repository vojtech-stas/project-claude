---
title: bootstrap-mode — forward-binding convention rollout policy
summary: The policy that new conventions bind FORWARD from the slice that ships them, with no retroactive sweep across pre-existing artifacts.
tags: [glossary, conventions, project-jargon, governance]
type: concept
last_updated: 2026-05-26
sources:
  - decisions/0004-bypass-prevention.md
  - CLAUDE.md
---

# bootstrap-mode

**Bootstrap-mode** is the project's policy that a newly-introduced convention binds FORWARD from the slice (or PRD) that ships it. Pre-existing artifacts authored before that bootstrap point are NOT retroactively swept to comply; only artifacts created or substantively modified after the convention's introduction must satisfy it.

**Edges**

- **related-to:** [[concepts/glossary/adr]]
- **related-to:** [[concepts/glossary/slice]]
- **part-of:** [[topics/governance]]

## What

When a new convention lands — a new ADR rule, a new reviewer check, a new template shape, a new naming convention — the convention's authority begins at the merge commit of the PR that introduced it. The PR body MAY enumerate a small explicit-sweep set (e.g., "this slice also retitles issues #47 and #57 to the new shape"), but absent that explicit list, the convention applies only to NEW work.

The pattern is used pervasively in this project. Examples from the ADR record:

- [ADR-0004](../../../decisions/0004-bypass-prevention.md) D2 — the canonical bootstrap-mode definition; new R-META requirements bind forward.
- [ADR-0007](../../../decisions/0007-vocabulary-glossary-and-grill-me-extension.md) — new glossary entry shape applies to entries added from acceptance onward; old entries remain in their legacy shape until touched.
- [ADR-0008](../../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D8 — title-naming conventions bind forward (issue #3 onward) with a tiny enumerated sweep (#47 and #57).
- [ADR-0010](../../../decisions/0010-implementer-subagent-auto-pipeline.md) D9 — even within a session, in-flight pipeline runs use the CLAUDE.md they loaded at session start; don't re-read mid-pipeline to pick up freshly-merged updates.

The bootstrap-mode flag is normally stated explicitly in the introducing ADR's text ("binds forward from the merge of slice N"; "no retroactive sweep") and again in the slice body's acceptance criteria.

## Why

Bootstrap-mode exists because **rigorous retroactive sweeps are expensive and dangerous**. Sweeping every pre-existing artifact to match a new convention bloats the introducing PR past the R-LOC cap, multiplies merge-conflict surface, and often surfaces inconsistencies that the new convention itself doesn't fully resolve. Forward-binding scopes the change cleanly: the new convention lives or dies on its merits against new work, and the legacy state gets cleaned up incrementally as old artifacts are touched for other reasons (boy-scout improvements per [ADR-0018](../../../decisions/0018-boy-scout-reviewer-rule.md)).

The policy also stabilizes the autonomous pipeline. Without bootstrap-mode, every new convention would risk invalidating in-flight slices and reopening closed PRs; reviewer would face "this PR was correct yesterday but is wrong today" failure modes. Forward-binding makes convention-introduction a clean cut: yesterday's work stays valid, tomorrow's work obeys the new rule.

## Examples from this project

- **PRD #245 itself is bootstrap-mode'd** — only the 22 terms enumerated in slice 1+2+3 migrate to atomic notes; new terms surfaced by other PRDs go through trivial-lane `/glossary-add` (per the slice body).
- **`adr-critic` rubric** — applies to ADR drafts written from PRD #4 onward; PRD #3's ADRs were not re-judged.
- **R-LOC 300-LoC cap** — applies forward; legacy slices over the cap (e.g., early PRD #3 slices) were not retro-blocked.

## Anti-patterns

- **Silent retroactive sweep** — modifying old artifacts to match a new convention without naming the sweep in the PR body; reviewer cannot judge scope and the sweep becomes invisible to the audit trail.
- **Indefinitely-deferred sweep** — citing bootstrap-mode as cover for never bringing legacy state into compliance, even when the touched-file boy-scout opportunity is right there.
- **Bootstrap-mode flag missing from the introducing ADR** — leaves downstream consumers unsure whether the convention is retroactive; the convention's introducing ADR MUST state the bootstrap-mode disposition explicitly.

## Scope

(a) project jargon coined here

## Authority

[ADR-0004](../../../decisions/0004-bypass-prevention.md) D2

## References

- [ADR-0004](../../../decisions/0004-bypass-prevention.md) D2 — canonical bootstrap-mode definition.
- [ADR-0008](../../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D8 — naming-convention bootstrap example with named exception sweep.
- [ADR-0010](../../../decisions/0010-implementer-subagent-auto-pipeline.md) D9 — in-flight-session bootstrap-mode for CLAUDE.md changes.
- [ADR-0018](../../../decisions/0018-boy-scout-reviewer-rule.md) — the incremental cleanup mechanism that complements bootstrap-mode.
- [CLAUDE.md](../../../CLAUDE.md) "Cross-cutting rules" — multiple rules cite bootstrap-mode explicitly when superseding earlier conventions.
