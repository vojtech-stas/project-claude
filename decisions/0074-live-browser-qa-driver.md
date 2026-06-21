---
id: ADR-0074
status: accepted
supersedes:
  - ADR-0050 D1
superseded_by: []
scope: verification
rule_ids: []
---
# ADR-0074: Live-browser QA driver — Chrome MCP preferred when connected, headless Playwright fallback

- **Status:** Accepted
- **Date:** 2026-06-21
- **Supersedes:** [ADR-0050](0050-headless-playwright-browser-driver.md) D1 — the headless-only browser driver choice. ADR-0050 D2 (tool-boundary update), D3 (dogfood self-test), D4 (no fallback chain), and D5 (parsimony) are **preserved** with the understanding that D2's tool boundary now extends to include Chrome MCP tools in the live path (see D3 below).
- **Extends:** [ADR-0037](0037-production-verification-gate.md) D2 — production-verify auto-routing by change type; the browser route now auto-selects live-vs-headless internally. [ADR-0050](0050-headless-playwright-browser-driver.md) D1/D2 — the third-generation browser driver, explicitly honoring why ADR-0050 went headless (interactive-MCP-unavailability) while restoring MCP driving when the condition is met. [ADR-0025](0025-qa-tester-ui-mode-playwright.md) — ui-mode foundation preserved.

## Context

ADR-0050 established headless Playwright/Chrome as the qa-tester browser driver, replacing Claude_Preview MCP (ADR-0049). The headless choice was correct for its context: Claude_Preview MCP had a hidden-window timeout that made it unreliable in unattended runs, and the interactive-MCP-availability assumption was unreliable.

In 2026-06-18, the operator connected the **Claude-in-Chrome browser extension** to the session and demonstrated via a spike that: (a) a dispatched subagent can reach the session-connected Chrome MCP (`list_connected_browsers` returns a non-empty list), and (b) `gif_creator` records a full click-through and exports a downloadable GIF with click indicators and action labels. This changes the trade-off space: when a browser is connected, the MCP driver provides a **live**, **video-recorded**, **console-checked** click-through that headless Playwright cannot produce — the agent literally drives the user's browser, sees exactly what the user sees, and records it. The headless path remains the correct fallback for autonomous/mobile-remote/cron runs where no browser is present.

This ADR is the macro-ADR for PRD [#974](https://github.com/vojtech-stas/project-claude/issues/974), authored in slice 1 per [ADR-0003](0003-autonomous-pipeline-with-critics.md) D8.

## Decisions

### D1: Chrome MCP is the PREFERRED browser driver when a browser is connected; headless Playwright is the FALLBACK

When qa-tester's browser route fires, the first action is `list_connected_browsers`. If the result is non-empty (at least one connected browser), the **LIVE path** is taken: qa-tester drives the Chrome MCP (navigate, click through the feature's surface, record a GIF, read the console). If the result is empty or the call fails, the **HEADLESS path** is taken: unchanged ADR-0050 Playwright/Bash driver.

**Justification:** A connected browser provides proof that is strictly superior to headless for user-facing browser changes: it exercises the real browser the user sees (not an offscreen buffer), records a video artifact the operator can watch, checks the live console, and demonstrates the feature as a human would. The ADR-0050 decision was NOT that headless is intrinsically better — it was that the interactive MCP (Claude_Preview) was unreliable because it required a foregrounded OS window in unattended runs. The Claude-in-Chrome extension solves this differently: it is explicitly opt-in (the operator connects it before the run), and the subagent confirms connectivity before choosing the path. When not connected, the headless Playwright driver (ADR-0050) is the correct fallback — it handles all non-interactive (autonomous/mobile-remote/cron) runs cleanly.

**Bootstrap-mode (per [ADR-0004](0004-bypass-prevention.md) D2):** This decision binds **forward from slice #975's merge**. Prior runs under the headless-only driver are grandfathered.

**Absence is not a failure:** a missing or empty `list_connected_browsers` result triggers the headless fallback, never a FAIL-for-lack-of-browser. The gate passes or fails on the feature's behavior, not on whether a browser happened to be connected.

### D2: Live path produces a GIF video artifact + console check as the rule-#20 browser proof

In the LIVE path, qa-tester MUST:
1. Call `gif_creator start_recording` before any navigation.
2. Navigate to the feature URL, click through the feature's declared surface (the "Production check:" line's steps), assert inner_text/rendered output, and read the browser console for errors (`read_console_messages(onlyErrors: true)` on the exercised surface).
3. Call `gif_creator export download:true` to produce the downloadable GIF artifact.
4. Emit the GIF path as the `ARTIFACTS` trailer field (the rule-#20 browser proof artifact becomes a video, not a screenshot).

If the console check finds ≥1 error on the exercised surface, the production-verify verdict is NOT PASS (FAIL or PROVISIONAL as appropriate). This is the mechanization of PRD #974 §2 criterion 5.

The GIF artifact path is ROOT-absolute (per ADR-0061 D5 — `qa-proof/<prd-num>/` or `.claude/logs/review-shots/`).

### D3: Tool-boundary update — Chrome MCP tools added for the live path

qa-tester's `tools:` frontmatter gains the Chrome MCP tools required for the live path: `list_connected_browsers`, `tabs_context_mcp`, `navigate`, `computer`, `read_page`, `find`, `read_console_messages`, `gif_creator`. `ToolSearch` is also added so qa-tester can load deferred tools in bulk when needed.

The headless path retains `Read, Bash, Grep` as its effective tool set — no change to ADR-0050 D2's Bash-driven Playwright pattern.

**Declared-vs-used discipline:** declaring a tool in `tools:` is not a mandate to use it. The live path uses Chrome MCP tools; the headless path uses `Read, Bash, Grep`. The tool set union covers both paths.

### D4: Live path is INTERACTIVE-ONLY — not available in autonomous/cron runs

The Chrome MCP (`list_connected_browsers`) requires an interactive Claude session where the user has connected the browser extension. It is NOT available in: CI runners, cron dispatches, mobile-remote runs, or any dispatch where no browser is connected. In those contexts, `list_connected_browsers` returns empty or errors, and the headless fallback fires automatically. No operator action is required — the selection is transparent.

This is the boundary that ADR-0050 enforced by choosing headless-always. ADR-0074 restores the MCP option WITHIN that boundary: interactive sessions where the operator has opted in.

### D5: Bootstrap-mode — headless path is grandfathered; forward binding only

All prior qa-tester invocations that ran under the headless-only driver (ADR-0050 D1) are grandfathered. This ADR binds forward from slice #975's merge. No retroactive re-run of prior features under the live path is required.

Runs dispatched after this merge will call `list_connected_browsers` at the start of the browser route. If the operator has not connected a browser, the result is empty, and the headless Playwright driver runs exactly as before.

### D6: Rule-#23 enforcement mechanism

Per [ADR-0056](0056-no-rule-without-a-check.md) D1, D1–D5 above are enforced by:

- **D1 (live-vs-headless selection):** `grep -E 'list_connected_browsers' .claude/agents/qa-tester.md >= 1` — enforced by CI CHECK 18 (AS-AUDIT) which verifies the qa-tester tool-boundary documentation.
- **D2 (GIF artifact + console):** `grep -E 'gif_creator|read_console_messages' .claude/agents/qa-tester.md >= 1` — same CI CHECK 18 gate.
- **D3 (tool-boundary update):** `grep -E 'list_connected_browsers|gif_creator|read_console_messages|ToolSearch' .claude/agents/qa-tester.md >= 1` — acceptance criterion for slice #975; verified by CI CHECK 18.
- **D4 (interactive-only):** documented as prose in qa-tester.md's live-browser branch; the `list_connected_browsers` empty-result → headless-fallback logic is the enforcement path; not separately metered.
- **D5 (bootstrap-mode):** per ADR-0004 D2 standard; no new mechanism needed.

## Propagation

Per ADR-0003 D8, the propagation obligation for this macro-ADR is fulfilled entirely within slice #975:

- **`.claude/agents/qa-tester.md`** — primary edit: toolset update (D3), live-browser branch in production-verify mode (D1/D2), propagation prose update (D4). The prior "headless Playwright is THE browser driver" characterization becomes "the **fallback** driver, used when no browser is connected". The front-matter `description:` is updated to reflect live-MCP-preferred-when-connected + headless-fallback.
- **`decisions/README.md`** — ADR-0074 index row added. ADR-0050 Status note updated to reflect D1 superseded by this ADR.

No other files require propagation in slice #975. Slices #976+ (per PRD #974) will handle verdict wiring (console-error count → non-PASS) and any additional documentation updates.

## Consequences

### Positive

- **Live browser proof is strictly richer.** A GIF of the real click-through (with click indicators + action labels) is more informative than a static headless screenshot. Operators can watch the feature behave.
- **Console errors in the live context.** Headless Playwright catches JS errors in the offscreen renderer; the live path checks the same console the user's browser exposes — closer to real user experience.
- **No regression in non-interactive runs.** The headless fallback is unchanged; all CI/cron/remote-agent runs continue to work exactly as before.
- **Parsimony honored.** No new critic, no new agent, no new skill. qa-tester remains a GENERATOR per ADR-0020 D9. The browser driver upgrade is a tool-boundary extension within an existing generator.

### Negative / Accepted

- **Interactive-only for the live path.** The GIF/console proof requires a connected browser; non-interactive runs see only the headless path. This is explicitly acceptable — the live path is opt-in, not mandatory.
- **GIF artifact path dependency.** The `gif_creator export` writes to the browser's download directory; qa-tester must reliably capture and emit this path. If the path is not capturable, the LIVE path degrades to PROVISIONAL (GIF unavailable).
- **More declared tools.** qa-tester's `tools:` frontmatter grows to include 8 Chrome MCP tools + ToolSearch. AS-AUDIT (CHECK 18) verifies the documentation contract is maintained.

### Neutral

- No new agent, no new critic, no new skill. Net new files: `decisions/0074-*.md` (this ADR).
- `decisions/README.md` gains an ADR-0074 row.
- ADR-0050's `decisions/README.md` status note is updated to reference D1 as superseded by ADR-0074.

## Alternatives considered

- **Alt-A (rejected): keep headless-always.** The headless driver (ADR-0050) continues to be the correct choice for non-interactive runs; it is preserved as the fallback. However, a connected browser is strictly superior for user-facing feature verification when available — rejecting the upgrade when the browser is present would sacrifice valuable proof quality for no benefit.

- **Alt-B (rejected): new separate gate step for live-browser QA.** This would add a distinct `/ship` step (e.g., step 7) that drives the live browser, keeping the headless gate at step 5/6 unchanged. PRD #974 §2 criterion 7 explicitly ruled this out: the live-vs-headless selection must be INTERNAL to the browser route so the orchestrator dispatch surface is unchanged. A new gate step would require touching `/build` and `/ship` — out of scope.

- **Alt-C (rejected): mandatory connected browser.** Making a connected browser a hard requirement (FAIL when absent) would break all CI/autonomous/mobile-remote runs. PRD #974 §3 explicitly lists this as a non-goal. The opt-in + fallback model is the correct choice.

## References

- PRD [#974](https://github.com/vojtech-stas/project-claude/issues/974) — parent PRD; slice [#975](https://github.com/vojtech-stas/project-claude/issues/975) (this ADR ships in slice 1 per ADR-0003 D8).
- Spike evidence (2026-06-18): `list_connected_browsers` returned non-empty in a dispatched subagent; `gif_creator` recorded a click-through and exported `qa-clickthrough-demo.gif`.
- [ADR-0050](0050-headless-playwright-browser-driver.md) — D1 superseded (driver choice); D2/D3/D4/D5 preserved.
- [ADR-0037](0037-production-verification-gate.md) — D2 extended (browser route now live-vs-headless internally); D3 preserved (orchestrator-enforced, qa-tester stays a generator).
- [ADR-0049](0049-claude-preview-browser-driver.md) — D3 (proof-posting by orchestrator) preserved; D4 fallback chain remains obsoleted per ADR-0050 D4.
- [ADR-0025](0025-qa-tester-ui-mode-playwright.md) — ui-mode foundation; D1/D3/D4/D5 preserved.
- [ADR-0004](0004-bypass-prevention.md) D1/D2 — bootstrap-mode policy; forward-binding discipline.
- [ADR-0046](0046-codebase-critic-and-parsimony-reframe.md) D1 — critic parsimony; no new critic, qa-tester stays a generator.
- [ADR-0056](0056-no-rule-without-a-check.md) D1 — rule-#23 enforcement; D6 above names the mechanisms.
- [ADR-0061](0061-rule-20-mechanization.md) D5 — ROOT-absolute artifact paths; GIF emitted to `qa-proof/<prd-num>/` or `.claude/logs/review-shots/`.
- [ADR-0003](0003-autonomous-pipeline-with-critics.md) D8 — macro-ADR convention (authored alongside PRD #974; ships in slice 1).
- `.claude/agents/qa-tester.md` — primary edit (toolset + live-browser branch in production-verify mode).
- `decisions/README.md` — ADR-0074 index row.
