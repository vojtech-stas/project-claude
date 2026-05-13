---
name: to-prd
description: Turn the current conversation context into a PRD and publish it to the project issue tracker. Use when user wants to create a PRD from the current context.
---

This skill takes the current conversation context and codebase understanding and produces a PRD using the **6-section template** defined below. It invokes the `prd-critic` subagent in a ≤3-round APPROVE/BLOCK loop before posting, and drafts any warranted macro-ADRs alongside the PRD per [ADR-0003](../../../decisions/0003-autonomous-pipeline-with-critics.md) D8.

Do NOT interview the user — synthesize what you already know from the grill session and the repo.

## Process

1. **Explore the repo** to understand current state. Use the project's domain vocabulary throughout the PRD; respect existing ADRs in the area you're touching.

2. **Decide if a macro-ADR is warranted** alongside the PRD. Apply the heuristic from [`decisions/README.md`](../../../decisions/README.md) — write one iff at least one of these is true:
   - The decision was hard to make (real trade-offs surfaced; multiple valid paths existed).
   - It constrains future work.
   - A future maintainer would ask "why did they do it this way?" without explanation.

   If yes → draft the ADR markdown in parallel with the PRD using the conventions in `decisions/README.md` (Status / Date / Context / Decisions / Consequences / Alternatives considered; optional Open questions deferred / Future direction / References). Number it `NNNN-<kebab-slug>.md` as the next unused integer. Both PRD and ADR(s) go to the critic in the same round; both ship together in slice 1 of the resulting implementation per ADR-0003 D8.

   If no → skip; trivial features don't get ADRs.

3. **Draft the PRD** using the 6-section template below.

4. **Invoke the `prd-critic` subagent** with the draft PRD (and any drafted ADRs) inline. State the round number explicitly (start at round 1).

5. **Critic loop (≤3 rounds):**
   - On **APPROVE** → proceed to step 6.
   - On **BLOCK** with `ROUND < 3` → apply each finding in the critic's itemized list, increment the round, re-invoke `prd-critic`. Do not invent fixes the critic didn't request; do not skip any finding.
   - On **BLOCK** with `ROUND == 3` (or `ESCALATE: needs-human` in the verdict) → STOP. Do not post. Surface the verdict back to the calling agent / user and recommend the grill session be re-opened. The pipeline does not silently publish a thrice-blocked PRD.

6. **Publish** to the project issue tracker:
   - PRD → `gh issue create` with label `prd`. Title format: `PRD: <one-line feature summary>`.
   - Any drafted ADR(s) → write to `decisions/NNNN-<slug>.md`. These ship as part of slice 1's PR per ADR-0003 D8; they are NOT separately posted as issues.
   - Append a one-line `> **Pipeline metadata** — Approved by prd-critic round <N>/3.` footer to the PRD body so the audit trail is visible.

## The 6-section PRD template (canonical definition)

This is the canonical location for the template. `CLAUDE.md` links here; do not restate the template elsewhere.

<prd-template>

## 1. Problem

Who is hurting, how, and why now. One paragraph. Concrete language; no "we should improve X" framings. Anchor in the grill-session insight that motivated the PRD.

## 2. Goal / Success criteria

The single observable outcome of shipping this PRD, plus a checklist of mechanically verifiable criteria. Each criterion must be checkable at merge (file exists with shape X, command Y produces output Z) — not by subjective judgment. End-to-end quality validation belongs in the QA-plan handoff, not these criteria.

## 3. Non-goals / Out of scope

A bulleted list of things deliberately NOT in this PRD, each with a one-line reason. Empty or TBD non-goals are not acceptable — a PRD without explicit non-goals will drift.

## 4. Appetite / Constraints

Slice budget (e.g., 5–7 slices), time appetite (e.g., 2–3 sessions), per-slice LoC cap, dependency stance (no new external deps unless justified), backward-compatibility commitments. Must be consistent with the Solution sketch in §5.

## 5. Solution sketch

Coarse module shape — what files get added/edited and the role each plays. Walking-skeleton-first: name what slice 1 must be (the thinnest end-to-end vertical), and call out any locked-in decisions that close earlier open questions. Do NOT enumerate the full slice list — the slicer subagent owns that.

## 6. Rabbit-holes & Open questions

Two sub-sections:
- **Rabbit-holes (don't chase)** — explicit traps the implementer must avoid. Pull from the grill session and referenced ADRs.
- **Open questions** — genuinely unresolved questions. Do not silently answer them; flag them for the slicer or implementer to surface again.

</prd-template>

## Rubric self-check (before invoking the critic)

These mirror `prd-critic`'s rubric. A quick self-pass shortens the loop:

1. Problem section names who hurts, how, why now — concretely.
2. Every Goal criterion is mechanically checkable.
3. Non-goals are explicit, with reasons.
4. Appetite is consistent with the Solution sketch's scope.
5. Rabbit-holes from the grill session are listed.
6. Unresolved questions are flagged, not silently answered.
7. No conflicts with accepted ADRs (and no references to non-existent ADRs — the critic BLOCKs on `"ADR-XXXX referenced but not present"`).
8. Solution sketch stays within the stated feature.
9. Slice-1 guidance is a thin end-to-end vertical, not a horizontal layer.

## What this skill deliberately does NOT do

- It does NOT interview the user (that's `/grill-me`).
- It does NOT enumerate the slice list (that's `slicer` + `to-issues`).
- It does NOT enforce the PRD template via JSON schema or YAML frontmatter — `prd-critic` checks section presence by prompt. (PRD #3 §6 rabbit-hole.)
- It does NOT spawn a separate `/to-adr` skill. ADR drafting happens inline here. (PRD #3 §5 locked-in decision.)

## References

- [ADR-0003](../../../decisions/0003-autonomous-pipeline-with-critics.md) — D2 (critic loop pattern), D6 (skill vs subagent), D8 (ADR placement).
- [`.claude/agents/prd-critic.md`](../../agents/prd-critic.md) — the critic this skill invokes.
- [`decisions/README.md`](../../../decisions/README.md) — ADR conventions and the "When to write an ADR" heuristic.
- Sibling: [`.claude/skills/ship/SKILL.md`](../ship/SKILL.md) — orchestrator that chains this skill into the autonomous pipeline.
