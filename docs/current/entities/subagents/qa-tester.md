---
title: qa-tester — dual-mode QA-plan executor subagent (bash-mode + ui-mode)
summary: Generator subagent dispatched by the `/qa-plan` writer; bash-mode walks a 3-column Markdown plan row-by-row running each bash check and returns a per-criterion verdict table + canonical GENERATOR trailer with PASS/FAIL/JUDGMENT/EXTRACT_FAILED counts; ui-mode runs a dogfood Playwright self-test first, then drives click recipes step-by-step with LLM-judged screenshots emitting PASS/PROVISIONAL_PASS/FAIL with PROVISIONAL_PASS auto-capturing a `captured`-labeled issue. Mechanical execution only — never posts to GitHub (bash-mode), never modifies tracked files, never calls another subagent.
tags: [subagent, generator, qa-automation, executor, qa-tester, dual-mode, playwright]
type: entity
last_updated: 2026-05-27
sources:
  - .claude/agents/qa-tester.md
  - decisions/0020-qa-automation-writer-executor.md
  - decisions/0025-qa-tester-ui-mode-playwright.md
  - decisions/0005-output-shape-and-slicing-methodology.md
  - decisions/0008-workflow-autolog-bootstrap-and-naming.md
  - decisions/0024-root-cause-workflow-capture-discipline.md
---

# qa-tester

The `qa-tester` subagent is the **executor half of the QA writer/executor split** per [ADR-0020](../../../decisions/0020-qa-automation-writer-executor.md) D1, extended to dual-mode (bash + UI) per [ADR-0025](../../../decisions/0025-qa-tester-ui-mode-playwright.md) D1. Dispatched by the `/qa-plan` writer skill (which runs in main-agent context so it can call `AskUserQuestion`), qa-tester runs in an isolated subagent context so deterministic mechanical work stays out of main. It is the 3rd generator subagent (alongside `slicer`, `implementer`; `current-state-reader` is the 4th), honoring the [ADR-0008](../../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D7 6-critic-cap.

This entity note is the **canonical full role synthesis** for the qa-tester subagent. After the T4 knowledge-architecture migration ([ADR-0031](../../../decisions/0031-knowledge-architecture-v2.md) D10 step 4 of 9, PRD #283 slice 10), the operational [`.claude/agents/qa-tester.md`](../../../.claude/agents/qa-tester.md) carries only the prompt-level operational mechanics (frontmatter incl. the `tools:` allowlist, role identity, mandatory reading order, mode-selection contract enough that the executor picks the right path, tool boundaries verbatim — security-critical) and links here for the full role synthesis, process details, output-shape detail, dogfood discipline, and PROVISIONAL_PASS capture flow.

## Role and responsibility

The qa-tester has one job, in two modes, in strict separation order:

1. **bash-mode (default)** — accept a 3-column Markdown plan from the writer, walk each row sequentially (per [ADR-0020](../../../decisions/0020-qa-automation-writer-executor.md) D3 per-criterion attribution), execute each bash check via the `Bash` tool, classify rows as **mechanical check** (column 2 is runnable shell), **judgment row** (column 2 is literally `JUDGMENT`), or **EXTRACT_FAILED** (column 2 is malformed/unparseable per [ADR-0020](../../../decisions/0020-qa-automation-writer-executor.md) D2), and emit per-criterion verdicts + canonical [GENERATOR trailer](../../concepts/glossary/generator-trailer.md) with `PASS_COUNT` / `FAIL_COUNT` / `JUDGMENT_COUNT` / `EXTRACT_FAILED_COUNT` per-agent extensions.
2. **ui-mode (per ADR-0025 D1)** — accept LLM-extracted click recipes from the writer plus the explicit `ui-mode` prompt token, **run the dogfood self-test FIRST** per [ADR-0025](../../../decisions/0025-qa-tester-ui-mode-playwright.md) D5 (ABORT with `INVALID_INPUT` if dogfood fails — false verdicts would mislead the writer), then drive each recipe step (`navigate` / `click` / `fill` / `screenshot` / `wait`) via `mcp__playwright__*`, LLM-judge each screenshot multimodally per [ADR-0025](../../../decisions/0025-qa-tester-ui-mode-playwright.md) D3 (`PASS` / `PROVISIONAL_PASS` / `FAIL`), aggregate per-step verdicts into per-criterion verdicts, and emit the trailer with `UI_PASS_COUNT` / `UI_PROVISIONAL_PASS_COUNT` / `UI_FAIL_COUNT` / `UI_CAPTURED_ISSUES` extensions.

It does NOT post a verdict to the PRD (the writer owns the audit-trail comment per [ADR-0020](../../../decisions/0020-qa-automation-writer-executor.md) D4), does NOT render JUDGMENT / EXTRACT_FAILED rows via `AskUserQuestion` (subagents lack the tool — the writer renders), does NOT invoke another subagent (no `Agent` tool), does NOT modify any tracked file (no `Write`/`Edit` — even ui-mode dogfood HTML goes via `Bash` to a tmp path per [ADR-0025](../../../decisions/0025-qa-tester-ui-mode-playwright.md) D5).

## Mode-selection contract

Per [ADR-0025](../../../decisions/0025-qa-tester-ui-mode-playwright.md) D1 the two modes are mutually exclusive within a single invocation. Selection logic:

- **`ui-mode` token absent** → bash-mode (default; original [ADR-0020](../../../decisions/0020-qa-automation-writer-executor.md) D3 behavior). Input shape: 3-column Markdown table (`criterion # | bash check or "JUDGMENT" | expected result`). Tool boundary: `Read, Bash, Grep` only.
- **`ui-mode` token present** → ui-mode. Input shape: YAML-shaped click recipes (criterion → steps). Tool boundary: bash-mode set + `mcp__playwright__*` (Tier-4 third-party per [ADR-0022](../../../decisions/0022-docs-first-kb-pattern.md) D2 escape clause + [ADR-0025](../../../decisions/0025-qa-tester-ui-mode-playwright.md) D2).
- **Both modes requested in one prompt** → `RESULT: INVALID_INPUT` with reason `"mode ambiguous — caller must pick bash-mode or ui-mode per ADR-0025 D1"`.

`/qa-plan` auto-router classifier (which would pick the mode automatically based on PRD §2 acceptance-criteria shape) is deferred to PRD-Q2 per [ADR-0025](../../../decisions/0025-qa-tester-ui-mode-playwright.md) OQ-3 — until then ui-mode is invoked explicitly.

## Process

### bash-mode process

For each row in plan order (sequential walk, NOT parallel):

1. **Classify the row** — mechanical / judgment / EXTRACT_FAILED per the column-2 shape.
2. **Mechanical check** → run the bash command, capture stdout/stderr/exit code. Verdict = `PASS` when exit code is `0` AND expected result matches (literal substring against stdout, OR numeric expression `>=`/`<=`/`==`/`>`/`<`/`!=` parsed as integer comparison, OR `/regex/` matched against stdout). Otherwise `FAIL` with detail (exit code, last line of stderr, or expected-vs-actual mismatch). **Default-conservative on ambiguous match**: render verdict `FAIL` with detail `"ambiguous match — manual review"` rather than guess PASS — the writer turns this into a judgment Q.
3. **Judgment row** → no bash; verdict = `JUDGMENT`; copy expected-result text verbatim to Detail for the writer's `AskUserQuestion` per [ADR-0020](../../../decisions/0020-qa-automation-writer-executor.md) D5.
4. **EXTRACT_FAILED row** → no bash; verdict = `EXTRACT_FAILED`; raw column-2 text in Detail. Writer treats EXTRACT_FAILED identically to JUDGMENT per [ADR-0020](../../../decisions/0020-qa-automation-writer-executor.md) D2.

Accumulate verdicts; compute `PASS_COUNT` / `FAIL_COUNT` / `JUDGMENT_COUNT` / `EXTRACT_FAILED_COUNT`; emit the verdict table + canonical trailer per [[topics/output-shapes]] and stop.

### ui-mode process

1. **Dogfood self-test FIRST** per [ADR-0025](../../../decisions/0025-qa-tester-ui-mode-playwright.md) D5 — write tmp HTML via `Bash` (keyed on `CLAUDE_SESSION_ID` to avoid collision per ADR-0025 OQ-2), `mcp__playwright__browser_navigate file://...`, `browser_click #dogfood-btn`, `browser_take_screenshot`, multimodally judge whether "PASS" text is visible. If PASSED → proceed; if FAILED → ABORT with `RESULT: INVALID_INPUT` and reason `"dogfood self-test failed — Playwright MCP wiring broken; aborting per ADR-0025 D5"`. ALWAYS `rm -f` the dogfood path on exit.
2. **Per-recipe execution** in plan order (sequential per ADR-0025 D1 step 3). For each step: invoke matching `mcp__playwright__*` tool; on Playwright error → step verdict = `FAIL` with the Playwright error message; otherwise take a screenshot.
3. **Per-step LLM-judgment** per [ADR-0025](../../../decisions/0025-qa-tester-ui-mode-playwright.md) D3:
   - **`PASS`** — high-confidence the screenshot matches the recipe's `expected`. Proceed to next step.
   - **`PROVISIONAL_PASS`** — uncertain. Trigger the capture flow below. Treat as PASS for aggregation. Proceed.
   - **`FAIL`** — high-confidence mismatch OR Playwright errored. Record detail. Halt the recipe (record remaining steps as `SKIPPED`) and move to next recipe.
4. **Per-criterion aggregation** — all PASS or PROVISIONAL_PASS → PASS; any FAIL → FAIL.
5. **Cleanup** — `mcp__playwright__browser_close` + `rm -f "$DOGFOOD_PATH"`.

## PROVISIONAL_PASS capture flow (ui-mode only)

Per [ADR-0025](../../../decisions/0025-qa-tester-ui-mode-playwright.md) D4 + CLAUDE.md rule #13: every `PROVISIONAL_PASS` verdict auto-creates a `captured`-labeled issue via `Bash` (`gh issue create` — the **single ui-mode exemption** to the `gh` mutation forbidance; `gh pr create`/`gh pr merge` remain forbidden). Body follows the 3-part Symptom / Root cause / Proposed workflow change shape per [ADR-0024](../../../decisions/0024-root-cause-workflow-capture-discipline.md) D3 — root cause is the LLM-judge's verbatim uncertainty reason; proposed change names the user-rescue path (add a reference-image or pixel-diff hash to the PRD AC to convert future runs from LLM-judge to mechanical match). Then invoke `/promote-to-backlog` inline per [ADR-0008](../../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D3 — `backlog-critic` fires once (no ≤3-round loop in autopilot mode); either APPROVE or BLOCK is acceptable, do NOT block your own execution on the autopilot's verdict. Increment `UI_CAPTURED_ISSUES` in the trailer. Continue — PROVISIONAL_PASS never halts the recipe; ambiguity surfaces for human cadence rather than blocking the pipeline (preserving the "human out of loop" 2026-05-24 motivation per ADR-0025 Context).

## Output shape

Two parts in both modes — verdict table then canonical [GENERATOR trailer](../../concepts/glossary/generator-trailer.md) per [[topics/output-shapes]].

- **bash-mode trailer extensions** (per ADR-0005 D1c + ADR-0020 D9): `PASS_COUNT` / `FAIL_COUNT` / `JUDGMENT_COUNT` / `EXTRACT_FAILED_COUNT`. Sum equals row count on SUCCESS/FAIL; all four = `0` on INVALID_INPUT. `ARTIFACTS:` empty (writer owns artifact persistence).
- **ui-mode trailer extensions** (per ADR-0005 D1c + ADR-0025 D1): `UI_PASS_COUNT` / `UI_PROVISIONAL_PASS_COUNT` / `UI_FAIL_COUNT` / `UI_CAPTURED_ISSUES`. `ARTIFACTS:` enumerates the URLs of `captured`-labeled issues opened.
- `RESULT: SUCCESS` when **every** row/criterion verdict is PASS / JUDGMENT / EXTRACT_FAILED (bash-mode) or every per-criterion aggregate is PASS (ui-mode). `RESULT: FAIL` on any FAIL row/criterion. `RESULT: INVALID_INPUT` on malformed input, missing `ui-mode` token, dogfood failure, or mode-ambiguous prompt.

## Tool boundaries — SECURITY-CRITICAL

Per [ADR-0020](../../../decisions/0020-qa-automation-writer-executor.md) D3 (narrowed by [ADR-0025](../../../decisions/0025-qa-tester-ui-mode-playwright.md) D1 — all other ADR-0020 decisions preserved):

- **bash-mode allowed:** `Read`, `Bash`, `Grep`.
- **ui-mode allowed:** bash-mode set + `mcp__playwright__browser_navigate`, `_click`, `_type`, `_take_screenshot`, `_snapshot`, `_wait_for`, `_evaluate`, `_close`.
- **Forbidden in BOTH modes:** `Agent` (no nested subagent dispatch — sequential walk is the only flow); `Write` / `Edit` (verification is read-only; ui-mode dogfood HTML goes via `Bash` to a tmp path, NOT via `Write`/`Edit` — preserves the "zero tracked file" contract per [ADR-0025](../../../decisions/0025-qa-tester-ui-mode-playwright.md) D5); `AskUserQuestion` (not available to subagents per Claude Code architecture — judgment rendering is the writer's job); `gh pr create`/`gh pr comment`/`gh pr merge` (writer owns audit trail; ui-mode `gh issue create` for PROVISIONAL_PASS captures is the single exemption per [ADR-0025](../../../decisions/0025-qa-tester-ui-mode-playwright.md) D4).

If the executor finds itself wanting any forbidden capability, that is the signal that the input is wrong-shape or the writer skill needs extension — return `INVALID_INPUT` with a one-sentence reason rather than improvise.

## Adversarial mindset

Treat every bash row / recipe step as **untrusted input from the writer's LLM-extract step** (per ADR-0020 D2 the extraction is non-deterministic at the margins). Paranoid about: plan-shape violations (exactly three columns? column 2 runnable-or-`JUDGMENT`?), expected-result parseability (deterministic comparison possible?), determinism (would re-running produce the same verdict?), Playwright wiring (dogfood is the trust gate — if it fails, abort don't degrade). NOT paranoid about command semantics — those are the writer's concern. Pre-empt INVALID_INPUT and default-conservative FAILs to give the writer clean failure surfaces.

## Failure return modes

- **`RESULT: SUCCESS`** — every row/criterion verdict is PASS (or JUDGMENT/EXTRACT_FAILED in bash-mode; PROVISIONAL_PASS folded as PASS in ui-mode). The writer proceeds to render judgment Qs and auto-close on all-PASS + all-judgment-ACCEPT per [ADR-0020](../../../decisions/0020-qa-automation-writer-executor.md) D5.
- **`RESULT: FAIL`** — at least one row/criterion has verdict FAIL. The writer surfaces the verdict table to the user via `AskUserQuestion` with accept-FAIL / reopen-for-fix / cull-as-won't-fix options per [ADR-0020](../../../decisions/0020-qa-automation-writer-executor.md) D5.
- **`RESULT: INVALID_INPUT`** — input plan malformed (no table, wrong column shape, no parseable rows), `ui-mode` token mismatch, ambiguous mode, or dogfood self-test failed. Verdict table omitted; only the trailer is emitted with all per-agent count extensions = `0`.

## Relationship to other agents

- **Caller:** the [`/qa-plan` writer skill](../../../.claude/skills/qa-plan/SKILL.md) (PRD #166 Tier 1; ui-mode dispatch via PRD #215). The writer LLM-extracts the plan or click recipes, persists the plan as a PRD comment per ADR-0020 D4, dispatches qa-tester, then renders judgment / PROVISIONAL_PASS handling.
- **No adversarial critic** — qa-tester is a generator; quality of its output is bounded by the writer's plan fidelity and qa-tester's own determinism + paranoia discipline. The writer's PRD-disposition step (auto-close on all-PASS or `AskUserQuestion` on any FAIL) is the terminal human checkpoint per [ADR-0003](../../../decisions/0003-autonomous-pipeline-with-critics.md) D4 (refined per ADR-0020 D10).
- **Sibling generators:** [`slicer`](slicer.md), [`implementer`](implementer.md), [`current-state-reader`](current-state-reader.md). qa-tester is the only generator with two modes and the only one with optional ui-mode `gh issue create` mutation (single ADR-0025 D4 exemption).
- **Honors the 6-critic-cap** per [ADR-0008](../../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D7 + [ADR-0020](../../../decisions/0020-qa-automation-writer-executor.md) D9 + [ADR-0025](../../../decisions/0025-qa-tester-ui-mode-playwright.md) D6 — 3rd generator (4 total at the current baseline), critics stay at 6.
- **Authority:** [ADR-0020](../../../decisions/0020-qa-automation-writer-executor.md) D1 (writer/executor split), D2 (LLM-extract + EXTRACT_FAILED), D3 (sequential walk + tool boundaries, narrowed by ADR-0025 D1), D4 (plan as PRD comment), D5 (auto-close + AskUserQuestion), D9 (generator role + 6-critic-cap honored), D10 (refines ADR-0003 D4 terminal human checkpoint). [ADR-0025](../../../decisions/0025-qa-tester-ui-mode-playwright.md) D1 (dual-mode contract + tool-boundary narrowing), D2 (Playwright MCP — Tier-4 escape), D3 (LLM-judge verdict shape), D4 (PROVISIONAL_PASS auto-capture), D5 (dogfood self-test), D6 (6-critic-cap), D7 (bootstrap.sh Playwright install), D8 (forward-only). [ADR-0005](../../../decisions/0005-output-shape-and-slicing-methodology.md) D1c (GENERATOR trailer). [ADR-0024](../../../decisions/0024-root-cause-workflow-capture-discipline.md) D1 + D3 (rule #13 3-part body shape for ui-mode captures).

## Topic synthesis

For the cross-cutting QA-automation synthesis (writer/executor split, PRD-disposition flow, terminal-human-checkpoint placement), see [qa-automation](../../qa-automation.md). Topic migration to `topics/qa-automation.md` deferred to T6 per PRD #283 OQ-4.

## Edges

- **part_of:** [[topics/qa-automation]]
- **related_to:** [[topics/output-shapes]]
- **related_to:** [[topics/pipeline-stages]]
- **related_to:** [[entities/subagents/slicer]]
- **related_to:** [[entities/subagents/implementer]]
- **related_to:** [[entities/subagents/current-state-reader]]
- **related_to:** [[entities/subagents/backlog-critic]]
- **related_to:** [[concepts/glossary/generator-trailer]]
- **defines:** [[decisions/0020-qa-automation-writer-executor]]
- **defines:** [[decisions/0025-qa-tester-ui-mode-playwright]]
