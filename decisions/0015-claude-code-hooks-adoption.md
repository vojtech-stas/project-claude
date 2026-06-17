---
id: ADR-0015
status: accepted
supersedes: []
superseded_by: []
scope: hooks
rule_ids:
  - HOK-001
  - HOK-002
---
# ADR-0015: Claude Code hooks adoption — policy + walking-skeleton (PostToolUse logging hook)

- **Status:** Accepted
- **Date:** 2026-05-21
- **Supersedes:** none
- **Extends:** [ADR-0004](0004-bypass-prevention.md) D2 (bootstrap-mode policy cited in D5 below); [ADR-0008](0008-workflow-autolog-bootstrap-and-naming.md) D3 (inline-firing convention — preserved unchanged; hooks are additive, not replacement). The `.githooks/pre-commit` server-side git hooks per [ADR-0004](0004-bypass-prevention.md) remain canonical for git-level enforcement; this ADR introduces a Claude-Code-session-level complement.

## Context

The project has 10 subagents, 8+ skills, 14 ADRs, and an autonomous pipeline that runs end-to-end without human gates between stages. Many conventions today rely on **agent discipline**:

- Rule #11 mandatory capture (per ADR-0009 D2)
- Inline-firing of `/promote-to-backlog` after `gh issue create --label captured` (per ADR-0008 D3)
- Periodic `/audit-subagents` invocation (per ADR-0011)
- Cascade-doc updates per ADR-0005 D3

When an agent forgets one of these, the captured-tier graveyard or post-PRD audit catches the drift, but the drift still occurs. Claude Code **hooks** (shell commands triggered on Claude Code tool events, configured in `.claude/settings.json`) provide a mechanism to enforce or observe at the session level — complementing the server-side git hooks (`.githooks/pre-commit` per ADR-0004) and the (not-yet-shipped) CI hooks (backlog #63).

User-raised 2026-05-21 (captured as backlog [#127](https://github.com/vojtech-stas/project-claude/issues/127)) from Anthropic YouTube videos: hooks are an unused automation surface.

**Reality-check (important constraint):** Claude Code hooks are **shell commands**. They can validate (exit nonzero to block), log (write to files), or notify (stderr). They **cannot directly invoke Claude Code skills or subagents** — those require active session interaction. This bounds what hooks can do: they are a logging/validation/notification layer, not an orchestration replacement.

This ADR establishes the **hook-adoption policy** for the project + ships ONE walking-skeleton hook (PostToolUse logging on subagent edits) to demonstrate the mechanism.

## Decisions

### D1: Hooks live in `.claude/settings.json`

Project-wide Claude Code hooks configured in `.claude/settings.json` under the `hooks` section. Per-event configuration (PreToolUse, PostToolUse, Stop, UserPromptSubmit, etc.) follows the Claude Code documented schema. Per-developer overrides via `.claude/settings.local.json` are NOT used in slice 1 (deferred per PRD §6 OQ#1).

### D2: Hook scope — logging / validation / notification ONLY

Hooks may:
- **Log** to local files (e.g., session events, edit notifications, audit triggers)
- **Validate** by exit code (block tool execution when input violates a policy)
- **Notify** via stderr (print a message to the user)

Hooks may NOT:
- **Auto-invoke** Claude Code skills or subagents (technically impossible; requires session interaction)
- **Modify Claude Code session state** beyond what shell commands naturally do
- **Bypass** the existing convention layers (ADR-0008 D3 inline-firing, ADR-0009 D2 mandatory capture, etc.) — hooks are additive enforcement, not replacement

This bounded scope keeps hooks simple and prevents the "hooks-become-an-orchestration-layer" anti-pattern.

### D3: Walking-skeleton hook — PostToolUse(Edit) on subagent files

The slice-1 hook fires on `PostToolUse(Edit)` when the edited file path matches `.claude/agents/.*\.md`. Behavior: appends one line to `.claude/logs/subagent-edits.log` containing `<ISO8601-timestamp> <file-path> (edit detected; consider running /audit-subagents)`. Pure logging; no blocking; no skill invocation.

**Why this hook:** demonstrates the mechanism end-to-end with zero blocking risk; dovetails with PRD-β (workflow log) which will consume the log substrate; catches subagent edits the moment they happen so the user knows to re-run `/audit-subagents`.

### D4: Log location — `.claude/logs/` (gitignored)

Slice 1's hook writes to `.claude/logs/subagent-edits.log`. The `.claude/logs/` directory is added to `.gitignore` — logs are local-to-developer, not committed. Future PRDs (likely PRD-β workflow log per #131) may extend the log location or format, but the local-only stance stands unless a future ADR explicitly changes it.

### D5: Bootstrap-mode acknowledgment (per ADR-0004 D2)

This ADR's mechanism binds **forward from slice-1 merge**. Specifically:
- Hook policy applies to NEW hooks added from slice-1 forward; the slice-1 PostToolUse(Edit) hook is the first.
- Existing pre-slice-1 sessions (no hooks configured) are unaffected.
- Future PRDs adding new hooks must honor D2's scope policy (logging/validation/notification only; no skill auto-invocation).
- `.githooks/pre-commit` per ADR-0004 D2 stands unchanged (server-side git layer; orthogonal to Claude Code hook layer).

The 6-critic-cap (ADR-0008 D7) is unaffected — hooks are not critics.

### D6: Future hook additions follow ADR-amendment-or-new-PRD pattern

A hook is added either via:
- **New PRD** for substantive new hook (e.g., commit-message validation, captured-tier autopilot trigger)
- **Trivial-lane PR** (≤10 LoC, no behavior change beyond convention) for tiny additions (e.g., add a second logging hook with the same shape as D3)
- **Within an existing PRD** if the hook is part of that PRD's scope (e.g., PRD-β workflow log may add a Stop hook to flush log buffer)

ADR-0015 itself does not need to be re-superseded when individual hooks are added; only when the D2 scope policy changes.

## Consequences

### Positive

- **Enforcement layer at Claude Code session level** complementing server-side git hooks + (future) CI hooks
- **Observability seed:** the slice-1 log file is a minimal substrate that PRD-β workflow log can extend
- **User awareness:** when an agent edits a subagent file, the user gets a passive reminder (log entry) without needing to manually scan diffs
- **Demonstration:** future PRDs adding hooks have a working example to follow

### Negative / Accepted

- **Hooks can't replace orchestration.** The reality-check (hooks are shell commands; can't invoke skills) means several attractive use cases (auto-fire `/promote-to-backlog`, auto-fire `/audit-subagents`) are NOT achievable via hooks alone. Mitigation: D2 scope policy is explicit.
- **Slice-1 hook is informational only.** No defect-prevention value beyond reminding the user. Acceptable for walking-skeleton; future hooks (validation-flavored) can add defect prevention.
- **Log file is local-only.** No central aggregation; no cross-developer observability. Acceptable for current single-developer state; revisit if/when the project goes multi-developer.
- **Adds a setup-knowledge requirement.** New contributors must understand that `.claude/settings.json` hooks fire automatically. Mitigation: README + CLAUDE.md cascade-docs explain.

## Alternatives considered

- **Alt-A: No hooks (status quo).** Rejected — user-requested + concrete value from logging seed for PRD-β.
- **Alt-B: Multiple hooks in slice 1.** Rejected per PRD §3 — walking-skeleton ships ONE hook to demonstrate the mechanism; additional hooks land via future PRDs.
- **Alt-C: PreToolUse(Bash) commit-message validation as the walking-skeleton hook** (instead of PostToolUse(Edit) logging). Rejected per Q-α1 — bigger scope (regex parse, edge-case handling, false-positive blocking risk); .githooks/pre-commit already covers it server-side.
- **Alt-D: Auto-invoke `/audit-subagents` from the hook.** Rejected per D2 reality-check — Claude Code hooks cannot invoke skills directly. The log entry includes a manual-reminder note; the user reads it and chooses to invoke.
- **Alt-E: Hook command as a separate script file** (`.claude/hooks/subagent-edit-log.sh`) instead of inline in settings.json. Rejected for walking-skeleton — inline is simpler; refactor to script files if more complex hooks land (per PRD §6 OQ#4).
- **Alt-F: Use `.claude/settings.local.json` for the hook** (per-developer). Rejected — project-wide hook is the right scope for a convention that applies to all contributors.
- **Alt-G: Replace ADR-0008 D3 inline-firing convention with a hook-based mechanism.** Rejected per Out-of-scope — hooks can't invoke `/promote-to-backlog` directly; even if they could indirectly (write a marker file that a periodic skill reads), that's a larger architectural shift better grilled in its own PRD.

## Open questions deferred

- **Will the slice-1 log file rotate / cap in size?** Defer until size becomes a problem.
- **Will additional hook events** (Stop, UserPromptSubmit, PreToolUse on specific tools) prove useful? Defer to future PRDs; ADR-0015 D6 allows them.
- **Should the hook command be extracted to a separate script file** as more hooks land? Defer per D6.
- **Per-developer hook overrides** via `.claude/settings.local.json`? Defer.
- **Hook-based replacement of inline-firing conventions** (ADR-0008 D3)? Defer; today's stance is hooks are additive.

## Future direction

- **PRD-β workflow log (backlog #131)** — extends the log substrate this ADR seeds
- **Validation hooks** (commit-message format, branch naming, etc.) — future PRDs can add per D6
- **PRD-γ audit-meta consolidation (backlogs #129 + #130 + #47)** — may use hooks for periodic-cadence triggering if/when feasible
- **CI integration (backlog #63)** — orthogonal but composable; CI fires server-side, hooks fire client-side, audit skills fire on-demand

## References

- [ADR-0004](0004-bypass-prevention.md) D2 — bootstrap-mode policy cited in D5
- [ADR-0008](0008-workflow-autolog-bootstrap-and-naming.md) D3 — inline-firing convention (preserved)
- [ADR-0008](0008-workflow-autolog-bootstrap-and-naming.md) D7 — 6-critic-cap (unaffected — hooks are not critics)
- [ADR-0011](0011-subagent-quality-framework.md) — audit-subagents skill (the manual-reminder target in D3's log message)
- Backlog [#127](https://github.com/vojtech-stas/project-claude/issues/127) — the captured item this ADR ships from
- Backlog [#131](https://github.com/vojtech-stas/project-claude/issues/131) — PRD-β workflow log; extends slice-1's log substrate
- Backlog [#63](https://github.com/vojtech-stas/project-claude/issues/63) — CI / branch protection R3/R4; orthogonal server-side layer
- `.claude/settings.json` — the config file modified
- `.githooks/pre-commit` — the server-side complement (unchanged)
- Anthropic Claude Code hooks documentation (implementer reads at slice time for exact env var names + schema)
