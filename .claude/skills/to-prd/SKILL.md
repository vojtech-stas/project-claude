---
name: to-prd
description: Turn the current conversation context into a PRD and publish it to the project issue tracker. Use when user wants to create a PRD from the current context.
---

This skill takes the current conversation context and codebase understanding and produces a PRD using the **6-section template** defined below. It invokes the `prd-critic` subagent in a ≤3-round APPROVE/BLOCK loop before posting. When a macro-ADR is drafted alongside the PRD per [ADR-0003](../../../decisions/0003-autonomous-pipeline-with-critics.md) D8, the `adr-critic` subagent runs in parallel under a **shared round counter** and BOTH critics must APPROVE in the same round before the skill publishes (per [ADR-0004](../../../decisions/0004-bypass-prevention.md) D1).

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

4. **Invoke the critic(s).** State the round number explicitly (start at round 1).
   - **Always:** invoke `prd-critic` with the draft PRD (and any drafted ADRs) inline.
   - **When a macro-ADR was drafted in step 2 (per [ADR-0003](../../../decisions/0003-autonomous-pipeline-with-critics.md) D8):** ALSO invoke `adr-critic` in parallel, passing the drafted ADR(s) — `adr-critic`'s `When invoked` contract accepts inline markdown or a path. Each drafted ADR gets its own `adr-critic` invocation; if multiple ADRs are drafted, invoke `adr-critic` once per ADR in the same round. Per [ADR-0004](../../../decisions/0004-bypass-prevention.md) D1, `adr-critic`'s verdict gates ADR publication exactly the way `prd-critic`'s verdict gates PRD publication.

5. **Critic loop (≤3 rounds, joint-APPROVE gate):**

   **Round counter convention (locked decision — Option A, shared round counter).** When both `prd-critic` and `adr-critic` are invoked, they share a single round number. If either returns BLOCK on round N, the loop revises and re-invokes BOTH critics on round N+1 (even if one already APPROVED on round N — the re-revision may have invalidated its prior verdict). Round-3 escalation triggers when EITHER critic returns BLOCK on round 3. **Rationale:** simpler invariant; conservative; one counter to reason about; matches the existing `prd-critic` semantics byte-for-byte for the PRD-only case (no ADR drafted → `adr-critic` is not invoked → behavior is unchanged).

   - On **joint APPROVE** (both critics return APPROVE in the same round, OR `prd-critic` returns APPROVE and no ADR was drafted) → proceed to step 6.
   - On **BLOCK from either critic** with `ROUND < 3` → apply each finding from each blocking critic's itemized list (PRD findings revise the PRD draft; ADR findings revise the ADR draft), increment the shared round, re-invoke BOTH critics. Do not invent fixes the critic didn't request; do not skip any finding; do not split the round counters.
   - On **BLOCK from either critic** with `ROUND == 3` (or `ESCALATE: needs-human` in either verdict) → STOP. Do not post the PRD. Do not commit the ADR. Surface both verdicts back to the calling agent / user. Per I5 escalation: apply the `needs-human` label to the draft tracking artifact (or to the posted PRD issue if already posted) and post a summary comment on the parent grill-session / PRD context with both verdicts attached. The pipeline does not silently publish a thrice-blocked PRD or ADR.

6. **Publish** to the project issue tracker (only after joint APPROVE):
   - PRD → `gh issue create` with label `prd`. Title format: `PRD: <one-line feature summary>`.
   - Any drafted ADR(s) → write to `decisions/NNNN-<slug>.md`. These ship as part of slice 1's PR per ADR-0003 D8; they are NOT separately posted as issues.
   - Append a one-line `> **Pipeline metadata** — Approved by prd-critic round <N>/3` footer to the PRD body so the audit trail is visible. When an ADR was drafted and reviewed, extend the footer to `> **Pipeline metadata** — Approved by prd-critic round <N>/3; adr-critic round <N>/3 (ADR-NNNN).` The round numbers match by construction (shared counter per step 5).

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

## Rubric self-check (before invoking the critic[s])

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

**Additional ADR self-check (when a macro-ADR was drafted in step 2 — mirrors `adr-critic`'s rubric):**

10. ADR has all required sections (Status, Date, Context, Decisions, Consequences, Alternatives considered) — non-empty.
11. ADR does not silently contradict an accepted ADR; any conflict carries an explicit `Supersedes:` header citing the specific D-ID being overridden.
12. `Supersedes:` header cites accurate D-IDs — each cited `ADR-NNNN D-X` exists in the named ADR file AND the substance matches what this ADR claims it says (the exact defect ADR-0003 had against ADR-0001 D3; `adr-critic` rule 3 catches this).
13. Every Decision in the ADR serves the ADR's stated theme — no "while we're here" scope creep into a separate concern.
14. If the ADR introduces a new enforcement mechanism (hook, branch protection rule, critic, gate subagent, mandatory loop), it explicitly cites ADR-0004 D2's bootstrap-mode policy OR includes its own bootstrap-mode acknowledgment naming which slices it binds.
15. ADR does NOT propose edits to existing ADR files. Corrections to prior ADRs ship as new ADRs with explicit `Supersedes:` headers per `decisions/README.md` immutability.

## What this skill deliberately does NOT do

- It does NOT interview the user (that's `/grill-me`).
- It does NOT enumerate the slice list (that's `slicer` + `to-issues`).
- It does NOT enforce the PRD template via JSON schema or YAML frontmatter — `prd-critic` checks section presence by prompt. (PRD #3 §6 rabbit-hole.)
- It does NOT spawn a separate `/to-adr` skill. ADR drafting happens inline here. (PRD #3 §5 and PRD #15 §3 locked-in decision.)
- It does NOT post a PRD or commit an ADR until BOTH `prd-critic` AND (if a macro-ADR was drafted) `adr-critic` APPROVE in the same round. Either-BLOCK loops the generator under the shared round counter (Option A); both-APPROVE on the same round → publish. Round-3 BLOCK on either critic → I5 escalation; no silent publish.

## References

- [ADR-0003](../../../decisions/0003-autonomous-pipeline-with-critics.md) — D2 (critic loop pattern), D6 (skill vs subagent), D8 (ADR placement — macro-ADRs drafted alongside the PRD; this is what makes the dual-critic dance necessary).
- [ADR-0004](../../../decisions/0004-bypass-prevention.md) — D1 (adr-critic exists; mirror of prd-critic's contract); D2 (bootstrap-mode policy).
- [`.claude/agents/prd-critic.md`](../../agents/prd-critic.md) — the PRD critic this skill invokes (always).
- [`.claude/agents/adr-critic.md`](../../agents/adr-critic.md) — the ADR critic this skill invokes (only when a macro-ADR is drafted in step 2).
- [`decisions/README.md`](../../../decisions/README.md) — ADR conventions and the "When to write an ADR" heuristic.
- Sibling: [`.claude/skills/ship/SKILL.md`](../ship/SKILL.md) — orchestrator that chains this skill into the autonomous pipeline.
