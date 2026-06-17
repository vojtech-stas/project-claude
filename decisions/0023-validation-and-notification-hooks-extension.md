---
id: ADR-0023
status: accepted
supersedes: []
superseded_by: []
scope: hooks
rule_ids:
  - HOK-003
  - HOK-004
  - HOK-005
---
# ADR-0023: Validation and notification hooks extension — SessionStart state injection + PreToolUse blocking (partially fulfills ADR-0015 D6)

- **Status:** Accepted
- **Date:** 2026-05-22
- **Supersedes:** none.
- **Extends:** [ADR-0015](0015-claude-code-hooks-adoption.md) D1 (hooks in `.claude/settings.json` — config location preserved unchanged), D2 (hook scope: logging/validation/notification ONLY — preserved unchanged; new hooks fit existing scope), D4 (log location `.claude/logs/` — N/A here; these hooks are validation/notification, not logging), D5 (bootstrap-mode forward-binding pattern reused in D9 below), D6 (this ADR PARTIALLY FULFILLS the "Validation hooks (commit-message format, branch naming, etc.) — future PRDs can add per D6" deferred direction); [ADR-0004](0004-bypass-prevention.md) D2 (bootstrap-mode policy cited in D9); [ADR-0004](0004-bypass-prevention.md) D3 (workflow-enforcement layer stack — this ADR adds the runtime/session-level Layer 4 complement to git Layer 1); CLAUDE.md rule #10 (main-agent meta-output discipline — now mechanically escalated via PreToolUse `"ask"` decision); CLAUDE.md rule #11 (surface deferred work — N/A here; PostToolUse nudge is explicitly OUT of scope per the parent PRD §3).

## Context

ADR-0015 D2 limits Claude Code hooks to "logging / validation / notification" and D6 explicitly defers validation hooks as a future direction. The current `.claude/settings.json` has 5 hooks (4 PostToolUse + 1 Stop), all logging-only per ADR-0016. Two failure patterns have demonstrated they need the validation/notification layer ADR-0015 D6 deferred:

1. **CLAUDE.md rule #10 (main-agent meta-output discipline) violations.** Across multiple sessions the main agent has hand-authored tracked files by accident; reviewer catches it post-PR but only after wasted round-trip cost. Per docs.claude.com/en/docs/claude-code/best-practices: *"Hooks are deterministic and guarantee the action happens"* — unlike CLAUDE.md prose, which is advisory.

2. **Stale-worktree false-alarm recurring defect (backlog #173).** Documented twice in two distinct session contexts (the second documented in the very same session that drafted this ADR; recorded as comment on #173 dated 2026-05-22). Root cause: agents do not check `git fetch + git log HEAD..origin/main` before reading local files; they trust the local worktree base. Concrete impact: main agent drafted a duplicate of already-merged ADR-0015 because local worktree was 21 commits behind main. A `SessionStart` hook injecting `additionalContext` with branch + divergence-count + open work would catch the staleness immediately; this is exactly the pattern docs.claude.com/en/docs/claude-code/hooks documents in the "Inject Context at SessionStart" walkthrough.

User mandate (2026-05-22): *"I want to have like a smart way how to do this workflow and that we are not going outside of the path of this project."*

PRDs B (#179) and C (#181) ship the *advisor understanding* of hooks (`/best-practice-subagents` + `/best-practice-hooks` skills). This ADR's parent PRD ships the *enforcement layer* the advisors describe. Both are independent applications of the same ADR-0015 foundation.

**Thematic scope of this ADR (per adr-critic Round 1 Rec):** the ADR covers BOTH Claude Code session-level hooks (D1-D5) AND a sibling git-side hook addition (D6 — new `.githooks/commit-msg`), framed as a single joint "workflow-enforcement-layer additions" deliverable per ADR-0004 D3's layer-stack architecture (Layer 1 = git hooks; Layer 4 = Claude Code hooks). Bundling the two layers in one ADR reduces ADR-ceremony overhead per the Alt-F rejection rationale below; slicer/implementer may still split the work across slices.

## Decisions

### D1: Four new hooks added to `.claude/settings.json` (additive to existing 5)

The project's `.claude/settings.json` gains 4 new hook entries, additive to (not replacing) the existing 5 logging hooks:

- **`SessionStart`** event (1 new entry; the event was previously absent from settings.json)
- **`UserPromptSubmit`** event (1 new entry; previously absent)
- **`PreToolUse`** event with matcher `Edit|MultiEdit|Write` (1 new entry; the event was previously absent)
- **`PreToolUse`** event with matcher `Bash` (1 new entry; same event but distinct matcher)

The existing 5 hooks (PostToolUse × 3 + Stop × 1, plus the initial PostToolUse(Edit|MultiEdit|Write) subagent-edit logger) are preserved unchanged. All new hooks are `command` type only — no HTTP / MCP / prompt / agent types per parent PRD §3 YAGNI.

### D2: SessionStart hook injects live workflow state

The SessionStart hook (`.claude/hooks/session-start.sh`) reads SessionStart JSON on stdin and emits `hookSpecificOutput.additionalContext` containing:

- Current git branch (`git symbolic-ref --short HEAD`)
- Divergence vs `origin/main` (`git fetch origin main 2>/dev/null && git rev-list --count HEAD..origin/main`)
- Recent commits (`git log --oneline -5`)
- Open `slice`-labeled issues (count + 3 most-recent titles via `gh issue list --label slice --state open --json number,title --limit 3`)
- Open PRs (count + 3 most-recent titles)
- Open `captured`-labeled issues (count + 3 most-recent titles)

Output capped at 50 lines / 4KB to honor the docs-stated 10,000-char hook output cap with headroom. The hook eliminates the recurring stale-worktree false-alarm pattern (backlog #173) at the moment of session start — the divergence count surfaces immediately in the agent's context, before any local file reads can be miscalibrated.

### D3: PreToolUse(Edit|MultiEdit|Write) hook mechanically escalates rule #10

The PreToolUse(Edit|MultiEdit|Write) hook (`.claude/hooks/pre-tool-edit.sh`) reads the tool-call JSON on stdin and inspects `tool_input.file_path`. Decision logic:

1. If env var `CLAUDE_AGENT_TYPE` is set (subagent context per docs.claude.com), **allow** (no emit; default permission flow applies). Subagents are the implementer + reviewer + critic surfaces; their writes ARE the PR pipeline.
2. Else if `file_path` matches the permitted-without-prompt allowlist (`.claude/projects/**` transcripts, `tool-results/**`, paths not under git's tracked-files set), **allow**.
3. Else if `git ls-files --error-unmatch <path>` succeeds (tracked file), emit `hookSpecificOutput.permissionDecision: "ask"` with reason: *"Main-agent write to tracked file — rule #10 says flow through PR pipeline. Confirm if this is an I3 trivial-lane edit (≤10 LoC, `trivial` label, branch `hotfix/<issue#>-…`); cancel and use /to-prd or /ship otherwise."*

The `"ask"` decision (NOT `"deny"`) preserves trivial-lane I3 ergonomics per ADR-0003 D1 — the user confirms or cancels rather than being hard-blocked. Hard-block would erode the legitimate fast-path.

### D4: PreToolUse(Bash) hook blocks dangerous git operations

The PreToolUse(Bash) hook (`.claude/hooks/pre-tool-bash.sh`) reads stdin JSON and pattern-matches `tool_input.command` against:

- `git push.*\borigin\s+main\b` (any flavor; matches `--force`, `--force-with-lease`, plain push) → `permissionDecision: "deny"` with reason *"Direct push to main forbidden per CLAUDE.md rule #4; open a PR instead."*
- `git push.*--force.*\borigin\s+main\b` (defense-in-depth pattern; logically subsumed by the broader pattern but explicit for clarity) → same deny.
- `git commit.*-m.*\bWIP\b` → **warn-only** via `systemMessage`; not blocked. WIP commits violate ADR-0001 commit-style guidance but are not so dangerous they merit hard-deny.

Other dangerous patterns (`rm -rf /`, `git reset --hard origin/<unsynced>`) are NOT covered in slice-1 — Claude Code's built-in auto-mode classifier already catches obvious destructive ops. This hook adds only the project-specific main-protection guardrails.

### D5: UserPromptSubmit nudges feature-request prompts toward `/grill-me`

The UserPromptSubmit hook (`.claude/hooks/user-prompt-submit.sh`) inspects the user's prompt for feature-request triggers (`(I want to (build|add|implement))|(we should add)|(let's add)`). If matched AND the prompt does NOT contain `/grill-me`, `/ship`, `trivial`, or `hotfix` substrings, the hook emits `hookSpecificOutput.additionalContext: "User prompt matches feature-request pattern. If the design isn't settled yet, consider /grill-me before /ship."`

Non-blocking notification — the agent may still proceed with a direct response; the nudge just reminds the agent to consider the pipeline. Reduces "I jumped past /grill-me" misuse.

### D6: New `.githooks/commit-msg` hook for conventional-commits format validation

**Git-hook-type correction (per prd-critic Round 1 Finding):** the `pre-commit` hook fires BEFORE `$EDITOR` is invoked and receives no commit-message-file argument — it cannot validate commit-message content. Git's canonical hook for commit-message-content validation is `commit-msg`, which fires AFTER `$EDITOR` closes and receives `COMMIT_EDITMSG` path as `$1`. This ADR therefore creates a NEW `.githooks/commit-msg` file (sibling to the existing `.githooks/pre-commit`), NOT an extension of pre-commit.

The new `.githooks/commit-msg` performs three checks on `$1` (the COMMIT_EDITMSG path):

- **Conv-commits subject regex:** read first non-comment line of `"$1"` (skip `#`-prefixed lines); match against `^(feat|fix|docs|chore|refactor|test|perf|style|build|ci)(\(.+\))?: [a-z]`. Fail-fast on mismatch with a clear error message naming CLAUDE.md rule #5.
- **≤72-char subject cap:** first non-comment line length ≤ 72. Fail-fast on overflow.
- **Co-Authored-By trailer:** **warn-only** (not block) if commit body lacks `Co-Authored-By: Claude`. Main-agent commits should have it, but missing trailer doesn't break correctness — warn-only preserves CI ergonomics for human-only commits.

Existing `.githooks/pre-commit` (branch-name regex + main-block per ADR-0004 D3 Layer 1) is UNCHANGED. `.githooks/install.sh` already sets `core.hooksPath .githooks` directory-wide, so the new sibling file is picked up automatically; no install.sh edit needed (slicer/implementer verifies).

Mechanizes the previously-prose-only CLAUDE.md rule #5.

### D7: Hook scripts live under `.claude/hooks/` (depart from ADR-0015 Alt-E inline pattern)

ADR-0015 Alt-E rejected the script-file pattern in favor of inline commands in `.claude/settings.json` for walking-skeleton simplicity. That was right at the time — the inline hooks were single-line `jq | echo | tee` pipelines. The 4 new hooks here are 30-50 LoC each (decision logic, multi-step JSON construction, fallback paths). Extracting them to `.claude/hooks/<name>.sh` is the natural follow-on per ADR-0015 D6 future direction (which explicitly contemplates "new PRD" or "trivial-lane PR" or "within an existing PRD" as the paths for new-hook additions) and ADR-0015's own open question *"Should the hook command be extracted to a separate script file as more hooks land? Defer."*

This ADR makes the call: extract. The existing 5 inline hooks stay inline (no refactor in this PRD per parent §3 non-goal); new hooks ship as separate files. Future PRD may unify by refactoring inline hooks into files; out of scope here.

Each script:
- ≤50 LoC (simplicity discipline; keep behavior auditable)
- Reads stdin JSON via `jq`
- Emits decision JSON on stdout (or empty + exit 0 for "allow with no emit")
- Bash shebang `#!/bin/bash` + `set -euo pipefail`
- Soft-degrades on missing `jq` (same convention as existing inline hooks per ADR-0016 D-IDs)

`bootstrap.sh` is extended with one idempotent step (`chmod +x .claude/hooks/*.sh 2>/dev/null || true`) so fresh clones get executable hooks.

### D8: ADR-0015 D2 scope policy preserved unchanged

D2 of ADR-0015 explicitly limits hooks to "logging / validation / notification" and forbids skill/subagent auto-invocation. This ADR's 4 new hooks fit cleanly inside that scope:

- SessionStart additionalContext = **notification**
- PreToolUse(Edit|Write) `"ask"` = **validation** (with escalation to user)
- PreToolUse(Bash) `"deny"` = **validation**
- UserPromptSubmit additionalContext = **notification**

No hook here invokes a skill or subagent. ADR-0015 D2's policy stands; this ADR PARTIALLY FULFILLS D6 by adding the validation/notification slice D6 deferred, while preserving D2's invariant.

### D9: Bootstrap-mode acknowledgment (per ADR-0004 D2)

All hooks bind **forward from the slice that ships them**. No retroactive sweep:

- Past sessions ran without these hooks; their artifacts are grandfathered.
- Past PRs and commits are not retroactively validated against the new commit-msg conv-commits format check.
- Existing 22 ADRs, 12 skills, 9 subagents are UNCHANGED by this PRD (modulo the documented cascade-doc edits, all per ADR-0005 D3 slicer cascade-doc check):
  - CLAUDE.md Map row addition for `.claude/hooks/`
  - CLAUDE.md "Pipeline operational logic" section gains a 4-line summary of the new hooks
  - README.md "Workflow enforcement" section gains explicit Layer 4 enumeration
  - `decisions/README.md` ADR-0015 index-row Status column updated to *"Accepted (D6 partially fulfilled by ADR-0023 — validation + SessionStart additions; D2 scope policy preserved unchanged)"* — mirrors the documented pattern of ADR-0013 D5 (Status update to ADR-0003 row) and ADR-0012's update to ADR-0007 row
  - `decisions/README.md` gains new ADR-0023 index row

Forward binding starts at slice-1 merge: every new session from that moment forward fires the SessionStart hook; every new tool call from that moment forward fires the PreToolUse hooks; every new commit from that moment forward passes the new `.githooks/commit-msg` conv-commits format check (the existing `.githooks/pre-commit` branch-name + main-block checks are unchanged and continue to apply as before).

The 6-critic-cap meta-rule (ADR-0008 D7) is unaffected — no new critic added. Hooks are infrastructure, not critics.

## Consequences

### Positive

- **Deterministic escalation of rule #10.** Main-agent writes to tracked files now escalate to user via PreToolUse `"ask"` decision; failure mode shifts from "reviewer catches post-PR" to "user confirms or cancels pre-write". Round-trip cost reduced.
- **Stale-worktree false-alarm mitigated at session start.** SessionStart hook injects branch + divergence-count + open work into every new session's context immediately — the recurring #173 pattern is caught before any local file reads can be miscalibrated.
- **Dangerous git ops mechanically blocked.** `git push origin main` (any flavor) is prevented, not just discouraged by CLAUDE.md prose.
- **Feature-request misuse reduced.** UserPromptSubmit nudge catches "user typed a feature request without /grill-me" before the agent commits to a path.
- **Pre-commit checks tightened.** Conv-commits format mechanically enforced; rule #5 no longer pure discipline.
- **ADR-0015 D6 progress.** Validation-hooks deferred direction partially fulfilled; future PRDs can extend further within the same D2 scope policy.
- **Foundation for future scoped hooks** per ADR-0015 D6 future direction. Per-skill / per-subagent `hooks:` frontmatter would layer on top of these project-level hooks.

### Negative / Accepted

- **PreToolUse `"ask"` adds confirmation friction for legitimate trivial-lane I3 edits.** Chosen explicitly over `"deny"` to preserve I3 ergonomics. If excessive in practice, future PRD refines allowlist (e.g., auto-allow when branch matches `hotfix/*`).
- **`CLAUDE_AGENT_TYPE` env var reliability unverified.** OQ-1: implementer dogfoods + documents. Fallback: always `"ask"` (escalate, don't silently allow).
- **SessionStart hook adds session-start latency.** Runs `git fetch` (network) + 3 `gh api` calls. Cap at 50 lines / 4KB output. If latency unacceptable, future PRD moves to async or `Setup` hook.
- **Hook scripts add maintenance surface.** 4 small bash scripts to maintain (≤50 LoC each per D7). Mitigation: scripts deliberately tiny + behavior auditable; per-script ownership clear.
- **Windows PowerShell parity deferred.** Git Bash on Windows handles bash scripts; documented as known limitation in slice-1 PR body.
- **Hook output capped at 10,000 chars per docs.** The SessionStart hook's output budget of 4KB stays well under, but the cap could in theory be hit if open work counts explode. Defer until observed.
- **The existing 5 inline hooks are NOT refactored** to match the new file pattern. Per §3 non-goal of parent PRD. Refactoring is a separate cleanup PRD if desired (LoC-cheap; could be trivial-lane).

## Alternatives considered

- **Alt-A: Don't add validation hooks; keep relying on CLAUDE.md prose + reviewer + pre-commit.** Rejected — the recurring rule #10 violations and stale-worktree false-alarm pattern demonstrate that advisory-only enforcement is insufficient. The Tier-1 source explicitly recommends hooks for deterministic enforcement.
- **Alt-B: Hard-block (`"deny"`) for rule #10 instead of `"ask"`.** Rejected — would block legitimate trivial-lane I3 edits and erode ergonomics. `"ask"` preserves the escape hatch.
- **Alt-C: Hooks at user-scope (`~/.claude/settings.json`) instead of project-scope.** Rejected per ADR-0015 D1 — project-scope is the only choice that makes hooks part of the project's enforcement contract; user-scope means each developer configures separately.
- **Alt-D: Ship hooks via plugin instead of in-repo `.claude/settings.json`.** Rejected for slice-1 simplicity. Plugins add a distribution layer that's overkill when hooks are project-specific.
- **Alt-E: Add a "hook-rule registry" abstraction (DSL on top of bash scripts).** Rejected as YAGNI — `.claude/settings.json` IS the registry per docs.claude.com canonical pattern.
- **Alt-F: Ship the extended pre-commit conv-commits validation as a separate PRD.** Rejected — both are "workflow-enforcement layer additions" thematically; bundling reduces PRD-ceremony overhead. Slicer can still split across slices if combined slice-1 overflows the LoC cap (see parent PRD §4).
- **Alt-G: Don't extract hook scripts (keep ADR-0015 Alt-E inline pattern).** Rejected — inline hooks for 30-50 LoC scripts are unreadable in JSON; extraction is the natural follow-on per ADR-0015 D6's own deferred OQ.
- **Alt-H: Don't add SessionStart state injection (leave session continuity per ADR-0006 D2 as-is).** Rejected — the recurring stale-worktree false-alarm pattern is directly addressed by D2's live state injection. ADR-0006 D2's prose-procedure approach is preserved (the hook can fail or be disabled); D2 here adds a complementary mechanical layer.
- **Alt-I: Include the PostToolUse(Edit|Write) "captured-reminder" nudge in slice-1.** Rejected — out per parent PRD §3 non-goal. The existing PostToolUse logging is enough; a separate nudge hook is a further-future concern. Avoids slice-1 bloat.
- **Alt-J: Use HTTP hooks instead of command hooks.** Rejected — adds network dependency for purely local checks. Command hooks are the docs-canonical shape.
- **Alt-K: Use `prompt` or `agent` hook types for the nudge logic.** Rejected per ADR-0015 D2 — those types push closer to "auto-invocation of skills/subagents from hooks" which D2 explicitly forbids on the reality-check ground. Command hooks emitting `additionalContext` is the legal shape.

## Open questions deferred

- **OQ-1 (per parent PRD §6): `CLAUDE_AGENT_TYPE` env var reliability.** Implementer verifies via dogfood; fallback documented in D3.
- **OQ-2: Windows `.githooks/commit-msg` regex portability.** Implementer verifies via Git Bash; POSIX `case` fallback if needed.
- **OQ-3: Bootstrap-mode for already-cloned repos.** Document upgrade path in slice-1 PR body.
- **OQ-4: SessionStart hook performance.** Defer-to-async if latency surfaces.
- **OQ-5: Pre-commit conv-commits regex strictness on edge cases** (reverts, merge commits). Document exception path if surfaces.
- **OQ-6: Per-skill / per-subagent `hooks:` frontmatter** (still deferred per ADR-0015 D6 future direction). Future PRD.
- **OQ-7: Refactor of existing 5 inline hooks into separate `.sh` files** to match the new file pattern. Future cleanup PRD (LoC-cheap; could be trivial-lane).

## Future direction

- **Per-skill / per-subagent hooks** per ADR-0015 D6 future direction. Most likely first targets: `/ship`'s SubagentStop hook to verify clean dispatch state; `slicer-critic`'s PreToolUse(Bash) hook to enforce `gh api` over local `decisions/` reads (the stale-worktree #173 systematic fix at the critic dispatch level).
- **Hook-firing observability.** A SessionEnd or PostToolBatch hook that logs hook firings to `.claude/logs/hook-events.jsonl` (extending ADR-0016) for debug/audit.
- **PowerShell `.ps1` siblings** for Windows-native parity.
- **CI integration** (backlog #63 + GitHub Actions): the same hooks could fire in CI via headless `claude -p` to validate PRs server-side.
- **Refactor existing 5 inline hooks** into separate `.sh` files for consistency (trivial-lane candidate).

## References

- docs.claude.com/en/docs/claude-code/hooks — Tier-1 source for hook event schemas, configuration shape, exit codes, decision JSON schemas, `${CLAUDE_PROJECT_DIR}` placeholder, the "Inject Context at SessionStart" + "Block destructive commands" walkthroughs.
- docs.claude.com/en/docs/claude-code/best-practices — *"Hooks are deterministic and guarantee the action happens"* (the motivating quote).
- docs.claude.com/en/docs/claude-code/sub-agents — subagent context env vars (basis for D3's `CLAUDE_AGENT_TYPE` detection).
- [ADR-0001](0001-foundational-design.md) — CLAUDE.md rule #4 (no direct push to main, original 7-rule set), rule #5 (conventional commits, original 7-rule set).
- [ADR-0004](0004-bypass-prevention.md) D4 — CLAUDE.md rule #10 origin (main-agent meta-output discipline; later refined by ADR-0009 D1).
- [ADR-0009](0009-discipline-tightening.md) D1 — current rule #10 wording (supersedes ADR-0004 D4's narrower scope).
- [ADR-0009](0009-discipline-tightening.md) D2 — CLAUDE.md rule #11 mandatory-capture wording (supersedes ADR-0006 D4's discretionary phrasing).
- [ADR-0003](0003-autonomous-pipeline-with-critics.md) D1 (3-tier PRD/Slice/PR hierarchy preserved); D8 (macro-ADR placement — this ADR drafted alongside the parent PRD).
- [ADR-0004](0004-bypass-prevention.md) D2 (bootstrap-mode policy cited in D9); D3 (workflow-enforcement defenses — extended with the runtime/session-level Layer 4 complement); D4 (R-META rule citation context).
- [ADR-0005](0005-output-shape-and-slicing-methodology.md) D3 (cascade-doc check the slicer must apply for CLAUDE.md Map + Pipeline operational logic + README workflow-enforcement section + decisions/README index row + bootstrap.sh chmod step).
- [ADR-0006](0006-backlog-and-session-continuity.md) D2 (session continuity via live-state reconstruction — D2 here adds the mechanical layer complementing the existing prose-procedure).
- [ADR-0008](0008-workflow-autolog-bootstrap-and-naming.md) D7 (6-critic-cap meta-rule — honored, no new critic added).
- [ADR-0015](0015-claude-code-hooks-adoption.md) D1 (hooks config location preserved); D2 (scope policy preserved unchanged — new hooks fit logging/validation/notification); D4 (log location N/A here); D5 (bootstrap-mode pattern reused); D6 (partially fulfilled by this ADR — validation + SessionStart additions; scope policy D2 preserved unchanged).
- [ADR-0016](0016-workflow-event-log-jsonl.md) D2 (hook-based delivery pattern — applied here for the 4 new hooks); D5 (bootstrap-mode pattern reused).
- [ADR-0022](0022-docs-first-kb-pattern.md) D2 (Tier-1 source-priority hierarchy — docs.claude.com is the canonical authority for the hook layer design).
- Backlog [#173](https://github.com/vojtech-stas/project-claude/issues/173) — stale-worktree false-alarm recurring defect; this ADR's D2 SessionStart hook is the **first systematic fix** of the three layers #173's 2026-05-22 comment proposed.
- Parent PRD: see GitHub Issue (the PRD this ADR ships alongside per ADR-0003 D8).
- `.claude/hooks/` — directory created by this ADR.
- `.claude/settings.json` — file extended by D1-D5.
- `.githooks/commit-msg` — new file created by D6.
- `.githooks/pre-commit` — file UNCHANGED by this ADR (existing branch-name + main-block checks preserved per D6).
- `bootstrap.sh` — file extended by D7.
