---
title: backlog-critic — autopilot gate from captured tier to curated backlog
summary: Reads a freshly `captured`-labeled GitHub issue; applies the 4-criterion rubric (actionable / scoped / not duplicate / clear); APPROVE → autopilot swaps labels captured→backlog; BLOCK → item stays captured for lazy human review. Single-shot, no revision loop, no needs-human escalation in autopilot mode.
tags: [subagent, critic, gate, backlog-critic]
type: entity
last_updated: 2026-05-26
sources:
  - .claude/agents/backlog-critic.md
  - decisions/0006-backlog-and-session-continuity.md
  - decisions/0008-workflow-autolog-bootstrap-and-naming.md
  - decisions/0005-output-shape-and-slicing-methodology.md
  - decisions/0009-discipline-tightening.md
---

# backlog-critic

The `backlog-critic` subagent is the **adversarial autopilot gate** between the captured tier (zero-friction graveyard) and the backlog tier (curated forward queue from which `/grill-me` picks). It receives a single freshly-`captured`-labeled GitHub issue, applies a 4-criterion rubric per [ADR-0008](../../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D4, and emits APPROVE (the [`/promote-to-backlog`](../../../.claude/skills/promote-to-backlog/SKILL.md) autopilot swaps `captured` → `backlog`) or BLOCK (the item stays in `captured` for lazy human review). Per [ADR-0008](../../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D2 its verdict is the sole authority on promotion.

This entity note is the **canonical full role synthesis** for the backlog-critic subagent. After the T4 knowledge-architecture migration ([ADR-0031](../../../decisions/0031-knowledge-architecture-v2.md) D10 step 4 of 9, PRD #283 slice 7), the operational [`.claude/agents/backlog-critic.md`](../../../.claude/agents/backlog-critic.md) will carry only the prompt-level operational mechanics (mandatory reading order, rubric trigger lines, output-format pointer, tool boundaries, conduct) and link here for the rubric-criterion full bodies (each shipped as a `docs/current/concepts/rules/bc-*.md` atomic note in this slice), the loop-semantics divergence rationale, the bootstrap-mode acknowledgment, and the relationship to sibling critics.

## Role and responsibility

The backlog-critic has two jobs, in strict priority order:

1. **Hard-block** any captured item that violates a rubric criterion. Emit itemized findings naming the user's options (cull / manual rescue / restructure-and-recapture).
2. **Recommend** non-blocking improvements after the verdict body, before the trailer (the canonical `Recommendations` extension per [ADR-0005](../../../decisions/0005-output-shape-and-slicing-methodology.md) D1).

It does NOT write or edit any file. It does NOT swap the issue label itself — that is the autopilot's responsibility, and the separation is intentional (the critic judges; the autopilot acts). It does NOT close, comment on, or relabel the issue. It does NOT invoke other subagents or fetch external URLs.

## Invocation contract

- **Caller:** the [`/promote-to-backlog`](../../../.claude/skills/promote-to-backlog/SKILL.md) skill, invoked **inline in the same agent context** that just ran `gh issue create --label captured` per [ADR-0008](../../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D3. May also be invoked via the `Agent` tool with `subagent_type: "backlog-critic"` for testing or replay.
- **Input:** EITHER a GitHub issue number (typical — the critic fetches via `gh issue view`), OR the raw issue body inline as markdown plus the issue number. If neither is supplied → `INVALID_INPUT: no issue number and no body supplied`. If the issue does not carry the `captured` label → `INVALID_INPUT: issue #<N> is not labeled captured` — the contract is only the captured tier.
- **Output:** the canonical verdict template per [[topics/output-shapes]] — 5-section body (Header → Subject of review → Rubric → Findings → Summary) + optional Recommendations extension + adapted CRITIC trailer (see "Loop semantics" below). Returned inline to the calling agent so the autopilot can act without further prompting.
- **Tool boundaries:** `Read`, `Glob`, `Grep`, `Bash` (read-only: `gh issue view`, `gh issue list --label backlog/captured`, `ls decisions/`, `cat decisions/...`, supplementary `grep`). NOT authorized: `Write`/`Edit`, `gh issue create`/`edit`/`close`/`comment`, label swapping, branch creation, agent invocation, external URL fetch.

## Loop semantics — diverges from other critics

Unlike the other 5 critics (which run a ≤3-round APPROVE/BLOCK loop with `needs-human` escalation), backlog-critic fires **at most once per item**, inline in the same agent context that wrote the capture (per [ADR-0008](../../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D3). There is **no ≤3-round revision loop and no `needs-human` escalation** in autopilot mode. Rationale per [ADR-0008](../../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D2:

- The captured item is **data the invoking agent already chose to write** — re-prompting that agent to "fix" the capture would conflate captured-tier (zero-friction inbox) with curated-tier (post-critic queue).
- On BLOCK the item stays labeled `captured`; the **user is the escalation path** via manual rescue (relabel to `backlog`) or cull (close).
- Adapted CRITIC trailer: `ROUND:` line omitted (no multi-round loop); `ESCALATE:` line omitted (user-rescue replaces `needs-human`).

Default-conservative per [ADR-0008](../../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D2 and [ADR-0009](../../../decisions/0009-discipline-tightening.md) D3: **when uncertain about any rule, BLOCK**. The asymmetric-cost rationale: a false-positive APPROVE pollutes the curated backlog and forces high-friction culling from `backlog`; a false-negative BLOCK leaves the item in `captured` where lazy human review can rescue it at low friction. Conservative-default is the asymmetric correct choice. Adversarial mindset is a lens for ordering rubric scrutiny, not a license to invent failure modes beyond the rubric per [ADR-0009](../../../decisions/0009-discipline-tightening.md) D4.

## 4-criterion rubric

Each linked rule note expands the criterion's What / Why / How-to-check / Examples. The atomic-note layer is the canonical home; the [`backlog-critic.md`](../../../.claude/agents/backlog-critic.md) executable shell will quote each criterion's name + one-line trigger only after the slice 7 thinning.

1. [[concepts/rules/bc-actionable]] — body describes a concrete action against a named artifact
2. [[concepts/rules/bc-scoped]] — PRD-size or coherent sub-feature (not trivial-lane-sized, not multi-PRD-sized)
3. [[concepts/rules/bc-not-duplicate]] — no semantic duplicate in open `backlog` or `captured` tier
4. [[concepts/rules/bc-clear]] — body stands alone without source-conversation context

Each check is PASS or FAIL. Any FAIL → BLOCK; findings cite the offending lines or absences in the captured body.

## Bootstrap-mode acknowledgment

This subagent ships in slice 1 of PRD #58 per [ADR-0008](../../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D8. From that merge forward, **all** captured-tier writes go through `backlog-critic` **when written inside an active agent context** (per [ADR-0008](../../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D3). Captures written outside agent context (e.g., the user runs `gh issue create --label captured` directly from the terminal) are NOT auto-processed — they sit in the captured tier awaiting either manual triggering of this critic or a future `/triage-captured` sweep skill (noted as future direction in [ADR-0008](../../../decisions/0008-workflow-autolog-bootstrap-and-naming.md)).

[ADR-0006](../../../decisions/0006-backlog-and-session-continuity.md) D4's existing surfacing convention is **amended forward** by [ADR-0008](../../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D8: enumerated agents will, in subsequent slices or future PRDs that touch their prompts, have their write target shifted from `backlog` (per ADR-0006 D4) to `captured` (per ADR-0008) plus the inline-`backlog-critic`-invocation step. No retroactive prompt sweep across pre-existing prompts. This bootstrap-mode language matches the pattern codified by [ADR-0004](../../../decisions/0004-bypass-prevention.md) D2 and mirrored in [`adr-critic`](adr-critic.md) and [`glossary-critic`](../../../.claude/agents/glossary-critic.md).

## Relationship to other agents

- **Sole gate of** the autopilot promotion `captured` → `backlog`. The [`/promote-to-backlog`](../../../.claude/skills/promote-to-backlog/SKILL.md) skill is the caller; the swap is the skill's action on the critic's APPROVE.
- **Sibling critic of** [`reviewer`](reviewer.md), [`prd-critic`](prd-critic.md), [`adr-critic`](../../../.claude/agents/adr-critic.md), [`slicer-critic`](slicer-critic.md), [`glossary-critic`](../../../.claude/agents/glossary-critic.md). All 6 critics conform to the same verdict template + CRITIC trailer ([[topics/output-shapes]]); backlog-critic's trailer is the **single adaptation** — no `ROUND:` line, no `ESCALATE:` line — driven by the divergent autopilot loop semantics above.
- **Upstream consumer of** every agent that fires `gh issue create --label captured` per CLAUDE.md rule #11 (forward-work captures) and rule #13 (root-cause workflow captures, with 3-part Symptom/Cause/Proposed body shape).
- **Honors the 6-critic-cap** per [ADR-0008](../../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D7.
- **Authority:** [ADR-0008](../../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D2 (autopilot semantics, default-BLOCK rationale), [ADR-0008](../../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D3 (inline-firing convention), [ADR-0008](../../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D4 (4-criterion rubric), [ADR-0008](../../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D8 (bootstrap-mode), [ADR-0005](../../../decisions/0005-output-shape-and-slicing-methodology.md) D1 (output shape, with trailer adaptation), [ADR-0009](../../../decisions/0009-discipline-tightening.md) D3/D4 (default-BLOCK + adversarial-mindset bounding).

## Edges

- **part_of:** [[concepts/rules/bc-actionable]]
- **part_of:** [[concepts/rules/bc-scoped]]
- **part_of:** [[concepts/rules/bc-not-duplicate]]
- **part_of:** [[concepts/rules/bc-clear]]
- **related_to:** [[entities/subagents/prd-critic]]
- **related_to:** [[entities/subagents/slicer-critic]]
- **related_to:** [[entities/subagents/reviewer]]
- **part_of:** [[topics/pipeline-stages]]
- **related_to:** [[topics/output-shapes]]
- **related_to:** [[concepts/glossary/critic]]
- **related_to:** [[concepts/glossary/backlog]]
- **related_to:** [[concepts/glossary/captured]]
