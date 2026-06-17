---
id: ADR-0050
status: accepted
supersedes:
  - ADR-0049
superseded_by: []
scope: verification
rule_ids:
  - VER-007
  - VER-008
---
# ADR-0050: Headless Playwright/Chrome as qa-tester browser driver — replaces Claude_Preview MCP

- **Status:** Accepted
- **Date:** 2026-06-05
- **Supersedes:** [ADR-0049](0049-claude-preview-browser-driver.md) D1 — the Claude_Preview MCP driver choice; [ADR-0049](0049-claude-preview-browser-driver.md) D2 — the `mcp__Claude_Preview__*` tool-boundary update. ADR-0049 D3 (proof-posting by orchestrator) and D5 (parsimony) are **preserved**; D4's screenshot fallback chain (preview_screenshot + preview_snapshot + canvas-export) is **obsoleted** by D1's architectural elimination of the hidden-window problem — the fallback chain was a workaround for Claude_Preview's OS-visibility timeout, which headless rendering has no exposure to.
- **Extends:** [ADR-0037](0037-production-verification-gate.md) D1 — the mandatory blocking gate is preserved and strengthened (headless rendering is reliable regardless of window state); [ADR-0037](0037-production-verification-gate.md) D3 — orchestrator-enforced blocking + qa-tester-stays-a-generator topology is unchanged.

## Context

ADR-0049 established Claude_Preview MCP (`mcp__Claude_Preview__*`) as the qa-tester browser driver, replacing the absent Playwright MCP. During the 2026-06-04/05 sessions, a new failure mode was demonstrated: `preview_screenshot` **times out when the OS preview window is backgrounded** (`document.visibilityState:"hidden"` — the OS compositor issues no frames for hidden windows). The D4 fallback chain (preview_snapshot + canvas-export) was designed to work around this, but it does not produce a real visual screenshot — it either produces an accessibility-tree dump (text) or a canvas-export rasterization that bypasses CSS rendering. Neither is a true "see what a human sees" proof.

**The root cause is architectural:** Claude_Preview drives a visible browser window, and screenshot capture depends on OS-level compositing. Any run where the window is backgrounded — which is the common case in unattended automated runs — hits this timeout. The D4 workaround adds complexity (the throwaway HTTP receiver pattern) but does not solve the underlying problem.

**Empirically demonstrated 2026-06-05:** a **headless browser** — the Playwright Python library driving the already-installed Chrome via `channel="chrome"`, `headless=True` — navigates, clicks, and screenshots all three dashboard tabs to real full-page PNGs with **no window-visibility problem**. The prototype `qa-proof/capture.py` produced clean Architecture/Live/Health captures and asserted DOCS-1/DOCS-10 = PASS and the Live default = a real session. The headless browser renders to its own offscreen buffer; there is no "hidden window" state to trigger the timeout.

This ADR is the macro-ADR for PRD [#574](https://github.com/vojtech-stas/project-claude/issues/574) drafted alongside the PRD per the macro-ADR convention ([ADR-0003](0003-autonomous-pipeline-with-critics.md) D8). The ADR file is authored in slice 1 per that convention.

## Decisions

### D1: Headless Playwright/Chrome replaces Claude_Preview MCP as the qa-tester browser driver

The Playwright Python library driving installed Chrome (`channel="chrome"`, `headless=True`) is the qa-tester browser driver for ui-mode and the production-verify browser route, effective from the merge of slice #575.

**Justification:** Claude_Preview's `preview_screenshot` tool has a fundamental OS-visibility limitation: it times out when the preview window is backgrounded (`document.visibilityState:"hidden"`), which is the common condition in unattended automated runs. This was demonstrated repeatedly in 2026-06-04/05 sessions and documented in ADR-0049 D4's fallback chain. Headless Chrome renders to an offscreen buffer — there is no window to background, no compositor to stall, no timeout to trigger. The prototype (`qa-proof/capture.py`) demonstrates end-to-end: navigate localhost:8765, click three tabs, screenshot each, assert DOCS-1/DOCS-10 PASS. Playwright is already `pip install`ed in this environment and uses the system-installed Chrome (`channel="chrome"`) — no binary download.

**Architectural elimination of the hidden-window problem:** ADR-0049 D4's `preview_screenshot` fallback chain (preview_snapshot + canvas-export) was a workaround for Claude_Preview's hidden-window timeout. That fallback chain is **obsoleted by D1**: headless Chrome renders offscreen, so there is no hidden-window state, no timeout, and no need for a fallback. Playwright `page.screenshot()` is always available.

**ADR-0040 D5 fidelity preserved:** the real-interaction-first fidelity discipline is unchanged. The ordered guarantee is: (1) drive real interaction via `page.click()`, `page.fill()`, `page.goto()` — same semantics as ADR-0040 D5's "real-click primary"; (2) assert via `page.inner_text()` / `page.get_by_text()` / `page.screenshot()` — the human-faithful evidence; (3) `page.evaluate()` is a last-resort disambiguator only, never the primary evidence of a passing check (eval-only proof → PROVISIONAL, not PASS). This mirrors ADR-0049 D3's ordering exactly, with Playwright equivalents.

**Bootstrap-mode (per [ADR-0004](0004-bypass-prevention.md) D2):** This swap binds **forward from slice #575's merge**. In-flight runs loaded before this merge continue using their loaded qa-tester body. Prior qa-tester runs under Claude_Preview are grandfathered; no retroactive re-run required. Future qa-tester invocations loaded after this merge use the headless Playwright driver.

**Scope of supersession:** This ADR supersedes [ADR-0049](0049-claude-preview-browser-driver.md) D1 and D2 only. ADR-0049 D3 (proof-posting: orchestrator commits proof, qa-tester returns the path) is PRESERVED unchanged. ADR-0049 D5 (parsimony honored, no new critic) is PRESERVED. ADR-0025 D1 (dual-mode contract), D3 (LLM-judge verdict shape), D4 (PROVISIONAL_PASS auto-captures), and D5 (dogfood self-test concept) are PRESERVED.

### D2: Tool-boundary update — Playwright `Bash`-driven replaces `mcp__Claude_Preview__*`

qa-tester ui-mode and production-verify browser route drop all `mcp__Claude_Preview__*` calls. The browser route is now driven entirely via `Bash` (writing a short Python script to a tmp path via heredoc, executing it, reading results). The `tools:` frontmatter drops all `mcp__Claude_Preview__*` entries; the browser route retains `Read, Bash, Grep`.

**Driver procedure (generalizing `qa-proof/capture.py`):**

The qa-tester writes a Python script via Bash heredoc to a tmp path (e.g., `/tmp/qa-headless-<session>.py`) — never via `Write`/`Edit` (zero tracked-file discipline, per ADR-0025 D5 dogfood pattern). The script:

1. Uses `sync_playwright()` → `chromium.launch(channel="chrome", headless=True)`
2. Navigates `localhost:8765` (or the declared URL)
3. Clicks tabs via `page.click("button:has-text('...')")` — real interaction per ADR-0040 D5
4. Screenshots each view to `qa-proof/<prd>/<tab>.png`
5. Asserts via `page.inner_text(...)` / `page.get_by_text(...)` — human-faithful evidence
6. Prints PASS/FAIL verdicts + the proof path(s)

The qa-tester reads the script output to determine PASS/FAIL and extracts the proof paths for the `ARTIFACTS` trailer field.

**Claude_Preview → Playwright mapping:**

| Claude_Preview tool | Playwright equivalent | Notes |
|---|---|---|
| `preview_start` | `page.goto(url)` | No serverId; direct URL navigation |
| `preview_stop` | `browser.close()` | Always call at script end |
| `preview_click` | `page.click(selector)` | CSS selector or text-based (`button:has-text(...)`) |
| `preview_fill` | `page.fill(selector, value)` | |
| `preview_snapshot` | `page.inner_text(selector)` / `page.get_by_text(...)` | PRIMARY evidence — text-based assertion |
| `preview_screenshot` | `page.screenshot(path=...)` | Always available in headless mode (no hidden-window timeout) |
| `preview_console_logs` | `page.on("console", ...)` / errors list | Collect before script exit |
| `preview_eval` | `page.evaluate(...)` | Last-resort disambiguator only |
| `browser_wait_for` | `page.wait_for_timeout()` / `page.wait_for_function()` | Direct Playwright API |

### D3: Dogfood self-test updated to headless Playwright

The ui-mode dogfood self-test (ADR-0025 D5) is preserved in concept and updated in implementation. The dogfood self-test:

1. Writes a minimal HTML file to a tmp path via Bash heredoc (e.g., `/tmp/qa-dogfood-<session>.html`) with a clickable button and "PASS" text
2. Writes a short Python script to a tmp path via Bash heredoc that launches a headless browser, navigates to `file:///tmp/qa-dogfood-<session>.html`, clicks the button, asserts `page.inner_text("body")` contains "PASS"
3. Executes the script via Bash; reads stdout for PASS/FAIL
4. On dogfood FAIL → ABORT with `RESULT: INVALID_INPUT`, reason `"dogfood self-test failed — Playwright/Chrome wiring broken; aborting per ADR-0025 D5 / ADR-0050 D3"`
5. Always removes tmp files on exit

This preserves the zero-tracked-file discipline (all tmp writes via Bash, not Write/Edit).

### D4: No new screenshot fallback chain — ADR-0049 D4 is obsoleted

ADR-0049 D4's fallback chain (`preview_screenshot` → timeout-detect → `preview_snapshot` + canvas-export) is **not carried forward**. It was a Claude_Preview-specific workaround for the hidden-window timeout. Headless Chrome has no hidden-window condition; `page.screenshot()` always succeeds in headless mode. No fallback chain is needed or defined for this driver.

### D5: Parsimony + agent caps honored — no new critic, qa-tester stays a generator

This ADR adds NO new critic. Per [ADR-0046](0046-codebase-critic-and-parsimony-reframe.md) D1 (critic parsimony principle), the driver swap is a tool-boundary change within an existing generator. qa-tester remains a GENERATOR per ADR-0020 D9 and ADR-0025 D6. The orchestrator (not qa-tester) enforces the blocking decision per ADR-0037 D3.

## Consequences

### Positive

- **Screenshots always work.** Headless Chrome renders to an offscreen buffer; `page.screenshot()` always returns a real PNG regardless of window visibility, desktop state, or whether the agent is running in the background. The primary failure mode of ADR-0049's driver is eliminated architecturally, not worked around.
- **ADR-0049 D4 fallback chain is obsoleted.** The throwaway HTTP receiver pattern (canvas-export) is no longer needed — a non-trivial recipe that only fired on canvas-heavy pages. Simpler, fewer moving parts.
- **Real visual screenshots.** Unlike ADR-0049's primary proof (accessibility-tree text via `preview_snapshot`), the headless driver produces actual rendered PNG screenshots — closer to "what a human sees."
- **ADR-0040 D5 fidelity fully preserved.** Real click → assert on rendered output is unchanged; `page.evaluate()` remains last-resort.
- **No new dependency beyond Playwright library.** Uses already-installed Chrome (`channel="chrome"`) — no 150 MB chromium download. `pip install playwright` is the only change.

### Negative / Accepted

- **Hard-swap from Claude_Preview.** Runs that currently rely on `mcp__Claude_Preview__*` must update. Bootstrap-mode handles this (D1: binds forward from slice #575 merge).
- **Requires Python + Playwright library.** The qa-tester now depends on `pip install playwright` in the environment (added to bootstrap.sh). Chrome is assumed installed (already true in this environment).
- **Script-via-Bash pattern.** Writing Python scripts via Bash heredoc is less ergonomic than direct tool calls, but preserves the zero-tracked-file discipline (no `Write`/`Edit` in qa-tester) that ADR-0025 D5 mandates. Consistent with the existing dogfood pattern.

### Neutral

- No new agent, no new critic, no new skill. Net new files: `decisions/0050-*.md` (this ADR) + the qa-tester.md rewrite.
- ADR-0049 D4's canvas-export recipe is retired (no longer referenced from qa-tester.md or any live procedure).
- `decisions/README.md` gains an ADR-0050 index row; ADR-0049 Status updated to note D1/D2 superseded.

## Alternatives considered

- **Alt-A (rejected): keep Claude_Preview and require the preview pane to be foregrounded.** This would require the orchestrator to ensure the Claude_Preview window is foregrounded before each screenshot call — imposing an OS/UI state management concern onto every automated QA run. Breaks unattended runs entirely (no human to foreground the window). Rejected: the hidden-window timeout is an OS compositor constraint that cannot be reliably managed programmatically.

- **Alt-B (rejected): in-browser DOM rasterization (canvas-export).** The ADR-0049 D4 canvas-export recipe is an in-browser rasterization workaround: it uses `canvas.toDataURL()` to get image data from `<canvas>` elements only. This has CSS-fidelity caveats (only canvas content, not the full rendered DOM + CSS), requires a throwaway HTTP receiver, and only applies to canvas-heavy pages. Not a general screenshot replacement. Rejected: functional subset of headless screenshot with higher complexity.

- **Alt-C (chosen): headless Playwright/Chrome.** Renders to an offscreen buffer, screenshots always succeed, full CSS fidelity, demonstrated working via `qa-proof/capture.py`. Minimal new dependency (Playwright library only; Chrome already installed). No fallback chain needed. Preserves ADR-0040 D5 real-interaction-first fidelity.

## References

- PRD [#574](https://github.com/vojtech-stas/project-claude/issues/574) — parent PRD; slice [#575](https://github.com/vojtech-stas/project-claude/issues/575) (this ADR ships in slice 1 per ADR-0003 D8).
- Empirical evidence: `qa-proof/capture.py` prototype (2026-06-05) — headlessly navigated localhost:8765, clicked Architecture/Live/Health tabs, screenshotted each, asserted DOCS-1/DOCS-10 PASS.
- Hidden-window timeout: demonstrated in 2026-06-04/05 sessions with Claude_Preview `preview_screenshot`; root cause: `document.visibilityState:"hidden"` stops OS compositor frames.
- [ADR-0049](0049-claude-preview-browser-driver.md) — D1/D2 superseded (Claude_Preview driver + tool-boundary); D3/D5 preserved; D4 fallback chain obsoleted.
- [ADR-0037](0037-production-verification-gate.md) — D1/D3 extended (mandatory gate preserved + strengthened; orchestrator-enforced topology unchanged).
- [ADR-0040](0040-qa-human-residual-model.md) D5 — browser-route fidelity (real-click primary, eval last-resort); preserved unchanged.
- [ADR-0025](0025-qa-tester-ui-mode-playwright.md) — D1/D3/D4/D5 preserved; D7 bootstrap.sh Playwright library install reinstated (library only; no chromium download).
- [ADR-0046](0046-codebase-critic-and-parsimony-reframe.md) D1 — critic parsimony principle; D5 honored (no new critic).
- [ADR-0020](0020-qa-automation-writer-executor.md) D9 — qa-tester is a generator role; preserved.
- [ADR-0004](0004-bypass-prevention.md) D2 — bootstrap-mode policy; D1 forward-binding.
- [ADR-0003](0003-autonomous-pipeline-with-critics.md) D8 — macro-ADR convention (this ADR drafted alongside PRD #574; ships in slice 1).
- `.claude/agents/qa-tester.md` — primary edit (ui-mode + production-verify browser route rewritten to headless Playwright).
- `bootstrap.sh` — `pip install playwright` step added (library only).
- `decisions/README.md` — ADR-0050 index row; ADR-0049 Status updated.
- `CLAUDE.md` — Map row for qa-tester updated.
