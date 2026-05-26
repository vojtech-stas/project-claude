---
title: glossary-critic — adversarial auditor of draft glossary entries against the 5-rule rubric
summary: Reads a draft glossary entry (or path to a staged CLAUDE.md `## Glossary` edit); applies the glossary-critic rubric; emits APPROVE on publishable entries (the generator then opens the trivial-lane PR) and BLOCK with itemized findings the generator can mechanically address; default-conservative when uncertain.
tags: [subagent, critic, gate, glossary-critic]
type: entity
last_updated: 2026-05-26
sources:
  - .claude/agents/glossary-critic.md
  - decisions/0007-vocabulary-glossary-and-grill-me-extension.md
  - decisions/0012-glossary-consolidation-single-tier.md
  - decisions/0005-output-shape-and-slicing-methodology.md
  - decisions/0009-discipline-tightening.md
  - decisions/0011-subagent-quality-framework.md
---

# glossary-critic

The `glossary-critic` subagent is the **adversarial gate for the trivial-lane glossary PR**. It receives a draft glossary entry (typically from [`/glossary-add`](../../../.claude/skills/glossary-add/SKILL.md) or the bulk [`/glossary-fold`](../../../.claude/skills/glossary-fold/SKILL.md) skill), applies the 5-rule rubric, and emits APPROVE (the generator then opens the `hotfix/glossary-<term>` PR with the `trivial` label) or BLOCK (with itemized findings the generator mechanically addresses in a ≤3-round revision loop). Per [ADR-0007](../../../decisions/0007-vocabulary-glossary-and-grill-me-extension.md) D5 as partially superseded by [ADR-0012](../../../decisions/0012-glossary-consolidation-single-tier.md) D4, this critic gates every glossary edit before it reaches the trivial lane.

This entity note is the **canonical full role synthesis** for the glossary-critic subagent. After the T4 knowledge-architecture migration ([ADR-0031](../../../decisions/0031-knowledge-architecture-v2.md) D10 step 4 of 9, PRD #283 slice 3), the operational [`.claude/agents/glossary-critic.md`](../../../.claude/agents/glossary-critic.md) is slated for thinning in PRD #283 slice 6 to carry only the prompt-level operational mechanics (mandatory reading order, rubric trigger lines, output-format pointer, tool boundaries, conduct) and link here for the rubric-criterion full bodies (each shipped as a `docs/current/concepts/rules/gc-*.md` atomic note), the iteration shape, the bootstrap-mode grandfathering policy, and the relationship to sibling critics.

## Role and responsibility

The glossary-critic has two jobs, in strict priority order:

1. **Hard-block** any draft entry that violates a rubric criterion. Emit itemized findings the generator can mechanically address.
2. **Recommend** non-blocking improvements after the verdict body, before the trailer (the canonical `Recommendations` extension per [ADR-0005](../../../decisions/0005-output-shape-and-slicing-methodology.md) D1).

It does NOT write or edit any file (including auto-fixing a malformed entry — mirrors `adr-critic`'s self-restraint per [ADR-0004](../../../decisions/0004-bypass-prevention.md) D1). It does NOT open, close, or label PRs or issues. It does NOT fetch external URLs (rule 4's URL shape check is syntax-only).

## Invocation contract

- **Caller:** the [`/glossary-add`](../../../.claude/skills/glossary-add/SKILL.md) skill (single-entry interactive flow), the [`/glossary-fold`](../../../.claude/skills/glossary-fold/SKILL.md) skill (bulk fold of skill-local vocabulary), or any agent/human via the `Agent` tool with `subagent_type: "glossary-critic"`.
- **Input:** EITHER a draft glossary entry as inline markdown (typical — invoked before the PR is opened) OR a path to a file containing the proposed `CLAUDE.md` Glossary section edit (already-staged case). Plus the round number (1, 2, or 3); if omitted, assume round 1.
- **Output:** the canonical verdict template per [[topics/output-shapes]] — 5-section body (Header → Subject of review → Rubric → Findings → Summary) + optional Recommendations extension + CRITIC trailer. Returned inline to the calling agent (the loop runs before any PR opens).
- **Tool boundaries:** `Read`, `Glob`, `Grep`, `Bash` (read-only `ls decisions/`, `cat decisions/<file>` via Read, `grep` via Grep). NOT authorized: `Write`/`Edit`, PR/issue mutation, agent invocation, WebFetch.

## Iteration shape — ≤3-round APPROVE/BLOCK loop with escalation

Per [ADR-0003](../../../decisions/0003-autonomous-pipeline-with-critics.md) D2 (and matching the four sibling critics byte-for-byte at the contract level), the iteration shape is:

- **Max 3 rounds** of APPROVE/BLOCK.
- Each BLOCK emits an itemized findings list the generator can mechanically address.
- **Round-3 BLOCK escalates** via the `needs-human` label on the draft (or PR-context comment if already staged) AND a clear `@vojtech-stas` mention in the verdict body. The calling agent surfaces the verdict back to the user and does NOT open the PR.

Default-conservative: when uncertain about any rule, BLOCK per [ADR-0009](../../../decisions/0009-discipline-tightening.md) D3. Adversarial mindset (paranoid linguist) is a lens for ordering rubric scrutiny — not a license to invent new failure modes beyond the 5 rules per [ADR-0009](../../../decisions/0009-discipline-tightening.md) D4. A spurious BLOCK costs one round of regeneration; a leaked malformed entry compounds across every future glossary read.

## Rubric

Each linked rule note expands the criterion's What / Why / How-to-check / Examples. The atomic-note layer is the canonical home; the [`glossary-critic.md`](../../../.claude/agents/glossary-critic.md) executable shell (after slice 6 thinning) will quote each criterion's name + one-line trigger only.

1. [[concepts/rules/gc-scope-tagged]] — scope category fits exactly one of (a) project jargon, (b) external standard, (c) common word narrowed (per ADR-0007 D3)
2. [[concepts/rules/gc-no-duplicate]] — term not already present in CLAUDE.md `## Glossary` or `docs/current/concepts/glossary/*.md`
3. [[concepts/rules/gc-canonical-shape]] — definition is exactly one declarative sentence (per ADR-0007 D2)
4. [[concepts/rules/gc-authority-resolvable]] — authority field is non-empty and matches `ADR-NNNN D-X` | URL | `external` (per ADR-0007 D2)
5. [[concepts/rules/gc-citation-threshold]] — term cited ≥3 times across ≥2 of {`decisions/`, `.claude/agents/`, `.claude/skills/`} (per ADR-0012 D2, grandfathering existing entries per D7)

## Bootstrap-mode acknowledgment

This subagent originally shipped in slice 1 of PRD #53 per [ADR-0007](../../../decisions/0007-vocabulary-glossary-and-grill-me-extension.md) D7 and was updated by PRD #111's consolidation slice per [ADR-0012](../../../decisions/0012-glossary-consolidation-single-tier.md) D7. From the merge of the consolidation slice forward, all glossary edits target the `## Glossary` section in `CLAUDE.md` (single tier). Pre-existing scattered "glossary-like" content in `CLAUDE.md` (the Map table, the rule definitions, the I1–I5 list) is NOT subject to `glossary-critic` review — those are different artifacts with their own rubrics (`reviewer`'s R-META etc.). The ~35-entry soft cap on the consolidated glossary (per ADR-0012 D5) is informational, not mechanically enforced. Existing CLAUDE.md glossary entries are grandfathered against rule 5's tightened inclusion threshold per ADR-0012 D7. This acknowledgment matches the bootstrap-mode language pattern established in [`adr-critic`](adr-critic.md) and codified by [ADR-0004](../../../decisions/0004-bypass-prevention.md) D2.

## Relationship to other agents

- **Adversarial critic for** the [`/glossary-add`](../../../.claude/skills/glossary-add/SKILL.md) and [`/glossary-fold`](../../../.claude/skills/glossary-fold/SKILL.md) generators.
- **Sibling critic of** [`reviewer`](reviewer.md), [`prd-critic`](prd-critic.md), [`adr-critic`](adr-critic.md), [`slicer-critic`](slicer-critic.md), [`backlog-critic`](../../../.claude/agents/backlog-critic.md). All 6 critics conform to the same verdict template + CRITIC trailer ([[topics/output-shapes]]).
- **Honors the 6-critic-cap** per [ADR-0008](../../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D7.
- **Aligns with** the mechanical-rubric philosophy per [ADR-0011](../../../decisions/0011-subagent-quality-framework.md) D2 — rule 5's `grep` invocation is the canonical "LLMs cannot bluff past this" check shape.
- **Authority:** [ADR-0007](../../../decisions/0007-vocabulary-glossary-and-grill-me-extension.md) D5 (rubric), [ADR-0012](../../../decisions/0012-glossary-consolidation-single-tier.md) D2 + D4 + D7 (rule 5 + rubric supersession + grandfathering), [ADR-0005](../../../decisions/0005-output-shape-and-slicing-methodology.md) D1 (output shape), [ADR-0009](../../../decisions/0009-discipline-tightening.md) D3/D4 (default-BLOCK + adversarial-mindset bounding).

## Edges

- **part_of:** [[concepts/rules/gc-scope-tagged]]
- **part_of:** [[concepts/rules/gc-no-duplicate]]
- **part_of:** [[concepts/rules/gc-canonical-shape]]
- **part_of:** [[concepts/rules/gc-authority-resolvable]]
- **part_of:** [[concepts/rules/gc-citation-threshold]]
- **related_to:** [[entities/subagents/prd-critic]]
- **related_to:** [[entities/subagents/adr-critic]]
- **related_to:** [[entities/subagents/slicer-critic]]
- **related_to:** [[entities/subagents/reviewer]]
- **part_of:** [[topics/pipeline-stages]]
- **related_to:** [[topics/output-shapes]]
- **related_to:** [[concepts/glossary/critic]]
