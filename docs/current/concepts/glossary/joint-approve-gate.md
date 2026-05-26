---
title: joint-APPROVE gate — both prd-critic and adr-critic must approve before posting
summary: The rule that when a PRD ships with a macro-ADR draft, BOTH prd-critic AND adr-critic must APPROVE before /to-prd posts anything.
tags: [glossary, pipeline, project-jargon, critic, governance]
type: concept
last_updated: 2026-05-26
sources:
  - decisions/0004-bypass-prevention.md
  - CLAUDE.md
---

# joint-APPROVE gate

The **joint-APPROVE gate** is the rule that when `/to-prd` is invoked with a PRD draft that includes a macro-ADR draft alongside it, BOTH the `prd-critic` AND the `adr-critic` must independently APPROVE before `/to-prd` posts either artifact. Per [ADR-0004](../../../decisions/0004-bypass-prevention.md) D1, this is a defense-in-depth mechanism: the PRD critic focuses on product-problem framing; the ADR critic focuses on architectural-decision integrity. A single APPROVE from either critic is insufficient.

**Edges**

- **related-to:** [[concepts/glossary/critic]]
- **related-to:** [[concepts/glossary/adr]]
- **part-of:** [[topics/pipeline-stages]]

## What

When `/to-prd` runs against a draft that names a paired macro-ADR (via the "Pipeline metadata" line at the bottom of the PRD body), it dispatches `prd-critic` and `adr-critic` in parallel against their respective drafts. Both critics emit canonical 5-section verdicts with CRITIC trailers. The skill aggregates:

- **Both APPROVE** → `/to-prd` posts the PRD GitHub Issue AND the new ADR file in the same commit.
- **Either or both BLOCK** → `/to-prd` returns the failure surface (FAILED_RULES from both critics, merged) and does not post.

Each critic runs its own independent ≤3-round APPROVE/BLOCK loop per [ADR-0003](../../../decisions/0003-autonomous-pipeline-with-critics.md) D2. The gate aggregates only the FINAL dispositions; intermediate BLOCKs from one critic do not block the other critic from continuing its own loop. The merged failure surface lists FAILED_RULES from each critic prefixed with the critic name so the generator knows which prose to address.

When the PRD ships WITHOUT a paired macro-ADR (T1 of any 9-step migration plan, for example), only `prd-critic` runs; the gate degenerates to a single-critic decision.

## Why

The joint-APPROVE gate exists because **PRDs and macro-ADRs have different failure modes**, and a single critic optimized for either tends to under-attend the other. PRDs fail by conflating problem with solution; ADRs fail by under-specifying supersession, missing bootstrap-mode disposition, or inconsistency with earlier ADRs. A `prd-critic` rubric tuned for the product-shape concerns naturally has weaker ADR-shape coverage and vice versa.

Forcing BOTH approvals — rather than letting one critic act as the umbrella gate — is the same defense-in-depth principle as the layered R-CLOSES + R-META + R-LOC reviewer rules: each rule covers a slice of the failure surface; the conjunction covers the union. A single-critic gate would create the conflict-of-interest failure mode where the umbrella critic's rubric gradually absorbs the other concern's checks (rubric bloat) and eventually under-attends one side.

## Examples from this project

- **PRD #128 + ADR-0019 (best-practices KB)** — paired draft; both `prd-critic` and `adr-critic` ran in parallel, both APPROVED in round 2.
- **PRD #242 + ADR-0031 (knowledge architecture v2)** — paired draft; the `adr-critic` BLOCKed once on missing supersession explicit by D-ID; both APPROVED in round 2.
- **PRD #245 (T1 migration)** — NO paired ADR (pure execution of ADR-0031); gate degenerated to single-critic `prd-critic` decision per its own ≤3-round loop.

## Anti-patterns

- **Single-critic umbrella gate** — one critic's rubric grows to cover both PRD and ADR concerns; rubric bloat erodes signal quality.
- **Skipping the ADR critic when ADR-content is "tiny"** — small ADRs still need supersession + bootstrap-mode discipline; size is no exemption.
- **Aggregating intermediate BLOCKs** — only final round-3 dispositions matter for the gate; intermediate states are each critic's private loop state.

## Scope

(a) project jargon coined here

## Authority

[ADR-0004](../../../decisions/0004-bypass-prevention.md) D1

## References

- [ADR-0004](../../../decisions/0004-bypass-prevention.md) D1 — canonical joint-APPROVE gate definition.
- [ADR-0003](../../../decisions/0003-autonomous-pipeline-with-critics.md) D2 — generator/critic-pairing principle that justifies layering critics.
- [`.claude/agents/adr-critic.md`](../../../.claude/agents/adr-critic.md) — ADR-specific critic body.
- [`.claude/agents/prd-critic.md`](../../../.claude/agents/prd-critic.md) — PRD-specific critic body.
- [`.claude/skills/to-prd/SKILL.md`](../../../.claude/skills/to-prd/SKILL.md) — orchestration of the joint dispatch.
- [[concepts/glossary/critic]] — the role both gate participants embody.
