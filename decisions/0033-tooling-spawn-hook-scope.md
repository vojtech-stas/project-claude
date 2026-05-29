# ADR-0033: Tooling-spawn carveout for hook scripts — authorize observation-only process spawning

- **Status:** Accepted
- **Date:** 2026-05-29
- **Supersedes:** none
- **Extends:** [ADR-0015](0015-claude-code-hooks-adoption.md) D2 (hook scope policy — adds 4th category "tooling-spawn" per D1 below; core intent of D2 preserved per D2 here); [ADR-0023](0023-validation-and-notification-hooks-extension.md) D2 (SessionStart hook — additive extension authorized; dashboard-autostart.sh joins existing session-start.sh in the SessionStart array); [ADR-0030](0030-windows-gitbash-hardening.md) D1 (cross-platform Windows Git Bash hardening — tooling-spawn pattern honors per D3 below); [ADR-0008](0008-workflow-autolog-bootstrap-and-naming.md) D7 (6-critic-cap — preserved per D5; dashboard is observation tool, not critic); [ADR-0004](0004-bypass-prevention.md) D2 (bootstrap-mode policy — cited by D6); [decisions/README.md](README.md) "What an ADR is" (ADR immutability — preserved; this ADR extends ADR-0015 D2 via standard supersession mechanism rather than editing)

## Context

[ADR-0015](0015-claude-code-hooks-adoption.md) D2 established the hook scope policy: hooks may "log to local files, validate by exit code, or notify via stderr" — three permitted categories. D2 explicitly excluded hook invocation of skills/subagents to prevent the failure mode where a hook auto-bills the user via LLM API calls without their knowledge.

PRD-DSH (project workflow dashboard, posted alongside this ADR per [ADR-0003](0003-autonomous-pipeline-with-critics.md) D8) requires the SessionStart hook to spawn a dashboard server process (Python HTTP server on `localhost:8765`) if not already running. The user explicitly chose "auto-start via SessionStart hook" (grill Q3 = 3B, 2026-05-29) as the zero-friction lifecycle for the dashboard. Manual start (Q3 A) and bootstrap.sh daemon (Q3 C) were rejected.

The spawned dashboard server is NOT a skill or subagent invocation. It is a standalone Python script under `dashboard/` that:
- Reads local files (`.claude/agents/`, `.claude/skills/`, `.claude/hooks/`, `.claude/settings.json`, `.claude/logs/workflow-events.jsonl`, `decisions/`)
- Serves an HTML+JS interface on `localhost:8765`
- Makes no LLM API calls
- Has no network exit beyond localhost

Strictly read, ADR-0015 D2's three-category list does not authorize this. The dashboard server is not "logging to local files" (it's reading them); it's not "validating by exit code" (it's a long-running process); it's not "notifying via stderr" (it serves HTTP). A new category is needed.

This ADR adds that fourth category — "tooling-spawn" — under tightly bounded criteria that preserve ADR-0015 D2's core safety intent.

## Decisions

### D1: Add fourth category to hook scope policy — "tooling-spawn"

[ADR-0015](0015-claude-code-hooks-adoption.md) D2 listed three permitted categories. This ADR adds a fourth: **tooling-spawn**. Hooks may spawn project-local tooling processes that meet ALL FOUR of the following criteria:

1. **No LLM API calls.** The spawned process must NOT invoke any LLM API (no `anthropic` SDK use, no `openai` SDK use, no `claude` CLI, no `gh copilot`, no remote model endpoints). Verified by reading the spawned script's source.

2. **Localhost-only binding.** If the spawned process exposes a network interface, it MUST bind only to `localhost` / `127.0.0.1` / `::1`. No `0.0.0.0` binding. No external port exposure. Verified by reading the spawned script's source for `bind()` / `listen()` arguments.

3. **Project-scoped.** The spawned script MUST live inside the project repo (e.g., `dashboard/`, `tools/`). System binaries, user-global scripts, or third-party tools outside the repo do NOT qualify. Verified by the hook script's invocation path containing `$CLAUDE_PROJECT_DIR`.

4. **Idempotent spawn.** The hook MUST check whether the target process is already running before spawning. Duplicate spawns are forbidden. Verified by the hook script containing a `curl` (or equivalent) check against the expected listening port BEFORE the spawn command.

All four criteria are AND-conditions. Failing any one disqualifies a tooling-spawn instance.

**Canonical example (the only currently authorized tooling-spawn instance):** `dashboard/server.py` spawned by `.claude/hooks/dashboard-autostart.sh` per PRD-DSH slice 2.

Future tooling-spawn additions require an explicit ADR amendment to D1's "References" section below.

### D2: ADR-0015 D2's core intent preserved — hooks STILL forbidden from skill/subagent invocation

The "tooling-spawn" carveout (D1) does NOT authorize hook scripts to invoke `.claude/skills/*/SKILL.md` skills or `.claude/agents/*.md` subagents directly. ADR-0015 D2's primary intent — preventing hooks from auto-billing the user via LLM API calls — is preserved by D1.1 ("no LLM API calls" criterion). A tooling process that meets D1.1 cannot make LLM calls; it cannot invoke skills or subagents (which run inside the Claude Code agent context with LLM calls).

The line is: spawned process makes no LLM calls and serves only localhost. Anything that violates either constraint is forbidden under this ADR and falls back to ADR-0015 D2's original three-category restriction.

### D3: Cross-platform spawn pattern per ADR-0030

Per [ADR-0030](0030-windows-gitbash-hardening.md) cross-platform Windows Git Bash hardening, the tooling-spawn pattern uses:
- `python3` preferred; `python` fallback (Windows Git Bash often only has `python` on PATH)
- `nohup "$CMD" >/dev/null 2>&1 &` for backgrounding (Git Bash on Windows: same pattern as Linux/macOS works in practice; tested per PRD-DSH slice 2)
- `disown` after `&` to detach from the parent shell's job table (Git Bash compat)
- All file paths must use forward slashes; `$CLAUDE_PROJECT_DIR` may contain Windows backslashes — convert with `${VAR//\\//}` if needed

### D4: R-LOC scope clarification — `dashboard/*` is a tooling artifact, NOT runtime

The R-LOC reviewer rule caps runtime-artifact diff at 300 LoC per slice per `reviewer.md` canonical scope. The canonical "runtime artifact" set, sourced from `r-loc.md` (`last_updated: 2026-05-26`), is: `.claude/agents/*.md`, `.claude/skills/*/SKILL.md`, `.claude/hooks/*.sh`, `.claude/settings.json`. Paths NOT in this set (e.g., `decisions/`, `CLAUDE.md`, `README.md`, `tests/`, `.github/`) are non-runtime by omission.

`dashboard/*` (any path under the `dashboard/` directory) is **also non-runtime by omission** under the current canonical set. This ADR's D4 records that interpretation explicitly so future contributors don't second-guess: `dashboard/*` is a tooling artifact (analogous to its motivation — it is the spawned target of D1), not Claude Code agent runtime config. The dashboard server is:
- A separate Python process from the Claude Code agent runtime
- Observed by, not consumed by, the agent runtime
- Optional infrastructure (Claude Code agent works without it)

This ADR does NOT itself amend `reviewer.md`'s R-LOC rule body — the current `r-loc.md` canonical scope already excludes `dashboard/*` by omission. PRD-DSH slice 1 ships with this interpretation; reviewer's R-LOC check on slice 1 passes either by the current omission semantics OR by the ~225 LoC slice 1 estimate being well under the 300 LoC cap regardless. PRD-DSH slice 2 may optionally add an explicit `dashboard/*` line to `reviewer.md`'s R-LOC rule body (and to `r-loc.md` if not yet retired by PRD #341); deferred to OQ-5 (Open questions).

`tools/*` is NOT in this ADR's scope. No current tooling-spawn instance lives under `tools/`. If a future ADR amendment adds such an instance under `tools/`, that ADR amendment can extend D4 at that time. YAGNI applies here.

### D5: 6-critic-cap honored per ADR-0008 D7

[ADR-0008](0008-workflow-autolog-bootstrap-and-naming.md) D7 caps the project at 6 critics. This ADR introduces no critic. The dashboard is an observation tool; it has no APPROVE/BLOCK verdict semantics. Critic count remains 6 (`reviewer`, `prd-critic`, `adr-critic`, `slicer-critic`, `glossary-critic`, `backlog-critic`).

### D6: Bootstrap-mode acknowledgment per ADR-0004 D2

The "tooling-spawn" carveout (D1) binds **forward** from this ADR's merge. Existing hooks at PRD-DSH merge time:
- `session-start.sh` (ADR-0023 D2) — observation; no tooling-spawn; unchanged
- `user-prompt-submit.sh` (ADR-0023 D5) — observation; unchanged
- `user-prompt-submit-topic-nudge.sh` (ADR-0026 D4) — being retired in PRD #341 Slice 6
- `pre-tool-edit.sh` (ADR-0023 D3, ADR-0028 D1, ADR-0030 D3) — validation; unchanged
- `pre-tool-bash.sh` (ADR-0023 D4) — validation; unchanged
- `stop-reviewer-gate.sh` (ADR-0029 D1) — validation; unchanged
- `dashboard-autostart.sh` (PRD-DSH slice 2, NEW) — tooling-spawn; authorized by this ADR D1

Future tooling-spawn additions require ADR amendments to D1's authorized-instances list.

## Consequences

### Positive

- **Authorizes the dashboard auto-start** (PRD-DSH zero-friction lifecycle per user grill Q3 = 3B)
- **Preserves ADR-0015 D2's core intent** — no LLM-call auto-billing via hooks; D1's four criteria + D2's reaffirmation enforce this strictly
- **Bounded** — only specific tooling-spawn instances; not a blanket relaxation; future additions need ADR amendments
- **Cross-platform** — D3 pattern works on Windows Git Bash + Linux + macOS per ADR-0030
- **R-LOC clarification** (D4) records that `dashboard/*` is non-runtime by omission under the current canonical scope; the rule's intent (preventing runaway agent body bloat) is preserved for `.claude/`
- **6-critic-cap preserved** (D5); no observability ≠ critic class confusion

### Negative / Accepted

- **Hooks are no longer purely observation** — they may now spawn observation tools. Mitigated by D1's strict four-criterion gate.
- **Drift risk**: future contributors may attempt to spawn non-observation tooling (e.g., an editor process, a build watcher) without ADR amendment. Mitigated by D1's "future additions require ADR amendment" + D2's reaffirmation of the skill/subagent exclusion. R-BOY-SCOUT extended in PRD-DSH slice 2 to include `dashboard/*` in trigger paths catches drift at PR-review time.
- **Multi-instance risk**: if multiple Claude Code sessions fire SessionStart simultaneously, both hooks may attempt to spawn. Mitigated by D1.4 (idempotent spawn check) + the OS's port-binding semantics (only one process can bind 8765; second one fails harmlessly).
- **Process orphan risk**: when the spawning Claude Code session ends, the dashboard process may or may not be killed depending on `nohup`/`disown` behavior on the platform. Mitigated by D1's idempotent spawn (next session detects + spawns if needed) + manual `kill $(lsof -ti:8765)` as user escape hatch.
- **R-LOC scope is interpretation-based for `dashboard/*`** (D4) — relies on the current `r-loc.md` canonical scope's omission semantics rather than an explicit allowlist entry. Future contributors must reach D4 to confirm `dashboard/*` is non-runtime; if a reviewer round-1 BLOCK fires on this point, OQ-5 captures the optional explicit-listing fix.

## Alternatives considered

- **Alt-A: Keep ADR-0015 D2 unchanged; use bootstrap.sh daemon (grill Q3 = 3C).** Rejected: stretches ADR-0008 D6 (bootstrap.sh is a one-time fresh-clone setup, not a process manager); Windows daemon management painful; bootstrap re-runs would restart the daemon mid-work.
- **Alt-B: Keep ADR-0015 D2 unchanged; require manual dashboard start (grill Q3 = 3A).** Rejected: user explicitly chose zero-friction auto-start (Q3 = 3B). Manual start adds friction that user has indicated they don't want.
- **Alt-C: Blanket relaxation — hooks may spawn anything.** Rejected: loses ADR-0015 D2's core safety (auto-billing prevention); opens future drift risk where contributors spawn editors / IDE plugins / external services from hooks.
- **Alt-D: New `/dashboard` skill that the user invokes (grill Q3 = 3D).** Rejected: shadow-skill defect ([#191](https://github.com/vojtech-stas/project-claude/issues/191)) has bitten 2× already this session with `/to-prd` and `/to-issues` shadowed by personal-scope skills; would bite a third time. Skill-to-background-process fork is also brittle.
- **Alt-E: Pre-tool-use hook spawns dashboard.** Rejected: PreToolUse fires per-edit, not per-session; would spawn many times. SessionStart is the correct lifecycle event for a one-per-session spawn.
- **Alt-F: Tooling-spawn category but without the 4-criterion gate.** Rejected: too permissive; loses bounded-criteria protection that preserves ADR-0015 D2's intent.
- **Alt-G: Categorize dashboard as a "skill" via abuse of `.claude/skills/dashboard/`.** Rejected: skills are LLM-invoked at runtime, not background processes; would also walk into Alt-D's shadow-skill defect.
- **Alt-H: Drop dashboard auto-start entirely; ship manual-start only.** Rejected: undermines grill Q3 decision. User wants zero-friction visibility into pipeline; manual-start is the consolation prize, not the goal.

## Open questions deferred

- **OQ-1**: SSE reconnect strategy on dashboard server restart — handled by browser-native `EventSource` auto-reconnect; PRD-DSH slice 2 implementer judgment.
- **OQ-2**: Multi-Claude-Code-session collision behavior beyond port-binding — single-user assumption per PRD-DSH §3 non-goals.
- **OQ-3**: Dashboard process orphan policy when spawning session ends — accepted per Consequences; manual cleanup via `kill $(lsof -ti:8765)`; future ADR amendment if recurrent issue.
- **OQ-4**: Whether to expand "tooling-spawn" criteria to non-localhost services (Tailscale, Wireguard internal IPs, etc.) — not in scope; future ADR amendment if needed.
- **OQ-5**: Whether to explicitly add a `dashboard/*` line to `reviewer.md`'s R-LOC rule body (and to `r-loc.md` if not yet retired by PRD #341) for forward clarity — deferred per D4; the current omission semantics handle this correctly; explicit listing is style/clarity only. Decision: optional in PRD-DSH slice 2 cascade.
- **OQ-6**: Whether `tools/cascade-finder.py` (existing) retroactively becomes a "tooling-spawn" instance — NO; cascade-finder is invoked as a one-shot CLI by other agents/scripts, not spawned by hooks. Only D1.4 (idempotent hook-spawn) applies, and cascade-finder is not hook-spawned.

## Future direction

- **PRD-DSH slice 2 ships the canonical tooling-spawn instance** (dashboard-autostart.sh)
- **Future tooling-spawn instances** (if any) require ADR amendments to D1's authorized-instances list
- **R-BOY-SCOUT trigger paths** (per PRD-DSH slice 2) include `dashboard/*` so PR-review-time drift detection catches accidental violations
- **Possible follow-up**: R-TOOLING-SPAWN reviewer rule that mechanically verifies new files added under `dashboard/*` honor the 4 criteria (no LLM imports, no `0.0.0.0` binding, etc.) — deferred; YAGNI until needed

## References

**Authorized tooling-spawn instances (D1):**

1. `dashboard/server.py` spawned by `.claude/hooks/dashboard-autostart.sh` (PRD-DSH slice 2, this ADR's introducing PRD)

Future authorized instances will be appended to this list via ADR amendments.

**Related ADRs:**

- [ADR-0015](0015-claude-code-hooks-adoption.md) D2 — hook scope policy; extended by D1 above (4th category added)
- [ADR-0023](0023-validation-and-notification-hooks-extension.md) D2 — SessionStart hook; additive extension per PRD-DSH
- [ADR-0030](0030-windows-gitbash-hardening.md) — cross-platform spawn pattern per D3 above
- [ADR-0028](0028-pretooluse-spec-gate.md) — spec-gate compliance for PRD-DSH slices
- [ADR-0029](0029-stop-reviewer-signoff-gate.md) — Stop hook (validation); unaffected by this ADR
- [ADR-0008](0008-workflow-autolog-bootstrap-and-naming.md) D7 — 6-critic-cap preserved per D5
- [ADR-0004](0004-bypass-prevention.md) D1 — joint-APPROVE gate (this ADR ships alongside PRD-DSH); D2 bootstrap-mode per D6
- [ADR-0003](0003-autonomous-pipeline-with-critics.md) D8 — macro-ADR placement alongside introducing PRD
- [ADR-0031](0031-knowledge-architecture-v2.md) — separate PRD #341 in progress addresses KB-related scope; unrelated to this ADR's scope
- [decisions/README.md](README.md) "What an ADR is" — ADR immutability preserved (no edits to ADR-0015's file body; extension via supersession mechanism declared in the Extends header above)

**Sources:**

- 2026-05-29 grill session — design decisions Q1-Q4
- PRD-DSH body (drafted alongside) — implementing PRD
- ADR-0015 D2 — original hook scope policy being extended
- Community dashboards researched: [disler](https://github.com/disler/claude-code-hooks-multi-agent-observability) (similar SessionStart-hook pattern; instructive prior art for the tooling-spawn category)
