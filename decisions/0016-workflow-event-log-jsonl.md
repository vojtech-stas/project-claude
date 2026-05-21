# ADR-0016: Workflow event log — JSONL via hooks (extends PRD-α hook substrate)

- **Status:** Accepted
- **Date:** 2026-05-21
- **Supersedes:** none
- **Extends:** [ADR-0015](0015-claude-code-hooks-adoption.md) D1 (hooks in `.claude/settings.json`), D2 (hook scope: logging/validation/notification — this ADR's events are pure logging), D4 (log location `.claude/logs/`), D5 (bootstrap-mode forward-binding pattern reused). [ADR-0006](0006-backlog-and-session-continuity.md) D2 (live-state session reconstruction — the workflow log is a new session-reconstruction artifact). [ADR-0004](0004-bypass-prevention.md) D2 (bootstrap-mode policy cited in D5 below).

## Context

PRD-α (PRD [#132](https://github.com/vojtech-stas/project-claude/issues/132)) shipped the Claude Code hooks adoption substrate: `.claude/settings.json` hooks section, `.claude/logs/` location (gitignored), policy that hooks are for logging/validation/notification only (not skill auto-invocation). The walking-skeleton hook (PostToolUse(Edit) on subagent file edits) was post-merge-fixed via PR #135 after verification found two schema bugs.

User-raised 2026-05-21 (backlog [#131](https://github.com/vojtech-stas/project-claude/issues/131)): there is no readable audit log of which skills/agents fired in what order. Today's observability is artifacts-only (GitHub Issues + PRs + reviewer comments + pipeline metadata footers). This ADR ships PRD-β: extend the hook substrate with three more hooks that write structured JSONL events to `.claude/logs/workflow-events.jsonl`.

The grill session for PRD-β (Q1-Q5 on 2026-05-21) locked the following:
- **Q1=1A**: PRD-β and PRD-γ ship as separate PRDs (per earlier meta-grill Q2=2A 3-PRD lock)
- **Q4=4A**: JSONL format + hook-based delivery (over in-skill instrumentation, Markdown timeline, or hybrid)
- **Q5=5A**: 3 hook events — PostToolUse(Agent) + PostToolUse(Bash) + Stop (excluding noisy PreToolUse and privacy-sensitive UserPromptSubmit)

## Decisions

### D1: JSONL format (one JSON object per line, append-only)

The workflow event log uses **JSONL** (JSON Lines) format: one valid JSON object per line, no enclosing array, append-only. Rationale:
- **Grep-friendly**: each line is independently parseable; `grep '"event": "agent_complete"' .claude/logs/workflow-events.jsonl` works
- **AI-readable**: any LLM session can parse line-by-line without loading the whole file
- **Append-safe**: append-only means no read-modify-write race condition between concurrent hook invocations
- **Industry-standard**: JSONL is widely supported (jq, Logstash, Fluentd, etc.)

Markdown timelines, YAML, plain text formats explicitly rejected per Q4 alternatives.

### D2: Hook-based delivery only (no in-skill instrumentation)

All log events are written by Claude Code hooks in `.claude/settings.json`. No skill or subagent body writes log entries directly. Rationale:
- **Walking-skeleton-pure**: zero per-skill churn (10+ skills + 8+ subagents would each need instrumentation otherwise)
- **DRY**: one logging mechanism in one config file
- **Hook substrate already exists** (PRD-α); this ADR extends rather than introduces

If hook-based capture proves insufficient for rich workflow semantics (e.g., capturing critic verdict APPROVE/BLOCK), a future PRD may add hybrid in-skill instrumentation. Out of scope here.

### D3: Three event types in slice 1 (per Q5=5A)

- **`agent_complete`** — fired by `PostToolUse(Agent)`. Captures subagent invocations. Schema:
  ```json
  {"ts": "<ISO8601>", "event": "agent_complete", "subagent_type": "<from tool_input.subagent_type>", "description": "<from tool_input.description, truncated to 100 chars>"}
  ```
- **`bash_complete`** — fired by `PostToolUse(Bash)`. Captures bash commands. Schema:
  ```json
  {"ts": "<ISO8601>", "event": "bash_complete", "command": "<from tool_input.command, truncated to 200 chars>"}
  ```
- **`session_stop`** — fired by `Stop`. Session boundary marker. Schema:
  ```json
  {"ts": "<ISO8601>", "event": "session_stop"}
  ```

Truncation prevents giant commands or descriptions from bloating the log. Truncation marker: `…[truncated]` appended when content exceeds the cap.

Per D6 below, future PRDs may add events; the JSONL one-object-per-line format itself is locked.

### D4: Log location — `.claude/logs/workflow-events.jsonl`

Co-located with PRD-α's `subagent-edits.log` under `.claude/logs/` (already gitignored). Single project-wide log; no per-session split (the `event: session_stop` lines mark boundaries). Anchored via `$CLAUDE_PROJECT_DIR` per the PR #135 hook-fix pattern.

### D5: Bootstrap-mode acknowledgment (per ADR-0004 D2)

The 3 new hooks bind **forward from slice-1 merge**. Pre-merge sessions had no workflow log; post-merge sessions append events as they run. No retroactive log reconstruction. Existing PRD-α hook (`subagent-edits.log`) is unchanged; the new hooks append to a different file (`workflow-events.jsonl`).

The 6-critic-cap (ADR-0008 D7) is unaffected — hooks are not critics.

### D6: Future event additions

Adding new event types (e.g., `edit_complete`, `read_complete`, `write_complete`) does NOT supersede this ADR — D1/D2/D4 format/delivery/location decisions stand. New events are added via:
- **New PRD** if substantive (e.g., adding 5+ new event types)
- **Trivial-lane PR** if adding 1-2 events to fill a specific observability gap
- **Within an existing PRD** if the event is part of that PRD's scope

The JSONL schema is open — future events add new fields freely; consumers ignore unknown fields per standard JSONL practice.

## Consequences

### Positive

- **Closes user-flagged observability gap** ("I am not sure if the agents and skills are firing correctly") for the highest-leverage events (subagent invocations + bash commands + session boundaries)
- **Session continuity per ADR-0006 D2 extended**: next-session can read `workflow-events.jsonl` to understand what last session did, instead of inferring from git log + gh issue list
- **Substrate for future PRDs**: backlog #129/#130/#47 audit-meta PRD can read events from this log; future query skill could grep against it
- **Hook substrate proven**: 3 more hooks validate the PRD-α + PR #135 pattern works for non-trivial cases

### Negative / Accepted

- **JSONL grows unbounded**: no rotation in slice 1. Acceptable for walking-skeleton (file size likely <1MB per typical session); revisit if files become unwieldy.
- **Missing fine-grained events** (Read/Write/Edit individually). Q5 excluded PreToolUse + finer PostToolUse events; future PRD can broaden.
- **Bash commands captured verbatim**: if a command contains a secret, it's logged. Mitigation: existing convention is don't-put-secrets-in-bash-commands; `.claude/logs/` is gitignored so secrets don't ship to remote.
- **jq dependency**: each hook uses jq for stdin parsing. Soft-degrades on missing-jq machines (event silently not logged). Per PR #135 discussion: acceptable trade.
- **No query interface**: users grep the JSONL directly. Acceptable for walking-skeleton; future `/show-workflow-log` skill can compose later.

## Alternatives considered

- **Alt-A: Markdown timeline format.** Rejected per Q4 — weaker AI-parseability; harder to grep specific events; harder to compose with future query skills.
- **Alt-B: YAML format.** Rejected — JSONL is more universal; YAML's whitespace-sensitivity makes append-only writes brittle.
- **Alt-C: In-skill instrumentation** (each skill/subagent body writes log entries). Rejected per Q4 — 18+ files of instrumentation churn; DRY violation; harder to keep consistent.
- **Alt-D: Hybrid** (hooks for tool events + in-skill for workflow semantics). Rejected per Q4 — 2 mechanisms to maintain; walking-skeleton scope creep; start simple, add later if hook-only proves insufficient.
- **Alt-E: External logging (write to local file + push to syslog/Datadog).** Rejected — overkill for single-developer repo; out of scope.
- **Alt-F: Per-session log files** (one JSONL per session ID). Rejected — single-file with `session_stop` boundary markers is simpler for walking-skeleton; per-session split can be added if needed.
- **Alt-G: Include PreToolUse hook** for "tool starting" events. Rejected per Q5 — fires on every tool call (thousands of lines per session); noise.
- **Alt-H: Include UserPromptSubmit hook** for "user said X" events. Rejected per Q5 — captures full user input verbatim (privacy + noise).
- **Alt-I: Include SessionStart hook** for "session begin" events. Rejected per Q5 — Stop is sufficient for boundary marking; SessionStart adds marginal value.
- **Alt-J: ALL 6+ events** (the broad Q5=5C option). Rejected — log bloat; walking-skeleton scope creep.

## Open questions deferred

- **JSONL growth**: rotation strategy if files become unwieldy. Defer until observed.
- **Event sufficiency**: will 3 events suffice or will users want fine-grained PostToolUse(Edit/Write/Read)? Defer to post-merge observation.
- **Query interface**: `/show-workflow-log` skill? Defer; grep suffices.
- **jq universality**: will jq be available on all developer machines? Soft-degrade is acceptable for walking-skeleton.
- **Per-session vs single-file**: revisit if multi-developer scenarios emerge.

## Future direction

- **PRD-γ audit-meta (backlog #129+#130+#47)** — may read this log as an audit input (e.g., "did /audit-subagents fire in the last 7 sessions?")
- **`/show-workflow-log` query skill** — composable viewer / filterer
- **Rich workflow event capture** (critic verdicts, slice progress) via hybrid in-skill instrumentation
- **Per-session log splitting** if multi-developer scenarios emerge
- **Log rotation / cap** if growth becomes problematic

## References

- [ADR-0015](0015-claude-code-hooks-adoption.md) D1, D2, D4, D5 — hook substrate this ADR extends
- [ADR-0006](0006-backlog-and-session-continuity.md) D2 — session continuity (extended by the workflow log)
- [ADR-0004](0004-bypass-prevention.md) D2 — bootstrap-mode policy cited in D5
- [ADR-0008](0008-workflow-autolog-bootstrap-and-naming.md) D7 — 6-critic-cap (unaffected; hooks aren't critics)
- Backlog [#131](https://github.com/vojtech-stas/project-claude/issues/131) — the captured item this ADR ships from
- PRD [#132](https://github.com/vojtech-stas/project-claude/issues/132) — PRD-α hooks adoption (the substrate)
- PR [#135](https://github.com/vojtech-stas/project-claude/pull/135) — hook-fix that established the canonical schema + jq pattern this ADR uses
- Claude Code hooks docs — https://code.claude.com/docs/en/hooks
- `.claude/settings.json` — the config file being extended
- `.claude/logs/workflow-events.jsonl` — the new log file
