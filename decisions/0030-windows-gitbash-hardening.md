# ADR-0030: Cross-platform Windows Git Bash hardening — jq + Playwright install + hook allowlist fix + SessionStart warning

- **Status:** Accepted
- **Date:** 2026-05-26
- **Supersedes:** none
- **Extends:** [ADR-0008](0008-workflow-autolog-bootstrap-and-naming.md) D6 (bootstrap.sh — extended with jq + Playwright install steps); [ADR-0015](0015-claude-code-hooks-adoption.md) D2 (hook scope policy — D2/D3 below honor logging/validation/notification); [ADR-0023](0023-validation-and-notification-hooks-extension.md) D2 (SessionStart hook — extended with jq-missing warning); [ADR-0023](0023-validation-and-notification-hooks-extension.md) D3 (PreToolUse Edit|Write hook — restructured to run allowlist BEFORE jq-fallback while preserving spec-gate per D3 below); [ADR-0023](0023-validation-and-notification-hooks-extension.md) D7 (hook scripts under `.claude/hooks/` — same placement); [ADR-0025](0025-qa-tester-ui-mode-playwright.md) D7 (Playwright MCP install — COMPLETES the deferred-to-implementer OQ-4 by codifying bootstrap.sh as the install location); [ADR-0026](0026-knowledge-architecture-truth-docs.md) D2+D5+D7 (R-TRUTH-DOC — this PR amends hooks.md AND creates bootstrap.md (4th topic backfill)); [ADR-0028](0028-pretooluse-spec-gate.md) D1+D2 (spec-gate layering — re-ordered relative to jq-fallback per D3 below; spec-gate behavior PRESERVED unchanged); [ADR-0028](0028-pretooluse-spec-gate.md) D5 (hooks truth-doc — being amended); [ADR-0004](0004-bypass-prevention.md) D2 (bootstrap-mode policy cited by D8); [ADR-0008](0008-workflow-autolog-bootstrap-and-naming.md) D7 (6-critic-cap meta-rule — preserved per D9); [decisions/README.md](README.md) *"What an ADR is"* (ADR immutability — this ADR doesn't edit prior ADRs).

## Context

Captured backlog [#222](https://github.com/vojtech-stas/project-claude/issues/222) (2026-05-26) documents the THIRD instance this autonomous run of cross-platform Windows Git Bash brittleness causing real user-impact:

**Root cause #1 (immediate user-impact):** `jq` is not installed on Windows Git Bash by default. The PreToolUse Edit/Write hook (pre-tool-edit.sh, ADR-0023 D3) defensively escalates via `emit_ask()` when `jq` is missing (the `command -v jq` guard fires BEFORE the gitignored-path allowlist and the tracked-file check). Result: every Edit/Write call prompts user, even gitignored scratch files. User-encountered today; manual workaround: `winget install jqlang.jq` + symlink to user-PATH dir.

**Root cause #2 (deferred-debt):** ADR-0025 D7 (PRD-Q1 ship) specified Playwright MCP install for bootstrap.sh but deferred the actual implementation to "implementer judgment" per OQ-4. The implementer never added it. Consumer-fork brittleness.

**Root cause #3 (latent):** The allowlist case-patterns in pre-tool-edit.sh use POSIX `/` (`*/tool-results/*`). Windows paths often have `\`. Case-pattern matching FAILS silently on Windows. Only safe today because jq-fallback escalates anyway. If we fix #1, we expose this latent bug.

Three pains converge → 3-layer defense per #222 proposal. This ADR codifies all three.

## Decisions

### D1: bootstrap.sh adds idempotent jq install (Windows winget / macOS brew / Linux apt)

`bootstrap.sh` (ADR-0008 D6) gains a step: detect `command -v jq`; if missing, OS-specific install:
- Windows: `winget install --id jqlang.jq --silent --accept-source-agreements --accept-package-agreements`
- macOS: `brew install jq`
- Linux: `apt-get install -y jq` (with sudo if available)

Warn-and-continue per existing bootstrap.sh best-effort policy. Idempotent (skip if installed).

### D2: bootstrap.sh adds idempotent Playwright MCP install

`bootstrap.sh` gains a step (completes ADR-0025 D7 OQ-4 deferral): detect `npx -y @playwright/mcp@latest --version`; if missing, `npx -y @playwright/mcp@latest install`. Requires Node.js + npm (assumed present per existing bootstrap.sh assumptions).

Warn-and-continue. Idempotent.

### D3: pre-tool-edit.sh restructures allowlist to run BEFORE jq-fallback (spec-gate per ADR-0028 D1+D2 PRESERVED unchanged)

Current chain on main (post-ADR-0028 merge): subagent skip → jq-fallback → file-path extract → allowlist (case-pattern, /-only) → tracked-check → spec-gate (ADR-0028 D1+D2) → rule-#10 ask. PROBLEM: when jq missing, fallback fires before allowlist, denying gitignored edits.

NEW chain: subagent skip → allowlist (path-substring check; POSIX-portable, handles `/` and `\`) → jq-fallback → file-path extract → tracked-check → spec-gate (ADR-0028 D1+D2, PRESERVED unchanged) → rule-#10 ask.

The ONLY change is moving the allowlist to run BEFORE the jq-fallback + fixing its path-separator handling. The spec-gate (ADR-0028 D1+D2) layering is PRESERVED unchanged — it still fires between tracked-check and rule-#10 ask per ADR-0028's canonical chain. The allowlist's purpose is unchanged (exit silently on gitignored scratch directories); its position is moved to make it robust when jq is missing.

Allowlist pseudo-code (runs BEFORE jq-fallback):
```bash
# Pre-jq allowlist: read raw stdin without jq, substring-match
# Handles both / and \ separators (Windows Git Bash)
FP_RAW=$(cat /dev/stdin | head -c 4096)
case "$FP_RAW" in
  *tool-results*|*.claude/projects*|*.claude/logs*|*.claude\\projects*|*.claude\\logs*) exit 0 ;;
esac
# Then existing jq check + fallback + tracked-check + ADR-0028 spec-gate + rule-#10 ask
```

This is the THIRD layer of defense: even if jq missing, the allowlist exits silently on gitignored scratch directories before any other check fires. ADR-0028 spec-gate behavior is fully preserved (downstream of the allowlist + tracked-check; allowlist exits early so spec-gate never fires for scratch dirs, which matches expected behavior — scratch dirs don't need spec-gate enforcement).

### D4: session-start.sh emits jq-missing warning in additionalContext

`session-start.sh` (ADR-0023 D2) gains a check at start: if `! command -v jq`, append to the additionalContext output: *"WARNING: jq is missing on this system. PreToolUse Edit/Write hook may prompt on every edit (rule #10 ask fallback). Install via `bootstrap.sh` or `winget install jqlang.jq` (Windows) / `brew install jq` (macOS) / `apt-get install jq` (Linux)."*

User sees the warning at session start instead of discovering it after 30 permission prompts.

### D5: NEW `docs/current/bootstrap.md` truth-doc (4th topic backfill)

Per ADR-0026 D1 format. Lists bootstrap.sh steps + dependencies (jq, Playwright MCP, Node.js, gh CLI, git). H1 / Status / Date / Active synthesis (table of steps) / Sources.

Per ADR-0026 D7 bootstrap-mode forward: this is the FOURTH topic backfill after qa-automation.md (PRD-K, inaugural), subagents.md (PRD-LM), hooks.md (PRD-O). The `bootstrap` topic is now queryable via the topic-nudge hook.

### D6: `docs/current/hooks.md` AMENDMENT

Per ADR-0026 D2 + D5 R-TRUTH-DOC: PR touching `decisions/0030-*.md` must touch corresponding `docs/current/<topic>.md`. This ADR affects TWO topics: bootstrap (new truth-doc per D5) AND hooks (pre-tool-edit + session-start changes). hooks.md is AMENDED:
- pre-tool-edit row updated: "what it does" includes "allowlist runs before jq-fallback for Windows Git Bash robustness"
- session-start row updated: "what it does" includes "warns if jq missing per ADR-0030 D4"

SECOND truth-doc AMENDMENT exercise of R-TRUTH-DOC (after PRD-P's Stop hook addition).

### D7: `.claude/topics.json` gains `bootstrap` entry

Per ADR-0026 D4 topic-nudge hook wiring. Keywords: `["bootstrap", "bootstrap.sh", "install", "jq", "playwright", "windows git bash", "fresh clone"]`. Implementer adjusts per OQ judgment.

### D8: Bootstrap-mode acknowledgment (per ADR-0004 D2)

Cross-platform hardening binds FORWARD from slice 1 merge:
- Existing developer machines get jq + Playwright on next `bootstrap.sh` run (idempotent — safe re-run)
- Pre-tool-edit allowlist + session-start warning live immediately after merge
- No retroactive sweep of historical sessions
- Dogfood on slice 1's own PR (Windows Git Bash where today's user pain originated)

### D9: 6-critic-cap honored per ADR-0008 D7

ADR-0030 adds NO critic. Hook/bootstrap script changes only. Critic count remains 6.

### D10: R-TRUTH-DOC self-satisfaction

PR touches `decisions/0030-windows-gitbash-hardening.md` (NEW) AND `docs/current/hooks.md` (AMENDED) AND `docs/current/bootstrap.md` (NEW) → R-TRUTH-DOC SATISFIED per ADR-0026 D5. First multi-topic exercise of the rule (ADR affecting 2 topics).

### D11: Cascade-doc updates

- `bootstrap.sh` — jq install per D1, Playwright install per D2
- `.claude/hooks/pre-tool-edit.sh` — restructured per D3
- `.claude/hooks/session-start.sh` — jq warning per D4
- `decisions/0030-windows-gitbash-hardening.md` — this ADR (NEW)
- `decisions/README.md` — ADR-0030 index row
- `docs/current/bootstrap.md` — NEW per D5
- `docs/current/hooks.md` — AMENDED per D6
- `.claude/topics.json` — `bootstrap` entry per D7
- `CLAUDE.md` — NO update
- `README.md` — NO update

## Consequences

### Positive

- **User-pain fixed mechanically** — jq install via bootstrap.sh means future devs don't hit the "every edit prompts" wall.
- **Allowlist-before-jq-fallback** means even if jq install fails or is later removed, gitignored edits still pass silently.
- **POSIX-portable path matching** fixes the latent Windows backslash bug.
- **session-start warning** surfaces the issue immediately if jq install missed.
- **Playwright install completion** addresses long-standing ADR-0025 D7 OQ-4 deferral.
- **First multi-topic R-TRUTH-DOC exercise** — proves rule scales when ADR affects ≥2 topics.
- **4th topic backfill** (bootstrap.md) extends the truth-doc surface.
- **6-critic-cap preserved.**

### Negative / Accepted

- **bootstrap.sh complexity grows** — ~40 LoC additions. Acceptable; bootstrap.sh is the documented place for setup steps per ADR-0008 D6.
- **Install dependencies on package managers** (winget/brew/apt) — accepted per platform conventions.
- **Multi-topic R-TRUTH-DOC compliance burden** — implementer must update 2 truth-docs in same PR. Acceptable for cross-cutting ADRs.
- **No WSL2 fallback** — out per §3; if Git Bash incompat surfaces, future PRD adds WSL2 path.
- **jq install requires network access** — accepted; bootstrap.sh assumes network for `gh`, etc.

## Alternatives considered

- **Alt-A: Just install jq; don't restructure hook.** Rejected — leaves latent allowlist-after-fallback bug.
- **Alt-B: Just restructure hook; don't install jq.** Rejected — user still hits "no jq" warning every session.
- **Alt-C: Rewrite pre-tool-edit.sh in Python or Go.** Rejected — language jump for one script; bash + small fixes suffice.
- **Alt-D: Pre-commit git hook installs jq.** Rejected — too late; jq needed at session-start time.
- **Alt-E: Detect Windows via uname and use Windows-specific logic only.** Rejected — POSIX-portable allowlist handles both Windows + Unix gracefully.
- **Alt-F: Skip Playwright install completion (defer further).** Rejected — ADR-0025 D7 OQ-4 deferred long enough; completing now is right.
- **Alt-G: Make bootstrap.sh fail-hard if jq install fails.** Rejected — best-effort policy per existing bootstrap.sh discipline.
- **Alt-H: Single truth-doc covering all infrastructure (bootstrap + hooks + topics).** Rejected — topic-per-truth-doc per ADR-0026 D1 cleaner; multi-topic ADRs amend multiple truth-docs.

## Open questions deferred

- OQ-1: jq install on Windows (winget chosen; scoop/choco alternatives noted)
- OQ-2: Playwright verification command precision
- OQ-3: POSIX-portable allowlist exact mechanism
- OQ-4: session-start warning wording
- OQ-5: bootstrap.md scope (slice 1 = bootstrap.sh steps only; CI for future)

## Future direction

- WSL2 fallback if Git Bash compat issues recur
- `/audit-meta` rule for bootstrap-drift
- Combine ADR-0028 + ADR-0029 + ADR-0030 into "Workflow enforcement hooks cluster" meta-ADR if pattern grows
- Pre-commit hook for "did bootstrap.sh run?" (idempotency check)

## References

- 2026-05-26 incident — manual jq install + symlink workaround
- captured #222 — origin (3-layer defense proposal)
- [ADR-0008](0008-workflow-autolog-bootstrap-and-naming.md) D6 — bootstrap.sh
- [ADR-0015](0015-claude-code-hooks-adoption.md) D2 — hook scope
- [ADR-0023](0023-validation-and-notification-hooks-extension.md) D2+D3+D7 — extended hooks
- [ADR-0025](0025-qa-tester-ui-mode-playwright.md) D7 — Playwright install (completed)
- [ADR-0026](0026-knowledge-architecture-truth-docs.md) D2+D5+D7 — R-TRUTH-DOC + bootstrap-mode
- [ADR-0028](0028-pretooluse-spec-gate.md) D5 — hooks truth-doc (being amended)
- captured #173, #195, #213, #218 — sibling cross-platform defects
- `bootstrap.sh` — file extended per D1+D2
- `.claude/hooks/pre-tool-edit.sh` — file restructured per D3
- `.claude/hooks/session-start.sh` — file extended per D4
- `docs/current/bootstrap.md` — NEW per D5
- `docs/current/hooks.md` — AMENDED per D6
