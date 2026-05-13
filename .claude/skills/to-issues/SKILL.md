---
name: to-issues
description: Break a PRD into independently-grabbable vertical-slice issues on GitHub. Delegates to the `slicer` and `slicer-critic` subagents under the hood. Invocation shape preserved — use when the user says `/to-issues`, asks to break a PRD into slices, or convert a plan into implementation tickets.
---

# /to-issues — thin wrapper around slicer + slicer-critic

This skill turns a PRD into a set of GitHub Issues, one per vertical slice. Since PRD #3 / slice #5, the decomposition work is delegated to the `slicer` and `slicer-critic` subagents (per [ADR-0003](../../../decisions/0003-autonomous-pipeline-with-critics.md) D2/D6). The invocation `/to-issues` is preserved — backward-compatible for both direct human use and `/ship` orchestration.

## Step-by-step

1. **Identify the PRD.** If the user passes a GitHub issue reference (`#N`, URL, or path), use that. Otherwise scan conversation context for a recently-posted PRD (`label:prd`). If still ambiguous, STOP and ask which PRD to slice — do not invent one.

2. **Generate N=3 decompositions via the `slicer` subagent.** Invoke `slicer` (file: `.claude/agents/slicer.md`) with the PRD reference. It returns the "Slicer output for PRD #N" block with three alternative decompositions (INVEST tags, walking-skeleton flag, dependency ordering, LoC estimate, risk note per slice). If the subagent returns `INVALID_PRD: <reason>` → surface that and STOP.

3. **Score and select via the `slicer-critic` subagent.** Invoke `slicer-critic` (file: `.claude/agents/slicer-critic.md`) with both the PRD and the slicer's N=3 block. The critic applies its rubric, picks one decomposition with tiebreak rationale, and runs **at most one** revision loop (per ADR-0003 D3 — no re-sampling N=3). It returns either APPROVE with a `Final approved decomposition` block, or BLOCK with reasons. On BLOCK: surface reasons, do NOT post issues, STOP.

4. **Confirm with the user (interactive mode only).** When `/to-issues` is invoked directly by a human, display the critic's `Final approved decomposition` and ask "Post these slices to GitHub?" before any `gh issue create`. When invoked via `/ship`, skip this step — the pipeline is autonomous per ADR-0003 D4. Detect the calling context from the surrounding conversation.

5. **Publish one GitHub Issue per slice, in dependency order.** Walk the approved decomposition's `Depends on` graph topologically — post blockers first so subsequent issues can reference real issue numbers in their `Depends on:` field. Use `gh issue create --label slice --body-file <tempfile>` (heredoc bodies mangle multiline on PowerShell). Each posted issue body includes `Parent: #<PRD-issue-number>` so GitHub renders the back-link.

<issue-template>
## Parent

PRD #<N> — <PRD title>

## What ships

<1–3 sentence end-to-end description from the slicer output. Behavior, not file paths.>

## Acceptance criteria

- [ ] <Criterion 1 — derived from the slicer output's per-slice detail>
- [ ] <Criterion 2>
- [ ] PR diff ≤<cap> LoC of runtime-artifact code (per PRD §4)

## Walking-skeleton role

<Only if this slice is tagged `walking-skeleton: yes` in the approved decomposition. Otherwise omit this section.>

## Depends on

- #<blocker issue number>

Or "None — can start immediately" if no blockers.

## LoC estimate

~<int> runtime LoC.

## Branch + commit conventions

- Branch: `feat/<this-issue-number>-<kebab-summary>`
- Commit prefix: `feat(<scope>):` (or `fix:` / `refactor:` etc. — Conventional Commits)
- PR body MUST include `Closes #<this-issue-number>`
</issue-template>

6. **Report back.**
   - Print the list of posted slice issue URLs in dependency order.
   - When called via `/ship`, return the issue numbers + URLs to the orchestrator so it can hand off to the implementer-reviewer loop (stage 4) downstream.

## What this skill deliberately does NOT do

- Does NOT close or modify the parent PRD issue.
- Does NOT decide the decomposition itself — that work belongs to `slicer` + `slicer-critic`.
- Does NOT post issues without an APPROVED critic verdict (autonomous loop integrity per ADR-0003 D4).
- Does NOT re-invoke the slicer pair if the critic blocks. The blocking surface is returned to the user/orchestrator; one round of human or orchestrator intervention re-runs the pipeline.

## References

- [ADR-0003](../../../decisions/0003-autonomous-pipeline-with-critics.md) — D2 (five-stage pipeline), D3 (N=3 at slicer + single revision loop), D6 (skills vs subagents).
- Subagents this skill orchestrates: [`.claude/agents/slicer.md`](../../agents/slicer.md), [`.claude/agents/slicer-critic.md`](../../agents/slicer-critic.md).
- Sibling skill: [`.claude/skills/ship/SKILL.md`](../ship/SKILL.md) — calls this skill as stage 3 of the pipeline.
