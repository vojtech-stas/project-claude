---
name: qa-plan
description: Writer/orchestrator for QA automation per ADR-0020. Takes a PRD number (defaults to the most-recently-merged PRD), LLM-extracts each §2 acceptance criterion into a bash check or JUDGMENT flag, persists the plan as a PRD comment for audit, dispatches the qa-tester subagent to execute, renders JUDGMENT and EXTRACT_FAILED rows via AskUserQuestion, and auto-closes the PRD on all-PASS + all-judgment-ACCEPT. Invoke at PRD acceptance — the terminal human checkpoint refined per ADR-0020 D10. Backward-compatible with /ship invocation surface.
---

# /qa-plan — writer/orchestrator for QA automation

This skill runs in **main-agent context** (so it can call `AskUserQuestion`); it does not modify code. It distills PRD §2 prose into a mechanical plan, hands execution to the [`qa-tester`](../../agents/qa-tester.md) subagent, and renders judgment rows back to the user. Per [ADR-0020](../../../decisions/0020-qa-automation-writer-executor.md) D1 the writer/executor split mirrors slicer + slicer-critic (one plans, one executes); per D10 the human checkpoint is refined (judge subjective outcomes, not run grep commands).

## When NOT to use this skill

- Mid-feature, while slices are still open — wait until all `Closes #<slice>` PRs for the PRD have merged.
- For PRDs whose §2 lacks acceptance criteria — push back; ask the user to `/grill-me` the missing criteria first.
- For Tier 2 (semantic) or Tier 3 (UI) QA — both deferred to future PRDs per ADR-0020 D6/D7.

## Process

1. **Read PRD §2.** `gh issue view <N> --json title,body --repo vojtech-stas/project-claude`. Parse the **Goal / Success criteria** section. If the PRD is not in `closed` state with all slice PRs merged, halt with `RESULT: STOPPED` and ask the user to confirm.
2. **LLM-extract the structured plan.** For each numbered criterion in §2, infer either a runnable bash check (the criterion's own "Verifiable: ..." prose often gives it directly) OR mark `JUDGMENT` if subjective. Failed extractions become `EXTRACT_FAILED` per [ADR-0020](../../../decisions/0020-qa-automation-writer-executor.md) D2. Build a 3-column Markdown table: `criterion # | bash check or "JUDGMENT" | expected result`.
3. **Persist the plan as a PRD comment.** `gh issue comment <N> --repo vojtech-stas/project-claude --body-file <tempfile>` containing the table under a `## QA-plan v1 (<YYYY-MM-DD>)` heading. Audit trail + re-runnability per [ADR-0020](../../../decisions/0020-qa-automation-writer-executor.md) D4. Capture the resulting comment URL as the trailer `ARTIFACTS:` value.
4. **Dispatch the qa-tester subagent.** Invoke via `Agent` tool with `subagent_type: "qa-tester"`, passing the plan table inline in the prompt. Receive back the per-criterion verdict table + canonical GENERATOR trailer (`PASS_COUNT`, `FAIL_COUNT`, `JUDGMENT_COUNT`, `EXTRACT_FAILED_COUNT`).
5. **Render JUDGMENT and EXTRACT_FAILED rows.** For each such row, call `AskUserQuestion` with option-format LLM-inferred from the criterion prose (per PRD #166 §6 OQ slice-2 implementer judgment: LLM-infer specific accept/reject options from each criterion's wording, matching the PRD #147 dogfood pattern; fallback to generic "Accept / Reject + reason" only when criterion prose is too thin to infer specific options). Collect responses.
6. **Decide PRD disposition.** If all mechanical PASS AND all judgment ACCEPT → `gh issue close <N> --reason completed --repo vojtech-stas/project-claude --comment <qa-pass-summary>` per [ADR-0020](../../../decisions/0020-qa-automation-writer-executor.md) D5. If any mechanical FAIL → `AskUserQuestion` with options accept-FAIL / reopen-for-fix / cull-as-won't-fix; act on the user's choice (no auto-close on FAIL).

## Tool boundaries

`Read`, `Bash` (gh CLI for issue view/comment/close + any pre-checks), `AskUserQuestion` (judgment-row + FAIL rendering — main-agent-only per ADR-0020 D3, which is why this skill cannot run as a subagent), `Agent` (dispatch qa-tester executor). Explicitly **NOT** `Write` / `Edit` — the writer never modifies tracked files; only the PRD issue comment + PRD state mutate. Plan persistence is via `gh issue comment`, not git.

## Output format for the calling agent

After step 6, emit the canonical **GENERATOR trailer** (per [ADR-0005](../../../decisions/0005-output-shape-and-slicing-methodology.md) D1c) as a fenced code block at the end of the terminal report:

```
RESULT: SUCCESS | STOPPED | INVALID_INPUT
REASON: <one sentence — e.g., "PRD #N auto-closed: 13 PASS + 3 judgment-ACCEPT" or "halted: 2 mechanical FAILs surfaced via AskUserQuestion">
ARTIFACTS: <URL of the persisted QA-plan comment>
PASS_COUNT: <integer>
FAIL_COUNT: <integer>
JUDGMENT_COUNT: <integer>
EXTRACT_FAILED_COUNT: <integer>
PRD_DISPOSITION: closed-completed | reopened-for-fix | culled | left-open-pending-fix
```

`PASS_COUNT` / `FAIL_COUNT` / `JUDGMENT_COUNT` / `EXTRACT_FAILED_COUNT` carry forward from the qa-tester subagent's trailer (per [`qa-tester.md`](../../agents/qa-tester.md) output shape). `PRD_DISPOSITION` is a per-agent extension naming the resulting PRD state so `/ship` and post-run audits can correlate without re-fetching.

## References

- Full role synthesis (writer/executor split rationale, edges): this file.
- [ADR-0020](../../../decisions/0020-qa-automation-writer-executor.md) — primary spec. D1 (writer/executor split), D2 (LLM-extract + EXTRACT_FAILED), D4 (plan persisted as PRD comment), D5 (auto-close on all-PASS + all-judgment-ACCEPT), D10 (refines ADR-0003 D4 terminal human checkpoint).
- [`.claude/agents/qa-tester.md`](../../agents/qa-tester.md) — executor subagent dispatched at step 4.
- [ADR-0005](../../../decisions/0005-output-shape-and-slicing-methodology.md) D1c — canonical GENERATOR trailer schema.
- [ADR-0003](../../../decisions/0003-autonomous-pipeline-with-critics.md) D4 — terminal human checkpoint (refined, not removed, per ADR-0020 D10).
- PRD [#166](https://github.com/vojtech-stas/project-claude/issues/166) — parent PRD; this skill's rewrite is slice [#168](https://github.com/vojtech-stas/project-claude/issues/168).
