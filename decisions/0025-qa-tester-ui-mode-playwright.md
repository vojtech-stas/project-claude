# ADR-0025: qa-tester subagent extension — Playwright MCP ui-mode for screenshot-judged acceptance testing

- **Status:** Accepted
- **Date:** 2026-05-24
- **Supersedes:** [ADR-0020](0020-qa-automation-writer-executor.md) D3 — narrowed: the qa-tester subagent's tool boundaries (originally `Read, Bash, Grep only` per ADR-0020 D3) gain `mcp__playwright__*` for the new ui-mode added by this ADR. ADR-0020 D3's sequential-walking + per-criterion-attribution contracts are PRESERVED unchanged (ui-mode aggregates per-step verdicts into per-criterion verdicts identically). ALL OTHER ADR-0020 decisions PRESERVED unchanged: D1 (writer/executor separation), D2 (LLM-extract at runtime from PRD §2), D4 (plan persisted as PRD comment), D5 (auto-close on all-PASS + all-judgment-ACCEPT), D6 (Tier 2 agentic semantic QA deferred), D7 (Tier 3 UI/browser QA deferred — ADR-0025 is the future-PRD that fulfills this deferral), D8 (bootstrap-mode), D9 (6-critic-cap honored + qa-tester is generator role), D10 (relationship to ADR-0003 D4 terminal human checkpoint).
- **Extends:** [ADR-0008](0008-workflow-autolog-bootstrap-and-naming.md) D3 (inline-firing `/promote-to-backlog` autopilot — qa-tester ui-mode invokes per JUDGMENT → captured-issue flow per D4 below); [ADR-0008](0008-workflow-autolog-bootstrap-and-naming.md) D7 (6-critic-cap meta-rule — honored per D6 below, no new critic added; qa-tester remains a generator per ADR-0020 D9); [ADR-0022](0022-docs-first-kb-pattern.md) D2 (source-tier hierarchy — D3 below justifies Tier-4 Playwright MCP per the explicit escape clause "selective; only when Tier 1-3 don't cover"); [ADR-0024](0024-root-cause-workflow-capture-discipline.md) D1 (CLAUDE.md cross-cutting rule #13 — JUDGMENT captures follow the 3-part root-cause shape per D4 below); [ADR-0004](0004-bypass-prevention.md) D2 (bootstrap-mode policy cited in D5 below).

## Context

The user articulated the missing capability (verbatim 2026-05-24): *"I want human out of the loop and if possible we need to test it out in some environment so that we are actually clicking through and printscreening imitating human test qa (when testing using tests in code don't reveal problems)."*

Current state per [ADR-0020](0020-qa-automation-writer-executor.md):
- `/qa-plan` (writer skill): LLM-extracts PRD §2 acceptance criteria into bash-check or JUDGMENT flag; persists plan as PRD comment; dispatches `qa-tester` executor; aggregates verdicts; auto-closes PRD on all-PASS + all-judgment-ACCEPT.
- `qa-tester` (executor subagent): runs bash checks per the structured plan; emits per-criterion PASS/FAIL/JUDGMENT/EXTRACT_FAILED verdict table + GENERATOR trailer per ADR-0005 D1c.

This pipeline correctly verifies **bash-checkable** acceptance criteria (file existence, grep counts, conv-commits format) but is structurally incapable of catching **visual / interaction defects** — broken layouts, missing CSS, JavaScript click handlers wired wrong without throwing, accessibility-tree breakage. Per the user's framing: *"tests in code don't reveal problems."*

The 2026-05-24 grill (Q1-Q8) locked the design:
- Q1 1B: scope = Web UI + CLI/TUI (CLI = bash-mode covers non-interactive)
- Q2 2C: browser driver = Playwright MCP (Tier-4 per ADR-0022 D2; justified per D3 below)
- Q3 3A: test plan source = LLM-extract from PRD §2 (mirrors ADR-0020 D2 writer pattern)
- Q4 4A: verification = LLM judges screenshots
- Q5 5B: JUDGMENT handling = PROVISIONAL_PASS + auto-capture per rule #13 captured-tier graveyard
- Q6 6C: replacement = auto-router in `/qa-plan` (deferred to PRD-Q2; this ADR's PRD ships the executor only)
- Q7 7B: subagent shape = extend existing qa-tester (single executor, dual-mode bash + ui)
- Q8 8A: dogfood = inline-generated static HTML to tmp dir (zero tracked file; user-stated "smart place to avoid bloat")

This ADR codifies the dual-mode contract, surgically supersedes ADR-0020 D3's tool-boundary clause (preserving D3's bash-mode + ALL OTHER ADR-0020 decisions unchanged per the documented partial-supersession pattern), and establishes the JUDGMENT-as-captured-tier convention. **This ADR does NOT modify `/qa-plan` skill** — that's PRD-Q2 (next PRD per Q7 decomposition).

## Decisions

### D1: qa-tester gains ui-mode alongside bash-mode (dual-mode contract)

The existing `qa-tester` subagent at `.claude/agents/qa-tester.md` is extended (not replaced) with a second execution mode `ui-mode`. The existing mode is now explicitly named `bash-mode` and PRESERVED unchanged per ADR-0020 D1-D10 contracts (modulo D3's tool-boundary clause narrowed per this ADR's Supersedes header above).

**Mode selection mechanism:** mode is determined by the caller (the writer skill `/qa-plan` via PRD-Q2's auto-router, or direct invocation via subagent prompt). For this ADR's PRD scope, ui-mode is invoked explicitly via subagent prompt arg pattern `qa-tester ui-mode <prd-num>`; PRD-Q2 will codify the auto-router classifier.

**ui-mode execution loop:**
1. Receive PRD-num + LLM-extracted click recipes from caller (recipes come from PRD §2 per Q3 3A; in this PRD's slice 1 the writer-side extraction isn't shipped yet, so ui-mode accepts recipes as a structured input the implementer can dogfood directly)
2. Run dogfood self-test FIRST per D5 below; ABORT if dogfood FAILs (signals Playwright wiring broken)
3. For each click recipe step: navigate/click/fill/screenshot via Playwright MCP
4. After each step: LLM judges screenshot vs expected outcome — emit PASS / PROVISIONAL_PASS / FAIL
5. PROVISIONAL_PASS triggers JUDGMENT capture per D4 below
6. Aggregate per-step verdicts into per-criterion verdict + standard GENERATOR trailer per ADR-0005 D1c (extend with `UI_PASS_COUNT`, `UI_PROVISIONAL_PASS_COUNT`, `UI_FAIL_COUNT`, `UI_CAPTURED_ISSUES` per-agent extensions)

**Tool boundaries:** bash-mode uses `Read, Bash, Grep` (ADR-0020 D3 unchanged). ui-mode uses `Read, Bash, Grep, mcp__playwright__*`. Single subagent file; mode-conditional tool usage.

### D2: Playwright MCP as browser driver (Q2 2C)

The browser-driving tool is `@playwright/mcp` (third-party, Tier-4 per ADR-0022 D2 hierarchy). Installed via `npx -y @playwright/mcp@latest` per Playwright MCP standard install. bootstrap.sh extended with idempotent install step per D7 below.

**Why Playwright vs Anthropic-first-party alternatives** (the grill explicitly weighed 2A Claude in Chrome, 2B Claude Preview, 2C Playwright, 2D both):
- **Claude in Chrome (Tier-1, Anthropic-recommended per docs.claude.com/en/best-practices)** requires the Chrome browser extension installed on every developer/CI machine running qa-tester. Consumer projects forking this template would need to install the extension per-machine — unacceptable friction.
- **Claude Preview (Tier-1, sandboxed)** is headless-friendly but less-documented for QA-shape use cases; not endorsed by Anthropic's best-practices doc for this specific scenario.
- **Playwright MCP (Tier-4)** is the industry-standard browser-automation library; multi-browser (Chromium/Firefox/WebKit); CI-friendly headless by default; well-documented test patterns; no extension install dependency.

This is an explicit invocation of ADR-0022 D2's escape clause: *"Tier-4 community content — selective; only when Tier 1-3 don't cover."* Tier-1 Claude in Chrome doesn't cover the no-extension consumer-machine constraint; Tier-4 Playwright does.

### D3: LLM-judges screenshots (Q4 4A)

Per click recipe step, qa-tester ui-mode emits one of:
- **PASS** — LLM-judge confident screenshot matches expected outcome from PRD §2 acceptance criterion
- **PROVISIONAL_PASS** — LLM-judge uncertain; proceeds to D4 capture flow
- **FAIL** — LLM-judge confident screenshot does NOT match (or click step itself errored: navigation failed, element not found, JS exception)

The LLM-judgment prompt is part of qa-tester's prompt body. PRDs whose §2 acceptance criteria mention visual outcomes (text "Login" visible, button "Submit" clickable, form fields aligned) produce useful LLM-judgments; PRDs whose §2 has only file-system / grep checks won't trigger ui-mode at all (auto-router in PRD-Q2 handles classification).

**Pixel-diff or reference-image verification explicitly rejected** at grill Q4 (option 4D); LLM-judge sufficient for v1. Reference-image verification may be added in a future PRD if LLM-judgment false-FAIL/false-PASS rate becomes problematic.

### D4: JUDGMENT (PROVISIONAL_PASS) auto-captures + invokes /promote-to-backlog inline

When LLM-judge emits PROVISIONAL_PASS:
1. qa-tester writes a `captured`-labeled GitHub issue with body following rule #13 (per ADR-0024 D3) 3-part shape:
   - **Symptom:** screenshot embedded (or path referenced) + the click recipe step + the expected outcome from PRD §2
   - **Root cause:** "LLM-judge uncertain whether screenshot matches expected outcome" + LLM's verbatim uncertainty reason
   - **Proposed workflow change:** "User reviews when convenient; if FAIL, reopen PRD + add reference-image to PRD §2 to convert future runs from LLM-judge to mechanical match"
2. qa-tester invokes `/promote-to-backlog` inline per ADR-0008 D3 (autopilot fires once per item; APPROVE swaps to backlog, BLOCK leaves in captured-tier graveyard per ADR-0008 D2)
3. qa-tester treats PROVISIONAL_PASS as PASS for purposes of the writer skill's aggregation — PRD does NOT block on PROVISIONAL_PASS

**Why PROVISIONAL_PASS not FAIL** (Q5 grill explicitly weighed 5A FAIL-conservative): the user's "human out of loop" goal incompatible with high false-FAIL rate that would force manual review of every JUDGMENT — defeating autonomy. PROVISIONAL_PASS + lazy review preserves the autonomy loop while surfacing ambiguity for human cadence.

### D5: Dogfood self-test on every ui-mode invocation (inline-generated tmp HTML; zero tracked file)

Before processing PRD click recipes, qa-tester ui-mode runs a dogfood self-test:
1. Writes `/tmp/qa-dogfood-${CLAUDE_SESSION_ID}.html` containing 3 elements: a button with `id="dogfood-btn"`, a hidden `<div id="dogfood-result">PASS</div>`, and inline JS that shows the div on button click
2. Opens via `file://` URL through Playwright MCP
3. Clicks button, screenshots
4. LLM-judges screenshot contains text "PASS"
5. If dogfood PASSes → proceed to PRD recipes
6. If dogfood FAILs → ABORT with diagnostic message (Playwright wiring broken; do NOT proceed to PRD)
7. Cleans up tmp file on exit

**Why inline-generated not tracked file** (Q8 explicit user instruction "smart place so we don't bloat the codebase"): zero new tracked artifact; subagent self-contains its self-test fixture; HTML regenerates each invocation so cannot rot.

### D6: 6-critic-cap honored (no new critic; qa-tester remains a generator)

Per ADR-0008 D7, the project currently runs 6 critics (reviewer, prd-critic, adr-critic, slicer-critic, glossary-critic, backlog-critic). This ADR adds NO new critic. qa-tester remains a generator per ADR-0020 D9 (emits structured PASS/FAIL output the writer consumes; no second-opinion review).

Q5 grill explicitly weighed option 5D (qa-judge-critic second-opinion subagent) and rejected as 6-critic-cap violation requiring a new ADR to override. The chosen PROVISIONAL_PASS + captured pattern (D4) achieves the second-opinion safety via the captured-tier autopilot's existing backlog-critic gate — no new critic needed.

### D7: bootstrap.sh adds Playwright MCP install step (idempotent)

`bootstrap.sh` (per ADR-0008 D6 fresh-clone project setup) gains an idempotent Playwright MCP install step. Detection: `command -v npx && npx -y @playwright/mcp@latest --version`. If not installed, run `npx -y @playwright/mcp@latest install` (or equivalent per Playwright MCP docs at time of implementation).

Implementer responsibilities (per OQ-1, OQ-4 in parent PRD): verify whether per-project MCP config (`.mcp.json` or `.claude/settings.json` `mcpServers` entry) is needed in addition to install; verify cross-platform install on Windows Git Bash (project's primary dev environment); document any platform-specific quirks in bootstrap.sh comments.

### D8: Bootstrap-mode acknowledgment (per ADR-0004 D2)

ui-mode binds **forward from the slice that ships it** (parent PRD slice 1 merge). No retroactive sweep:
- Past PRDs (#3 through #210) ran without ui-mode; their `/qa-plan` invocations continue using bash-mode unchanged
- Existing skill/subagent/ADR surface UNCHANGED modulo this ADR's documented edits (qa-tester ui-mode extension + decisions/README ADR-0020 row Status amendment + ADR-0025 index row) — phrasing matches ADR-0008 D8 documented drift-proof pattern
- Future PRDs whose §2 acceptance criteria are UI-shaped will trigger ui-mode via PRD-Q2's auto-router (when PRD-Q2 ships)

The 6-critic-cap meta-rule (ADR-0008 D7) is unaffected per D6 above. Per-PRD opt-in via the auto-router classifier (PRD-Q2 scope); no PRD is force-routed to ui-mode against its §2 shape.

### D9: Cascade-doc updates

- `.claude/agents/qa-tester.md` — the primary edit; gains dual-mode contract + ui-mode contract + Tool boundaries extension + dogfood section + References update
- `decisions/0025-qa-tester-ui-mode-playwright.md` — this ADR file (new)
- `decisions/README.md` — ADR-0025 index row appended in numerical order
- `decisions/README.md` — ADR-0020 row Status amended to note D3 tool-boundary partial supersession per ADR-0025 D1 (mirrors documented pattern of ADR-0013 D5 updating ADR-0003 row + ADR-0012 updating ADR-0007 row + ADR-0024 amending ADR-0009 row)
- `bootstrap.sh` — Playwright MCP install step per D7
- `CLAUDE.md` Map row for qa-tester subagent — verify whether existing Map row mentions bash-mode-only; if so, update to note ui-mode addition (slicer/implementer judgment per cascade-doc check)
- `README.md` — NOT updated. ui-mode is an executor-internal extension; README's workflow narrative doesn't enumerate subagent modes
- `.claude/skills/qa-plan/SKILL.md` — NOT updated. The auto-router edit is PRD-Q2 scope; this PRD's qa-tester edit is the executor only

## Consequences

### Positive

- **Visual / interaction defect coverage** that code-tests can't catch — directly addresses user's 2026-05-24 motivation
- **Zero human-in-loop** for the autonomous QA path — PROVISIONAL_PASS + captured replaces the existing /qa-plan AskUserQuestion JUDGMENT flow
- **Backward-compat preserved** — bash-mode unchanged; existing /qa-plan calling pattern unchanged; ADR-0020 D1-D10 PRESERVED (modulo D3 tool-boundary clause narrowed per this ADR's D1); no in-flight PRDs affected by this ADR
- **Surgical supersession** — only ADR-0020 D3's tool-boundary clause narrowed; mirrors the ADR-0012 D1 + ADR-0013 D1 + ADR-0024 D2 documented partial-supersession discipline (each amends a single named D-ID rather than blanket-replacing the whole prior ADR)
- **Honors existing conventions** — uses `captured` label, `/promote-to-backlog` autopilot, rule #13 3-part body shape, ADR-0005 D1c GENERATOR trailer
- **Compounding with rule #13** — JUDGMENT captures use root-cause-shape body per ADR-0024; the discipline rule #13 mandated is mechanically applied by qa-tester ui-mode's PROVISIONAL_PASS flow
- **Future-proof for consumer projects** — template ships ready-to-use UI QA infrastructure; consumer projects activate by writing UI-shape §2 ACs

### Negative / Accepted

- **External dependency on Playwright MCP** — first non-Tier-1 dependency in this template. Justified per D2 escape clause; documented per ADR-0022 D2 hierarchy.
- **LLM-judgment non-determinism** — same screenshot may judge differently across runs; mitigated by PROVISIONAL_PASS + captured pattern surfacing for human review rather than hard-blocking on inconsistency
- **PROVISIONAL_PASS false-PASS risk** — LLM wrongly confident-PASS on a broken UI would slip through; mitigated by D5 dogfood self-test catching obvious wiring breaks before per-step judging, and by D4 captured-tier review surfacing patterns over time
- **bootstrap.sh complexity grows** — Playwright install adds ~30 LoC + platform-specific concerns (Windows Git Bash verified during implementation per OQ-4)
- **Dogfood self-test runs every ui-mode invocation** — small wall-clock cost (~5s per qa-tester run); accepted as the price of trust-but-verify wiring
- **PRD-Q2 dependency** — full value of this PRD requires PRD-Q2 (auto-router) to ship; this PRD alone provides the executor but the user-facing /qa-plan still routes to bash-mode only until Q2 lands

## Alternatives considered

- **Alt-A: Hard replace ADR-0020 entirely** with a new qa-tester from scratch. Rejected — ADR-0020 D1-D10 contracts work for bash-mode PRDs which dominate this template's current PRD shape; surgical supersession of D3 only is the right precision per the ADR-0012 D1 + ADR-0013 D1 documented partial-supersession pattern (each amends a single named D-ID via README index-row Status rather than blanket-replacing the whole prior ADR).
- **Alt-B: New `qa-ui-tester` sibling subagent** alongside existing `qa-tester`. Rejected per Q7 7B grill — single executor with dual mode honors `/best-practice-subagents` Rule 1 ("each subagent excels at one specific task") via the unifying task framing "execute QA verification against PRD §2 ACs"; two subagents would duplicate plumbing without coverage gain.
- **Alt-C: Claude in Chrome (Tier-1)** as browser driver instead of Playwright. Rejected per D2 — extension install dependency unacceptable for consumer template forks.
- **Alt-D: Claude Preview (Tier-1) sandboxed driver** instead of Playwright. Rejected per D2 — less-documented for QA-shape use cases; Anthropic best-practices doc doesn't endorse for this scenario.
- **Alt-E: Both Claude in Chrome + Claude Preview with caller-selected driver flag**. Rejected — doubles infrastructure surface; YAGNI for v1.
- **Alt-F: JUDGMENT → AskUserQuestion human gate** (matches existing /qa-plan pattern). Rejected per Q5 5A vs 5B — user explicit "human out of loop" goal; PROVISIONAL_PASS + captured (5B) preserves autonomy.
- **Alt-G: JUDGMENT → retry with stronger LLM prompt before deciding** (Q5 5C). Rejected as YAGNI — adds LLM call cost without resolving fundamental ambiguity; captured pattern handles edge cases via lazy review.
- **Alt-H: JUDGMENT → second-opinion qa-judge-critic subagent** (Q5 5D). Rejected per D6 — would violate ADR-0008 D7 6-critic-cap; captured-tier autopilot's backlog-critic already provides second opinion.
- **Alt-I: Implementer paste-in click recipes in PR body** (Q3 3B). Rejected — adds new author burden; LLM-extract from PRD §2 (ADR-0020 D2 pattern) preserves zero-burden default.
- **Alt-J: Separate `.qa-tests/` test-file directory** (Q3 3C). Rejected — over-engineering for project's PRD cadence; would introduce new file format + versioning concerns.
- **Alt-K: Pixel-diff or reference-image verification** (Q4 4D). Rejected for v1 — LLM-judge sufficient; reference-image deferred to future PRD if LLM-judgment proves unreliable.
- **Alt-L: Tracked dogfood HTML file in `demo-ui/` or similar** (Q8 8B/8C). Rejected per user's explicit "smart place to avoid bloat" instruction — inline-generated tmp file (8A + reasonable-call placement) is the zero-bloat choice.
- **Alt-M: Defer dogfood entirely to consumer-project first use** (Q8 8D). Rejected — would ship untested browser-driving infrastructure; violates walking-skeleton discipline rule #2.
- **Alt-N: One mega-PRD covering qa-tester + /qa-plan router + capture autopilot** (Q7 7C). Rejected — walking-skeleton + smaller blast radius preferred; 2-PRD split (this + PRD-Q2) per Q7 7B is the right granularity.

## Open questions deferred

- **OQ-1: Per-project vs user-level MCP config for Playwright.** Implementer verifies during slice 1 (parent PRD §6).
- **OQ-2: Dogfood HTML collision handling.** Default = overwrite; UUID suffix if collision risk surfaces (parent PRD §6).
- **OQ-3: PROVISIONAL_PASS aggregation semantics.** PRD-Q2 codifies; this PRD just emits per-step verdict.
- **OQ-4: Cross-platform Playwright install (Windows Git Bash).** Implementer verifies during slice 1.
- **OQ-5: Headed mode for local debugging.** Future PRD if needed.
- **OQ-6: Multi-browser (Firefox + Safari) support.** Future PRD if consumer needs.
- **OQ-7: Reference-image pixel-diff fallback** for cases where LLM-judge proves unreliable. Future PRD if needed.

## Future direction

- **PRD-Q2** (next PRD per Q7 7B decomposition) — extend `/qa-plan` skill with LLM-classifier auto-router (UI vs mechanical vs both) + JUDGMENT → `/promote-to-backlog` inline-firing wiring
- **PRD-Q3 (hypothetical)** — if interactive TUI testing becomes needed for consumer projects, add `expect`/`pexpect` driver as a third execution mode per Q1 grill (currently deferred per PRD §3)
- **Future PRD** — multi-browser support if consumer needs (OQ-6)
- **Future PRD** — reference-image pixel-diff verification mode if LLM-judgment false-rate problematic (OQ-7)
- **Future PRD** — `qa-tester-fixtures/` colocation if dogfood HTML grows beyond inline-generation reasonable scope

## References

- docs.claude.com/en/best-practices — "UI changes can be verified using the Claude in Chrome extension" (related framing; this ADR's D2 explicitly weighs and rejects Claude in Chrome for consumer-template constraint)
- docs.claude.com/en/mcp — MCP server configuration (OQ-1 reference)
- Playwright MCP — `@playwright/mcp` (the Tier-4 dependency this ADR adopts)
- [ADR-0001](0001-foundational-design.md) D6 — subagent definition + tool boundaries pattern (qa-tester ui-mode honors)
- [ADR-0003](0003-autonomous-pipeline-with-critics.md) D8 — macro-ADR placement (this ADR drafted alongside parent PRD per the pattern)
- [ADR-0004](0004-bypass-prevention.md) D2 — bootstrap-mode policy cited by D8
- [ADR-0005](0005-output-shape-and-slicing-methodology.md) D1c — GENERATOR trailer schema (qa-tester ui-mode extends with UI_* extensions)
- [ADR-0008](0008-workflow-autolog-bootstrap-and-naming.md) D3 — inline-firing `/promote-to-backlog` autopilot (D4 above invokes)
- [ADR-0008](0008-workflow-autolog-bootstrap-and-naming.md) D7 — 6-critic-cap meta-rule (D6 honors)
- [ADR-0020](0020-qa-automation-writer-executor.md) D1-D10 — writer/executor split (ADR-0025 D1 surgically supersedes only ADR-0020 D3's tool-boundary clause; D1 D2 D4 D5 D6 D7 D8 D9 D10 PRESERVED)
- [ADR-0012](0012-glossary-consolidation-single-tier.md) D1 — surgical-supersession precedent (single-D-ID amendment via README index row Status)
- [ADR-0013](0013-slicer-n3-contract-refined.md) D1 + D5 — surgical-supersession precedent (single-D-ID amendment + README index-row Status update pattern)
- [ADR-0022](0022-docs-first-kb-pattern.md) D2 — source-tier hierarchy + escape clause (D2 cites for Playwright Tier-4 justification)
- [ADR-0024](0024-root-cause-workflow-capture-discipline.md) D1 + D3 — CLAUDE.md rule #13 + 3-part body shape (D4 follows)
- `.claude/agents/qa-tester.md` — file edited by parent PRD slice 1
- `bootstrap.sh` — file edited by parent PRD slice 1 per D7
- `decisions/README.md` — file edited by parent PRD slice 1 per D9
- 2026-05-24 grill Q1-Q8 — the decision provenance (Q-by-Q decisions locked verbatim with user)
