---
title: adr-critic — adversarial auditor of draft ADRs against the 6-criterion rubric + truth-doc flagging
summary: Reads a draft ADR (inline or already-committed); applies the 6-criterion adr-critic rubric (convention compliance, cross-ADR consistency, supersession by D-ID, no scope creep, bootstrap-mode acknowledged, immutability respected); flags affected truth-doc topics; emits APPROVE or BLOCK with itemized findings.
tags: [subagent, critic, gate, adr-critic]
type: entity
last_updated: 2026-05-26
sources:
  - .claude/agents/adr-critic.md
  - decisions/0003-autonomous-pipeline-with-critics.md D2
  - decisions/0004-bypass-prevention.md D1
  - decisions/0005-output-shape-and-slicing-methodology.md D1
  - decisions/0009-discipline-tightening.md D3
  - decisions/0026-truth-docs-and-r-truth-doc-rule.md D2
---

# adr-critic

The `adr-critic` subagent is the **adversarial gate at stage 2.6** of the autonomous pipeline, running alongside [`prd-critic`](prd-critic.md) whenever a macro-ADR is drafted with a PRD. It receives a draft ADR (inline markdown or a path to an already-committed `decisions/NNNN-*.md`), applies the 6-criterion rubric, and emits APPROVE (the calling generator commits the ADR) or BLOCK (with itemized findings the generator mechanically addresses in a ≤3-round revision loop). When a macro-ADR ships alongside a PRD, adr-critic and `prd-critic` form a **joint-APPROVE gate** per [ADR-0004](../../../decisions/0004-bypass-prevention.md) D1 — BOTH must APPROVE before [`/to-prd`](../../../.claude/skills/to-prd/SKILL.md) posts anything.

This entity note is the **canonical full role synthesis** for the adr-critic subagent. After the T4 knowledge-architecture migration ([ADR-0031](../../../decisions/0031-knowledge-architecture-v2.md) D10 step 4 of 9, PRD #283 slice 2), the operational [`.claude/agents/adr-critic.md`](../../../.claude/agents/adr-critic.md) carries only the prompt-level operational mechanics (mandatory reading order, rubric trigger lines, output-format pointer, tool boundaries, conduct) and links here for the rubric-criterion full bodies (each shipped as a `docs/current/concepts/rules/ac-*.md` atomic note in this slice), the iteration shape, the truth-doc-flagging sub-responsibility per [ADR-0026](../../../decisions/0026-truth-docs-and-r-truth-doc-rule.md) D2, and the joint-gate relationship to `prd-critic`.

## Role and responsibility

The adr-critic has three jobs, in strict priority order:

1. **Hard-block** any draft ADR that violates a rubric criterion. Emit itemized findings the generator can mechanically address.
2. **Flag affected truth-doc topics** per [ADR-0026](../../../decisions/0026-truth-docs-and-r-truth-doc-rule.md) D2 as non-blocking Recommendations so the implementer knows which `docs/current/<topic>.md` to regenerate or amend alongside the ADR.
3. **Recommend** other non-blocking improvements after the verdict body, before the trailer (the canonical `Recommendations` extension per [ADR-0005](../../../decisions/0005-output-shape-and-slicing-methodology.md) D1).

It does NOT write or edit any file (including auto-creating a missing ADR — see [AC-SUPERSEDES-BY-D-ID](../../concepts/rules/ac-supersedes-by-d-id.md) sub-check). It does NOT modify any file under `decisions/` — not even to flip a `Status` field; that is the merging tool's job, not the critic's.

## Invocation contract

- **Caller:** the [`/to-prd`](../../../.claude/skills/to-prd/SKILL.md) skill (typically dispatched via [`/ship`](../../../.claude/skills/ship/SKILL.md) stage 2) when a macro-ADR is drafted alongside the PRD, or any agent/human via the `Agent` tool with `subagent_type: "adr-critic"`. May also be invoked retroactively against an already-committed `decisions/NNNN-*.md` for spot review.
- **Input:** EITHER a draft ADR as inline markdown (typical — invoked before the ADR is committed), OR a path to an ADR file at `decisions/NNNN-<slug>.md` (already-committed case) which adr-critic `Read`s in full. Plus the round number (1, 2, or 3); if omitted, assume round 1. If neither inline body nor valid path is supplied → return `INVALID_INPUT: no draft ADR and no path supplied` and stop.
- **Output:** the canonical verdict template per [[topics/output-shapes]] — 5-section body (Header → Subject of review → Rubric → Findings → Summary) + optional Recommendations extension + CRITIC trailer. Either posted as a comment on an ADR-tracking issue via `gh issue comment` if one exists, OR returned inline to the calling agent if the ADR is still a draft.
- **Tool boundaries:** `Read`, `Glob`, `Grep`, `Bash` (read-only `gh issue view/list/comment` + `git log decisions/` + `ls decisions/` — but prefer `gh api repos/{owner}/{repo}/contents/decisions/<file>.md` for ADR existence checks per the stale-worktree mitigation in [AC-SUPERSEDES-BY-D-ID](../../concepts/rules/ac-supersedes-by-d-id.md)). NOT authorized: `Write`/`Edit`, `gh issue create` / `gh issue edit` / `gh issue close`, branch creation, agent invocation, any mutation under `decisions/`.

## Iteration shape — ≤3-round APPROVE/BLOCK loop with escalation

Per [ADR-0003](../../../decisions/0003-autonomous-pipeline-with-critics.md) D2, the iteration shape matches the project's standard critic loop (byte-for-byte at the contract level shared with `prd-critic`, `slicer-critic`, `reviewer`):

- **Max 3 rounds** of APPROVE/BLOCK.
- Each BLOCK emits an itemized findings list the generator can mechanically address.
- **Round-3 BLOCK escalates** via the `needs-human` label on the draft-tracking issue (or the posted ADR-tracking issue if already posted) AND a summary comment on the parent grill-session / PRD context. Mention `@vojtech-stas` in the verdict body.

Default-conservative: when uncertain about any rubric criterion, BLOCK per [ADR-0009](../../../decisions/0009-discipline-tightening.md) D3. A false-positive APPROVE puts an unverified ADR into the accepted-decisions record — high friction to undo once downstream PRDs and slices cite it. A false-negative BLOCK creates a recoverable revision cycle. Adversarial mindset is a paranoid-architect lens for ordering rubric scrutiny — not a license to invent failure modes beyond the 6 rules per [ADR-0009](../../../decisions/0009-discipline-tightening.md) D4.

## Rubric

Each linked rule note expands the criterion's What / Why / How-to-check / Examples. The atomic-note layer is the canonical home; the [`adr-critic.md`](../../../.claude/agents/adr-critic.md) executable shell quotes each criterion's name + one-line trigger only.

1. [[concepts/rules/ac-convention-compliance]] — required ADR sections present and non-empty per `decisions/README.md`
2. [[concepts/rules/ac-cross-adr-consistency]] — no silent contradiction with accepted ADRs without `Supersedes:` header
3. [[concepts/rules/ac-supersedes-by-d-id]] — every `Supersedes:` citation verified to exist and substance-match; also gates the referenced-but-missing ADR sub-check
4. [[concepts/rules/ac-no-scope-creep]] — every Decision serves the ADR's stated theme; off-theme Decisions belong in a separate ADR
5. [[concepts/rules/ac-bootstrap-mode-acknowledged]] — ADRs introducing enforcement must cite ADR-0004 D2 or include explicit bootstrap acknowledgment
6. [[concepts/rules/ac-immutability-respected]] — no proposed edits to existing ADR files; corrections flow through new ADRs

## Truth-doc topic flagging (per ADR-0026 D2)

This is a **non-blocking** responsibility — surfaced in the Recommendations section of the verdict, never as a Rubric rule (the 6-rule rubric count is preserved per the established critic discipline; the 6-critic-cap per [ADR-0008](../../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D7 is honored, not breached).

When auditing a draft ADR that **cites or extends** prior ADRs whose topics already have a materialized truth-doc at `docs/current/<topic>.md` (canonical knowledge surface per [ADR-0026](../../../decisions/0026-truth-docs-and-r-truth-doc-rule.md) D1), adr-critic flags *"this ADR affects topics X, Y"* in the verdict's Recommendations section so the implementer knows which truth-doc(s) to regenerate or amend alongside the ADR. The implementer is bound by CLAUDE.md cross-cutting rule #14 (truth-doc currency) and the reviewer's R-TRUTH-DOC rule mechanically enforces the requirement at PR review time per [ADR-0026](../../../decisions/0026-truth-docs-and-r-truth-doc-rule.md) D5 — adr-critic's flagging makes the topic candidate set visible at ADR-draft time so the implementer doesn't discover the requirement at PR time.

**How to check:** parse the draft for `ADR-NNNN` references; read `.claude/topics.json` (keyword→topic mapping per [ADR-0026](../../../decisions/0026-truth-docs-and-r-truth-doc-rule.md) D4); for each topic with an existing `docs/current/<topic>.md`, check whether any cited ADR appears as a source. Soft-degrade if either is absent (pre-ADR-0026-merge bootstrap state or topic not yet backfilled). Tool budget: 1-2 `Read` calls; honors the read-only critic contract.

**Boundary clarity:** flagging is adr-critic's job; deciding which truth-doc to actually amend (or whether to ship a NEW truth-doc) is the implementer's judgment per [ADR-0026](../../../decisions/0026-truth-docs-and-r-truth-doc-rule.md) D2 + OQ-7. Do NOT propose specific truth-doc edits; do NOT BLOCK if the implementer's slice plan omits a truth-doc edit (that is R-TRUTH-DOC's job at PR review time).

## Joint-APPROVE gate with prd-critic

When `/to-prd` drafts a macro-ADR alongside the PRD (per [ADR-0003](../../../decisions/0003-autonomous-pipeline-with-critics.md) D8 macro-ADR placement), adr-critic and [`prd-critic`](prd-critic.md) form a **joint-APPROVE gate** per [ADR-0004](../../../decisions/0004-bypass-prevention.md) D1: BOTH must APPROVE before `/to-prd` posts anything. Either BLOCK gates publication. The two critics run in parallel (no ordering); each scores its own rubric independently. The joint gate exists because PRD-level concerns (scope, appetite, non-goals) and ADR-level concerns (convention compliance, cross-ADR consistency, supersession) are orthogonal — and either failure mode would silently ship if only one critic gated.

## Open-question → captured issue convention

When an Open question surfaces during ADR review that warrants future-PRD treatment, adr-critic MUST create a `captured`-labeled GitHub Issue to track it and immediately invoke `/promote-to-backlog <N>` per [ADR-0008](../../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D3 inline-firing convention. Mandatory per CLAUDE.md rule #11; the autopilot's [`backlog-critic`](../../../.claude/agents/backlog-critic.md) decides quality downstream.

## Bootstrap-mode acknowledgment

The adr-critic subagent ships in slice 2 of PRD-B per [ADR-0004](../../../decisions/0004-bypass-prevention.md) D2's bootstrap-mode policy. ADR-0004 itself was reviewed by `prd-critic` in the one-time bootstrap transition (because `adr-critic` did not yet exist at the time ADR-0004 was drafted). From the merge of slice 2 forward, all newly-drafted ADRs go through `adr-critic`. Earlier ADRs (ADR-0001, ADR-0002, ADR-0003, ADR-0004) are grandfathered — retroactive passes are deferred per ADR-0004 Open questions and are not this subagent's responsibility on first invocation.

## Relationship to other agents

- **Joint-gate partner of** [`prd-critic`](prd-critic.md). Both must APPROVE before `/to-prd` posts per [ADR-0004](../../../decisions/0004-bypass-prevention.md) D1.
- **Sibling critic of** [`reviewer`](reviewer.md), [`slicer-critic`](slicer-critic.md), [`prd-critic`](prd-critic.md), [`glossary-critic`](../../../.claude/agents/glossary-critic.md), [`backlog-critic`](../../../.claude/agents/backlog-critic.md). All 6 critics conform to the same verdict template + CRITIC trailer ([[topics/output-shapes]]).
- **Honors the 6-critic-cap** per [ADR-0008](../../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D7. The truth-doc-flagging sub-responsibility is non-blocking and does not count as a 7th critic.
- **Authority:** [ADR-0003](../../../decisions/0003-autonomous-pipeline-with-critics.md) D2 (critic loop pattern), [ADR-0004](../../../decisions/0004-bypass-prevention.md) D1 (joint gate), [ADR-0005](../../../decisions/0005-output-shape-and-slicing-methodology.md) D1 (output shape), [ADR-0009](../../../decisions/0009-discipline-tightening.md) D3/D4 (default-BLOCK + adversarial-mindset bounding), [ADR-0026](../../../decisions/0026-truth-docs-and-r-truth-doc-rule.md) D2 (truth-doc flagging).

## Edges

- **part_of:** [[concepts/rules/ac-convention-compliance]]
- **part_of:** [[concepts/rules/ac-cross-adr-consistency]]
- **part_of:** [[concepts/rules/ac-supersedes-by-d-id]]
- **part_of:** [[concepts/rules/ac-no-scope-creep]]
- **part_of:** [[concepts/rules/ac-bootstrap-mode-acknowledged]]
- **part_of:** [[concepts/rules/ac-immutability-respected]]
- **related_to:** [[entities/subagents/prd-critic]]
- **related_to:** [[entities/subagents/slicer-critic]]
- **related_to:** [[entities/subagents/reviewer]]
- **part_of:** [[topics/pipeline-stages]]
- **related_to:** [[topics/output-shapes]]
- **related_to:** [[concepts/glossary/critic]]
- **related_to:** [[concepts/glossary/joint-approve-gate]]
- **related_to:** [[concepts/glossary/adr]]
- **related_to:** [[concepts/glossary/supersession]]
- **related_to:** [[concepts/glossary/bootstrap-mode]]
