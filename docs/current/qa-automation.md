# qa-automation — current state

- **Status:** current as of 2026-05-25
- **Date:** 2026-05-25
- **Topic slug:** `qa-automation`

Active synthesis of QA automation per [ADR-0026](../../decisions/0026-knowledge-architecture-truth-docs.md) D1 — canonical answer to "what is currently true about QA automation in this project?" derived from the immutable ADR chain + skill/subagent contracts + CLAUDE.md preamble; regenerated at PR review time per R-TRUTH-DOC ([ADR-0026](../../decisions/0026-knowledge-architecture-truth-docs.md) D5).

## Active synthesis

**Writer/executor split** (per [ADR-0020](../../decisions/0020-qa-automation-writer-executor.md) D1, the load-bearing contract):

- **Writer:** `/qa-plan` skill at `.claude/skills/qa-plan/SKILL.md`. Runs in **main-agent context** (so it can call `AskUserQuestion`). Takes a PRD number; LLM-extracts each §2 acceptance criterion into either a runnable bash check or a `JUDGMENT` flag per [ADR-0020](../../decisions/0020-qa-automation-writer-executor.md) D2; persists the structured plan as a comment on the PRD issue per [ADR-0020](../../decisions/0020-qa-automation-writer-executor.md) D4; dispatches the executor; renders `JUDGMENT` / `EXTRACT_FAILED` rows; decides PRD disposition.
- **Executor:** `qa-tester` subagent at `.claude/agents/qa-tester.md`. Runs in **isolated subagent context** (deterministic mechanical work stays out of main). Walks rows/recipes sequentially per-criterion (per [ADR-0020](../../decisions/0020-qa-automation-writer-executor.md) D3); returns a per-criterion verdict table + canonical GENERATOR trailer per [ADR-0005](../../decisions/0005-output-shape-and-slicing-methodology.md) D1c. Executor never touches `AskUserQuestion` — subagents lack the tool; the writer renders all judgment.

**Dual-mode executor** per [ADR-0025](../../decisions/0025-qa-tester-ui-mode-playwright.md) D1 (surgically narrows [ADR-0020](../../decisions/0020-qa-automation-writer-executor.md) D3's tool-boundary clause; preserves all other ADR-0020 decisions):

- **bash-mode** (default; original ADR-0020 D3 behavior). Tool boundary: `Read, Bash, Grep` only. Input: 3-column Markdown table. Output trailer extensions: `PASS_COUNT` / `FAIL_COUNT` / `JUDGMENT_COUNT` / `EXTRACT_FAILED_COUNT`.
- **ui-mode** (per ADR-0025 D1). Tool boundary adds `mcp__playwright__*` (Tier-4 third-party justified per [ADR-0022](../../decisions/0022-docs-first-kb-pattern.md) D2 escape clause + [ADR-0025](../../decisions/0025-qa-tester-ui-mode-playwright.md) D2). Input: LLM-extracted click recipes + `ui-mode` prompt token. Process: **dogfood self-test FIRST** per [ADR-0025](../../decisions/0025-qa-tester-ui-mode-playwright.md) D5 (ABORT if dogfood fails); then per-step Playwright MCP calls; LLM-judges each screenshot per [ADR-0025](../../decisions/0025-qa-tester-ui-mode-playwright.md) D3 emitting `PASS` / `PROVISIONAL_PASS` / `FAIL`. Trailer extensions: `UI_PASS_COUNT` / `UI_PROVISIONAL_PASS_COUNT` / `UI_FAIL_COUNT` / `UI_CAPTURED_ISSUES`.

Mode selection: caller's invocation prompt. `ui-mode` token → ui-mode; otherwise bash-mode default. Both modes in one prompt → `RESULT: INVALID_INPUT` per [ADR-0025](../../decisions/0025-qa-tester-ui-mode-playwright.md) D1. `/qa-plan` auto-router deferred to PRD-Q2 per [ADR-0025](../../decisions/0025-qa-tester-ui-mode-playwright.md) OQ-3.

**JUDGMENT / PROVISIONAL_PASS handling:** bash-mode JUDGMENT + EXTRACT_FAILED rows return to the writer; the writer renders them via `AskUserQuestion` in main-agent context per [ADR-0020](../../decisions/0020-qa-automation-writer-executor.md) D5. ui-mode PROVISIONAL_PASS is different: per [ADR-0025](../../decisions/0025-qa-tester-ui-mode-playwright.md) D4 the executor auto-creates a `captured`-labeled issue (3-part body per CLAUDE.md rule #13 / [ADR-0024](../../decisions/0024-root-cause-workflow-capture-discipline.md) D3) and invokes `/promote-to-backlog` inline per [ADR-0008](../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D3. PROVISIONAL_PASS counts as PASS for aggregation — never halts/blocks.

**PRD disposition + auto-close** per [ADR-0020](../../decisions/0020-qa-automation-writer-executor.md) D5: on all-mechanical-PASS + all-judgment-ACCEPT, the writer auto-closes the PRD with `gh issue close --reason completed`. On any mechanical FAIL the writer halts with `AskUserQuestion` (accept-FAIL / reopen-for-fix / cull-as-won't-fix). Writer's trailer adds `PRD_DISPOSITION` extension (`closed-completed` / `reopened-for-fix` / `culled` / `left-open-pending-fix`).

**Terminal human checkpoint** per [ADR-0003](../../decisions/0003-autonomous-pipeline-with-critics.md) D4, refined per [ADR-0020](../../decisions/0020-qa-automation-writer-executor.md) D10: humans judge subjective outcomes via `AskUserQuestion`; agents handle mechanical verification. PRD #147 dogfood reduced PRD-close cycle from ~80 min → ~5 min.

**6-critic-cap honored** per [ADR-0020](../../decisions/0020-qa-automation-writer-executor.md) D9 + [ADR-0025](../../decisions/0025-qa-tester-ui-mode-playwright.md) D6: `qa-tester` is GENERATOR, not critic. [ADR-0008](../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D7 6-critic-cap unaffected.

**Bootstrap-mode (forward-only):** per [ADR-0020](../../decisions/0020-qa-automation-writer-executor.md) D8 + [ADR-0025](../../decisions/0025-qa-tester-ui-mode-playwright.md) D8: writer/executor binds FORWARD from each ADR's slice-1 merge. Closed PRDs (#1-#13 + #147) not retroactively re-QA'd. ui-mode binds FORWARD from its own slice-1 merge.

**Tier 2 + Tier 3** per backlog #57: [ADR-0020](../../decisions/0020-qa-automation-writer-executor.md) D6/D7 deferred Tier 2 (agentic semantic QA) and Tier 3 (UI/browser). [ADR-0025](../../decisions/0025-qa-tester-ui-mode-playwright.md) fulfilled Tier 3. Tier 2 remains deferred.

## Sources

ADRs:

- [ADR-0003](../../decisions/0003-autonomous-pipeline-with-critics.md) D4 — terminal human checkpoint (refined by ADR-0020 D10)
- [ADR-0005](../../decisions/0005-output-shape-and-slicing-methodology.md) D1c — canonical GENERATOR trailer schema
- [ADR-0008](../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D3 — inline-firing `/promote-to-backlog` (ui-mode invokes per PROVISIONAL_PASS)
- [ADR-0008](../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D7 — 6-critic-cap meta-rule
- [ADR-0020](../../decisions/0020-qa-automation-writer-executor.md) — primary writer/executor spec; D1-D2-D4-D10 all active; D3 narrowed by ADR-0025 D1.
- [ADR-0022](../../decisions/0022-docs-first-kb-pattern.md) D2 — source-tier hierarchy + escape clause (Playwright Tier-4)
- [ADR-0024](../../decisions/0024-root-cause-workflow-capture-discipline.md) D1/D3 — rule #13 + 3-part body shape (PROVISIONAL_PASS captures follow)
- [ADR-0025](../../decisions/0025-qa-tester-ui-mode-playwright.md) — ui-mode spec; D1 supersedes ADR-0020 D3 tool-boundary; D1-D9 active.

Subagents + skills:

- [`.claude/agents/qa-tester.md`](../../.claude/agents/qa-tester.md) — dual-mode executor body
- [`.claude/skills/qa-plan/SKILL.md`](../../.claude/skills/qa-plan/SKILL.md) — writer skill body

CLAUDE.md: "Pipeline operational logic" → "How to run a QA plan" — narrative entry.

External: backlog [#57](https://github.com/vojtech-stas/project-claude/issues/57); PRD [#147](https://github.com/vojtech-stas/project-claude/issues/147) (5-min vs 80-min metric source); PRD [#166](https://github.com/vojtech-stas/project-claude/issues/166); PRD [#215](https://github.com/vojtech-stas/project-claude/issues/215) (PRD-Q1; ADR-0025 source).
