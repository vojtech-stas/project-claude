# ADR-0049: Claude_Preview MCP as qa-tester browser driver — replaces Playwright

- **Status:** Accepted
- **Date:** 2026-06-05
- **Supersedes:** [ADR-0025](0025-qa-tester-ui-mode-playwright.md) D2 — the Playwright MCP driver choice; the "less-documented" rationale for rejecting Claude Preview in ADR-0025 Alt-D is overtaken by empirical evidence (Playwright MCP absent in the environment; Claude_Preview MCP verified working). ADR-0025 D1/D3/D4/D5 (dual-mode, LLM-judge, PROVISIONAL capture, dogfood concept) are **preserved**; only D2's driver implementation changes via this ADR.
- **Extends:** [ADR-0037](0037-production-verification-gate.md) D2/D3 — the browser route (Claude_Preview is the verified-working driver that makes D2's browser route actually run); D3 (orchestrator-enforced proof-posting extends D3's orchestrator-owns-enforcement model).

## Context

ADR-0025 established the qa-tester ui-mode and production-verify browser route as driven by Playwright MCP (`mcp__playwright__*`, per ADR-0025 D2). ADR-0037 extended this with a mandatory blocking production-verify gate.

**The machinery was wired to a driver that does not exist in this environment.** A tool enumeration on 2026-06-05 confirms: no `mcp__playwright__*` tools are available; only `mcp__Claude_Preview__*` is present. As a result, the "mandatory" visual QA gate silently cannot run for UI features here — its dogfood self-test aborts (or the tools simply don't exist), and the gate contributes no UI coverage.

**Concrete failure this caused:** during the 2026-06-04/05 dashboard QA session, two real dashboard defects were caught **only by manual click-through**, not by the automated gate that is supposed to guarantee "the UI actually works":
- [#550](https://github.com/vojtech-stas/project-claude/issues/550) — Health DOCS-1 shows false dangling refs (regex misparses zero-padded ADR ids).
- [#551](https://github.com/vojtech-stas/project-claude/issues/551) — Live tab opens on an empty default + 2336 events bucketed as session `unknown`.

A second gap also exists: the prior browser route captured screenshots at ephemeral local paths — never posted where the human reviewing the PR can see them.

**ADR-0025 Alt-D** (which rejected Claude Preview as "less-documented for QA-shape use cases") is now overtaken by empirical evidence: Claude_Preview drove the full 2026-06-04/05 dashboard QA successfully. The "less-documented" concern is superseded by the demonstrated capability and, critically, by the absence of any alternative — Playwright MCP is simply not available and cannot be assumed installable in a harness-provided-tools environment.

This ADR is the macro-ADR for PRD [#552](https://github.com/vojtech-stas/project-claude/issues/552) drafted alongside the PRD per the macro-ADR convention ([ADR-0003](0003-autonomous-pipeline-with-critics.md) D8). The ADR file is authored in slice 1 per that convention.

## Decisions

### D1: Claude_Preview MCP replaces Playwright MCP as the qa-tester browser driver

Claude_Preview MCP (`mcp__Claude_Preview__*`) is the qa-tester browser driver for ui-mode and the production-verify browser route, effective from the merge of slice #553.

**Justification:** Playwright MCP is absent in the environment (verified by tool enumeration on 2026-06-05: no `mcp__playwright__*` tools available). Claude_Preview MCP is present and demonstrated working — it drove the full 2026-06-05 dashboard QA end-to-end. The "Playwright absent / Claude_Preview verified working" empirical evidence supersedes ADR-0025 D2's "Playwright preferred" rationale.

**Scope of supersession:** This ADR supersedes [ADR-0025](0025-qa-tester-ui-mode-playwright.md) D2 only. ADR-0025 D1 (dual-mode contract), D3 (LLM-judge verdict shape), D4 (PROVISIONAL_PASS auto-captures), and D5 (dogfood self-test concept) are PRESERVED unchanged. The dogfood self-test (ADR-0025 D5) is preserved in concept — its tool calls change via D2 below (from `mcp__playwright__*` to `mcp__Claude_Preview__*`), but the pattern (write tmp HTML via Bash, start a preview session against it, click the dogfood button, judge "PASS" text via `preview_snapshot`, abort on failure, clean up on exit) is the same discipline.

**Bootstrap-mode:** This swap binds **forward from slice #553's merge**. In-flight runs loaded before this merge continue using their loaded qa-tester body; no retroactive sweep.

### D2: Tool-boundary update — `mcp__Claude_Preview__*` replaces `mcp__playwright__*`

qa-tester ui-mode and production-verify browser route drop all `mcp__playwright__*` calls and gain `mcp__Claude_Preview__*`. bash-mode tool boundaries are unchanged.

**Playwright → Claude_Preview mapping:**

| Playwright tool | Claude_Preview equivalent | Notes |
|---|---|---|
| `browser_navigate` | `preview_start` (reads `.claude/launch.json`; dashboard config: `name:"dashboard"`, port 8765) | `preview_start` returns a `serverId` used by all subsequent calls; reload via `preview_eval` `location.reload()` |
| `browser_click` | `preview_click` (CSS selector) | |
| `browser_type` | `preview_fill` | |
| `browser_snapshot` | `preview_snapshot` (accessibility tree) | PRIMARY pass/fail evidence per ADR-0040 D5 |
| `browser_take_screenshot` | `preview_screenshot` | Returns inline JPEG; subject to hidden-window timeout (see D4) |
| `browser_evaluate` | `preview_eval` | Last-resort disambiguator only (ADR-0040 D5); eval-only proof → PROVISIONAL not PASS |
| (console errors) | `preview_console_logs` with `level:"error"` | Preferred over eval-ing `window.__consoleErrors` |
| `browser_wait_for` | No direct equivalent | Poll via `preview_eval` (Promise+setInterval) or rely on `preview_snapshot` stability |
| `browser_close` | `preview_stop` (by serverId) | Always call on exit for cleanup |

**serverId discipline:** `preview_start` returns a `serverId` that MUST be passed to every subsequent `preview_*` call in the session. The qa-tester agent MUST record this value after `preview_start` and include it in every subsequent call.

**Updated `tools:` frontmatter:** The qa-tester agent frontmatter lists `mcp__Claude_Preview__preview_start`, `mcp__Claude_Preview__preview_stop`, `mcp__Claude_Preview__preview_click`, `mcp__Claude_Preview__preview_fill`, `mcp__Claude_Preview__preview_snapshot`, `mcp__Claude_Preview__preview_screenshot`, `mcp__Claude_Preview__preview_console_logs`, `mcp__Claude_Preview__preview_eval` instead of `mcp__playwright__*`.

### D3: Proof-posting — orchestrator commits proof, qa-tester returns the path (extends ADR-0037 D2/D3)

After the qa-tester browser route captures a proof (screenshot image or canvas-export PNG), it returns the proof file path in its `ARTIFACTS` trailer field. The **orchestrator** (`/build` step 5, `/ship` gate) then:
1. Commits the image to the PR branch at `qa-proof/<prd-num>/<slug>.png`.
2. Posts a PR comment embedding the image via its raw GitHub URL (`raw.githubusercontent.com/<owner>/<repo>/<branch>/qa-proof/...`), so the reviewer and the user see the rendered proof inline in the PR.

**qa-tester stays read-only (no `gh`/`git` mutation calls)** — consistent with ADR-0020 D4 (the orchestrator owns the audit-trail). qa-tester's job is to capture the proof locally and report the path; the orchestrator's job is to post it.

This extends [ADR-0037](0037-production-verification-gate.md) D2 (browser route) and D3 (orchestrator-enforced): the orchestrator enforcement domain expands from "blocking on FAIL" to "committing proof + embedding it in the PR".

### D4: Screenshot fallback chain — `preview_screenshot` first; fallback to `preview_snapshot` + canvas-export (extends ADR-0037 D2)

The browser route MUST NEVER hang on a blocked screenshot. An observed real failure mode: `preview_screenshot` times out (~30s) when the preview window is backgrounded (`document.visibilityState:"hidden"` — the browser issues no compositor frames in this state). The qa-tester must detect this condition and fall back immediately.

**Fallback chain (applied in order for every screenshot attempt in the browser route):**

1. **Try `preview_screenshot`** — if it returns within ~15s, use the inline JPEG as secondary visual proof.
2. **On timeout or hidden-window** — fall back to:
   - **`preview_snapshot`** (accessibility-tree text) — PRIMARY proof-of-record, always available. This is the authoritative pass/fail evidence per ADR-0040 D5; the snapshot IS the proof, not a fallback to something less authoritative.
   - **Canvas-export image** (for canvas-heavy pages such as the dashboard): start a throwaway HTTP receiver via `Bash`; `preview_eval` the page to `canvas.toDataURL()` and `fetch`-POST the base64 to the receiver; the receiver writes the decoded PNG to `qa-proof/<prd-num>/canvas-export-<timestamp>.png`. This path is the `PROOF` value and the `ARTIFACTS` return.

**`preview_snapshot` is ALWAYS the primary evidence.** The screenshot / canvas-export is secondary supporting proof for the human reviewing the PR. A gate that passes based solely on screenshot is not more reliable than one that passes based on the accessibility-tree snapshot — they are complementary, with the snapshot being the machine-readable primary signal.

### D5: Parsimony + agent caps honored — no new critic, qa-tester stays a generator

This ADR adds NO new critic. Per [ADR-0046](0046-codebase-critic-and-parsimony-reframe.md) D1 (critic parsimony — the gate on adding a critic is a parsimony principle, not a number-cap), adding a critic requires an ADR that justifies a distinct concern no existing critic absorbs. The driver swap is a tool-boundary change within an existing generator; it does not change qa-tester's role as a generator (emits PASS/FAIL, does not generate APPROVE/BLOCK verdicts).

qa-tester remains a GENERATOR per ADR-0020 D9 and ADR-0025 D6. The orchestrator (not qa-tester) enforces the blocking decision per ADR-0037 D3. Extend, not sibling — per ADR-0025 Alt-B rationale.

## Consequences

### Positive

- **The visual QA gate actually runs.** The browser route works end-to-end in the environment where it was previously inoperable (Playwright MCP absent). The concrete dashboard defects (#550, #551) that slipped past the automated gate would have been caught.
- **Zero new dependency.** Claude_Preview is harness-provided; no install step (unlike Playwright, which required `npx -y @playwright/mcp@latest` per ADR-0025 D7 / ADR-0030).
- **Proof is visible on the PR.** The orchestrator proof-posting (D3) ensures the human reviewer and user see the rendered screenshot / snapshot inline — not an ephemeral local path in the trailer.
- **Fallback chain is robust.** The D4 chain guarantees the gate completes even when the preview window is backgrounded; it never hangs on a screenshot timeout.
- **ADR-0025 D1/D3/D4/D5 discipline preserved.** The dual-mode contract, LLM-judge verdict shape, PROVISIONAL_PASS captures, and dogfood self-test concept all stand — only the tool calls change.

### Negative / Accepted

- **Hard-swap, no Playwright fallback.** Consumer forks that have Playwright MCP available do not get a driver-selection option in v1. The Playwright path is documented as a future direction (re-add behind a capability check in a future PRD if the environment gains Playwright).
- **ADR-0025 D7 bootstrap.sh step becomes vestigial.** The `npx -y @playwright/mcp@latest` install step added by ADR-0025 D7 / ADR-0030 is now unnecessary (Claude_Preview needs no install). Deprecating/removing it is a follow-on housekeeping item; it does not break anything if left.
- **canvas-export recipe complexity.** The throwaway HTTP receiver pattern is non-trivial to implement correctly each run. This is accepted: it only fires on canvas-heavy pages when `preview_screenshot` times out — the common case (non-canvas, or screenshot available) is simpler.
- **`preview_screenshot` hidden-window gotcha.** The ~30s timeout when backgrounded is an observed real failure mode. D4's fallback chain handles it, but the root cause (OS compositor behavior) is outside qa-tester's control.

### Neutral

- No new agent, no new critic, no new skill. Net new files: `decisions/0049-*.md` (this ADR) + the qa-tester.md rewrite.
- bootstrap.sh vestigial Playwright step is left as-is for now (zero breaking change; future cleanup).

## Alternatives considered

- **Alt-A (rejected): keep Playwright + install the MCP.** Rejected because this is a harness-provided-tools-only environment where Playwright MCP is absent and cannot be assumed installable. The template's design constraint (minimal external dependencies, harness-provided tooling preferred) makes Playwright an inappropriate default. Even if installable, it would require bootstrap.sh changes, per-machine setup friction, and CI configuration — none of which are needed with Claude_Preview.

- **Alt-B (rejected): multi-driver abstraction layer with auto-detection.** Rejected as YAGNI for v1. A driver-selector (check which MCP tools are available, route to the appropriate driver) is a clean architectural pattern, but it doubles the implementation surface without providing value in the current single-environment deployment. If a consumer fork needs Playwright, a future PRD can re-add it behind a capability check.

- **Alt-C (prior rejection now overtaken): ADR-0025 Alt-D — Claude Preview "less-documented."** ADR-0025 explicitly rejected Claude Preview in its Alternatives section (Alt-D): "less-documented for QA-shape use cases; not endorsed by Anthropic's best-practices doc for this specific scenario." This rejection is now overtaken by two empirical facts: (1) Playwright MCP is absent — the "preferred" option is simply unavailable; (2) Claude_Preview demonstrably drove the full 2026-06-05 dashboard QA end-to-end, producing real proof. The "less-documented" concern is moot when the alternative does not exist in the environment.

- **Alt-D (rejected): advisory-only gate (no blocking).** Rejected — the gate's value is precisely that it blocks. An advisory gate reproduces the same "merged but doesn't actually work" failure mode ADR-0037 was designed to close.

- **Alt-E (rejected): per-slice browser gate** (instead of per-PRD). Rejected for the same reason as ADR-0037's Alt-C: individual slices — especially ADR/docs/refactor — are not independently runnable; the overhead would be high for mostly-non-visual slices.

## References

- PRD [#552](https://github.com/vojtech-stas/project-claude/issues/552) — parent PRD; slice [#553](https://github.com/vojtech-stas/project-claude/issues/553) (this ADR ships in slice 1 per ADR-0003 D8).
- Empirical evidence: tool enumeration 2026-06-05 returns no `mcp__playwright__*` (only `mcp__Claude_Preview__*`); Claude_Preview drove the full 2026-06-05 dashboard QA.
- Missed defects: [#550](https://github.com/vojtech-stas/project-claude/issues/550) (false dangling refs), [#551](https://github.com/vojtech-stas/project-claude/issues/551) (empty Live tab + unknown session bucket).
- [ADR-0003](0003-autonomous-pipeline-with-critics.md) D8 — macro-ADR convention (this ADR drafted alongside PRD #552; ships in slice 1).
- [ADR-0025](0025-qa-tester-ui-mode-playwright.md) — D2 superseded (Playwright driver); D1/D3/D4/D5 preserved; Alt-D overturned.
- [ADR-0037](0037-production-verification-gate.md) — D2/D3 extended (browser route driver + proof-posting).
- [ADR-0040](0040-qa-human-residual-model.md) D5 — browser-route fidelity (real-click primary, eval last-resort); preserved unchanged.
- [ADR-0046](0046-codebase-critic-and-parsimony-reframe.md) D1 — critic parsimony principle; D5 honored (no new critic).
- [ADR-0020](0020-qa-automation-writer-executor.md) D9 — qa-tester is a generator role; preserved.
- `.claude/agents/qa-tester.md` — primary edit (ui-mode + production-verify browser route rewritten to Claude_Preview).
- `decisions/README.md` — ADR-0049 index row (added by this slice's cascade-doc update).
- `CLAUDE.md` — Map row for qa-tester updated (three-mode operation description; Playwright reference removed).
