---
title: qa-plan — writer/orchestrator for QA automation (terminal human checkpoint)
summary: Writer half of the Tier-1 QA automation per ADR-0020; LLM-extracts each PRD §2 acceptance criterion into a bash check or JUDGMENT flag, persists the plan as a PRD comment, dispatches qa-tester to execute, renders judgment rows via AskUserQuestion, and auto-closes the PRD on all-PASS + all-judgment-ACCEPT.
tags: [skill, pipeline, generator, qa, qa-plan, checkpoint]
type: entity
last_updated: 2026-05-27
sources:
  - .claude/skills/qa-plan/SKILL.md
  - decisions/0020-qa-automation-writer-executor.md
  - decisions/0003-autonomous-pipeline-with-critics.md
---

# /qa-plan

The `/qa-plan` skill is the **terminal human checkpoint** in the autonomous pipeline — the writer half of the Tier-1 QA automation writer/executor split per [ADR-0020](../../../decisions/0020-qa-automation-writer-executor.md) D1. After all `Closes #<slice>` PRs for a PRD have merged, this skill takes the PRD number, LLM-extracts each §2 acceptance criterion into a runnable bash check or marks it `JUDGMENT` (subjective) or `EXTRACT_FAILED` (could not parse), persists the structured plan as a PRD comment for audit + re-runnability, dispatches the [`qa-tester`](../subagents/qa-tester.md) subagent to execute the mechanical rows, and renders any `JUDGMENT` / `EXTRACT_FAILED` / mechanical-`FAIL` rows back to the user via `AskUserQuestion`. On all-PASS + all-judgment-ACCEPT → auto-close the PRD via `gh issue close --reason completed`.

## Role and responsibility

`/qa-plan` runs in **main-agent context** (so it can call `AskUserQuestion` — main-agent-only per [ADR-0020](../../../decisions/0020-qa-automation-writer-executor.md) D3). It has three jobs:

1. **Distill PRD §2 prose into a mechanical plan.** For each numbered criterion, infer a runnable bash check OR mark `JUDGMENT` (subjective) per [ADR-0020](../../../decisions/0020-qa-automation-writer-executor.md) D2. Failed extractions become `EXTRACT_FAILED`. Persist as a PRD comment under the heading `## QA-plan v1 (<YYYY-MM-DD>)` per D4.
2. **Dispatch the executor** ([`qa-tester`](../subagents/qa-tester.md)) via the `Agent` tool; receive back the per-criterion verdict table + GENERATOR trailer with `PASS_COUNT` / `FAIL_COUNT` / `JUDGMENT_COUNT` / `EXTRACT_FAILED_COUNT`.
3. **Render judgment + FAIL rows** via `AskUserQuestion` (LLM-infer specific accept/reject options from each criterion's prose; fallback to generic "Accept / Reject + reason" only when prose is too thin). On all mechanical PASS + all judgment ACCEPT → `gh issue close <N> --reason completed` per D5. On any mechanical FAIL → halt with `AskUserQuestion` offering accept-FAIL / reopen-for-fix / cull-as-won't-fix.

## Invocation contract

- **Caller:** the user via `/qa-plan <PRD#>` (defaults to most-recently-merged PRD when no argument supplied).
- **Input:** a PRD GitHub issue number. Halts with `RESULT: STOPPED` if the PRD is not in `closed` state with all slice PRs merged.
- **Output:** a persisted `## QA-plan v1` comment on the PRD (URL captured as `ARTIFACTS:`), plus the canonical [GENERATOR trailer](../../concepts/glossary/generator-trailer.md) with 5 per-agent extensions: `PASS_COUNT`, `FAIL_COUNT`, `JUDGMENT_COUNT`, `EXTRACT_FAILED_COUNT` (carried from `qa-tester`), and `PRD_DISPOSITION` (the writer's own extension naming `closed-completed` / `reopened-for-fix` / `culled` / `left-open-pending-fix`).
- **Tool boundaries:** `Read`, `Bash` (`gh issue view/comment/close`), `AskUserQuestion` (judgment + FAIL rendering — main-agent-only), `Agent` (dispatch qa-tester). Explicitly NOT `Write` / `Edit` — the writer never modifies tracked files; only the PRD issue comment + PRD state mutate.

## Writer/executor split rationale

Per [ADR-0020](../../../decisions/0020-qa-automation-writer-executor.md) D1, the split mirrors slicer + slicer-critic (one plans, one executes). The writer must remain in main-agent context for `AskUserQuestion`; the executor ([`qa-tester`](../subagents/qa-tester.md)) lives in an isolated context with strict tool boundaries (`Read`, `Bash`, `Grep` only — no `Agent`, no `Write`, no `AskUserQuestion` per D3) so its mechanical row-execution stays auditable and free of side effects. The writer's [GENERATOR trailer](../../concepts/glossary/generator-trailer.md) layers `PRD_DISPOSITION` on top of the qa-tester's count fields per D5.

## Relationship to other skills and agents

- **Called by** the user; NOT called by `/ship` (per [ADR-0003](../../../decisions/0003-autonomous-pipeline-with-critics.md) D4 — `/qa-plan` is the terminal human checkpoint, refined per [ADR-0020](../../../decisions/0020-qa-automation-writer-executor.md) D10).
- **Invokes** [`qa-tester`](../subagents/qa-tester.md) as the executor.
- **Upstream consumer of** the merged-PR state from [`/ship`](ship.md).
- **Honors the 6-critic-cap** per [ADR-0008](../../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D7 — `/qa-plan` is a skill, `qa-tester` is a generator subagent (NOT a 7th critic).
- **Authority:** [ADR-0020](../../../decisions/0020-qa-automation-writer-executor.md) — primary spec. D1 (writer/executor split), D2 (LLM-extract + EXTRACT_FAILED), D4 (plan persisted as PRD comment), D5 (auto-close on all-PASS + all-judgment-ACCEPT), D10 (refines [ADR-0003](../../../decisions/0003-autonomous-pipeline-with-critics.md) D4 terminal human checkpoint).

## Edges

- **part_of:** [[topics/pipeline-stages]]
- **related_to:** [[entities/skills/ship]]
- **related_to:** [[entities/subagents/qa-tester]]
- **related_to:** [[concepts/glossary/prd]]
- **related_to:** [[concepts/glossary/generator-trailer]]
- **related_to:** [[topics/output-shapes]]
