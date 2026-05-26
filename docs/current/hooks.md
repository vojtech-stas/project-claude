# Hooks — current capability table

- **Status:** current as of 2026-05-26
- **Date:** 2026-05-26
- **Topic slug:** `hooks`

Active synthesis of Claude Code hooks per [ADR-0026](../../decisions/0026-knowledge-architecture-truth-docs.md) D1 — canonical answer to "what hooks are currently wired in this project, and what does each one do?" derived from the immutable ADR chain ([ADR-0015](../../decisions/0015-claude-code-hooks-adoption.md), [ADR-0016](../../decisions/0016-workflow-event-log-jsonl.md), [ADR-0023](../../decisions/0023-validation-and-notification-hooks-extension.md), [ADR-0026](../../decisions/0026-knowledge-architecture-truth-docs.md) D4, [ADR-0028](../../decisions/0028-pretooluse-spec-gate.md), [ADR-0029](../../decisions/0029-stop-reviewer-signoff-gate.md), [ADR-0030](../../decisions/0030-windows-gitbash-hardening.md)) + `.claude/settings.json` registration + scripts under `.claude/hooks/`; regenerated at PR review time per R-TRUTH-DOC ([ADR-0026](../../decisions/0026-knowledge-architecture-truth-docs.md) D5).

## Active hooks (8 entries across 5 events)

Per [ADR-0015](../../decisions/0015-claude-code-hooks-adoption.md) D2 scope policy (logging / validation / notification only — no skill or subagent invocation). Hook scripts live under `.claude/hooks/` per [ADR-0023](../../decisions/0023-validation-and-notification-hooks-extension.md) D7; logging-only hooks remain inline in `.claude/settings.json` per [ADR-0023](../../decisions/0023-validation-and-notification-hooks-extension.md) D7's extraction-when-non-trivial heuristic.

| Event | Script | When fires | What it does | Scope | ADR |
|---|---|---|---|---|---|
| SessionStart | `.claude/hooks/session-start.sh` | Claude Code session opens | Injects `additionalContext` with branch + divergence vs `origin/main` + recent commits + open slice/PR/captured counts; mitigates stale-worktree false-alarm (#173) — warns if jq missing per ADR-0030 D4 | notification | [ADR-0023](../../decisions/0023-validation-and-notification-hooks-extension.md) D2 + [ADR-0030](../../decisions/0030-windows-gitbash-hardening.md) D4 |
| PreToolUse (Edit\|MultiEdit\|Write) | `.claude/hooks/pre-tool-edit.sh` | Before Edit / MultiEdit / Write tool calls | Spec-gate: parses branch via `git rev-parse --abbrev-ref HEAD`, extracts issue number, runs `gh issue view <N>` and emits `permissionDecision: "deny"` when branch lacks an in-flight PRD/slice issue (no matching pattern / closed / missing). Falls through to rule-#10 escalate-to-ask when issue exists+open. Soft-degrades to ask on missing `gh` or network error. Subagent context (CLAUDE_AGENT_TYPE set) and `tool-results/` allowlist bypass the gate — allowlist moved before jq-fallback for Windows Git Bash robustness per ADR-0030 D3; spec-gate per ADR-0028 D1+D2 PRESERVED downstream | validation | [ADR-0023](../../decisions/0023-validation-and-notification-hooks-extension.md) D3 + [ADR-0028](../../decisions/0028-pretooluse-spec-gate.md) D1+D2+D4 + [ADR-0030](../../decisions/0030-windows-gitbash-hardening.md) D3 |
| PreToolUse (Bash) | `.claude/hooks/pre-tool-bash.sh` | Before Bash tool calls | Emits `permissionDecision: "deny"` on `git push ... origin main` (any flavor); mechanically enforces CLAUDE.md rule #4 ("never push directly to main") | validation | [ADR-0023](../../decisions/0023-validation-and-notification-hooks-extension.md) D4 |
| UserPromptSubmit | `.claude/hooks/user-prompt-submit.sh` | User sends a prompt | Detects feature-request-shaped prompts (e.g., "I want to add…", "let's build…") and emits stderr nudge toward `/grill-me` before `/ship`; non-blocking notification | notification | [ADR-0023](../../decisions/0023-validation-and-notification-hooks-extension.md) D5 |
| UserPromptSubmit | `.claude/hooks/user-prompt-submit-topic-nudge.sh` | User sends a prompt | Detects topic keywords from `.claude/topics.json` (qa-automation, subagents, hooks, …) and emits stderr nudge toward the `current-state-reader` subagent + the matching `docs/current/<topic>.md` truth-doc | notification | [ADR-0026](../../decisions/0026-knowledge-architecture-truth-docs.md) D4 |
| PostToolUse (Edit\|MultiEdit\|Write + Agent + Bash) | inline in `.claude/settings.json` | After each Edit / Agent / Bash tool call | Logs subagent edits to `.claude/logs/subagent-edits.log` (Edit matcher) and JSONL events (`agent_complete`, `bash_complete`) to `.claude/logs/workflow-events.jsonl` (Agent + Bash matchers) | logging | [ADR-0015](../../decisions/0015-claude-code-hooks-adoption.md) + [ADR-0016](../../decisions/0016-workflow-event-log-jsonl.md) |
| Stop | inline in `.claude/settings.json` | Claude finishes responding | Appends a `session_stop` JSONL event to `.claude/logs/workflow-events.jsonl` for session-continuity reconstruction per [ADR-0006](../../decisions/0006-backlog-and-session-continuity.md) D2 | logging + reviewer-signoff gate (via sibling script below) | [ADR-0016](../../decisions/0016-workflow-event-log-jsonl.md) |
| Stop | `.claude/hooks/stop-reviewer-gate.sh` | Claude finishes responding | Reviewer-signoff gate: `gh pr list --author @me --state open` then for each PR greps comments for `VERDICT: APPROVE` (reviewer subagent's CRITIC trailer per [ADR-0005](../../decisions/0005-output-shape-and-slicing-methodology.md) D1); emits stderr + `exit 2` to BLOCK Stop when any in-flight PR lacks reviewer APPROVE. Honors `STOP_GATE_BYPASS=1` env override (D2). Skips subagent context (CLAUDE_AGENT_TYPE set) per D3 to avoid reviewer-subagent-own-Stop loop. Soft-degrades to exit 0 on missing `gh`/`jq` or network error. | validation | [ADR-0029](../../decisions/0029-stop-reviewer-signoff-gate.md) D1+D2+D3+D4 |

## Scope policy (per ADR-0015 D2)

Hooks may LOG to local files, VALIDATE by exit code or `permissionDecision`, or NOTIFY via stderr / `additionalContext`. Hooks may NOT invoke skills or subagents (no Skill or Agent tool access — they run as plain bash). This is a reality-check, not a policy choice — Claude Code hooks technically cannot spawn subagents per the platform's tool-boundary model.

The PreToolUse Edit hook (`pre-tool-edit.sh`) is the most expressive example: it combines validation (`permissionDecision: "deny"` for spec-gate violations, `"ask"` for rule-#10 fallback) with soft-degrade defense-in-depth (falls back to "ask" when `gh` is unavailable so the rule-#10 layer still fires).

## Bootstrap-mode (forward-only)

Per [ADR-0028](../../decisions/0028-pretooluse-spec-gate.md) D7: spec-gate binds FORWARD from slice 1 merge. Existing branches at merge time get the new check on next tracked-file edit; if they don't match the canonical pattern (e.g., old `wip/...` branch), the user creates a proper issue + branch. No retroactive sweep of stale branches.

Same bootstrap-mode policy applies to every other hook on this page: each binds FORWARD from its own slice merge per [ADR-0004](../../decisions/0004-bypass-prevention.md) D2.

## 6-critic-cap honored

No hook on this page is a critic. All entries are notification, validation, or logging layers — none emits an APPROVE/BLOCK verdict against another agent's output. [ADR-0008](../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D7 6-critic-cap is preserved across the hook layer.

## Sources

ADRs:

- [ADR-0006](../../decisions/0006-backlog-and-session-continuity.md) D2 — session-continuity reconstruction via live state (logging hooks feed)
- [ADR-0015](../../decisions/0015-claude-code-hooks-adoption.md) D2 — hook scope policy (logging / validation / notification)
- [ADR-0016](../../decisions/0016-workflow-event-log-jsonl.md) — workflow event log JSONL substrate
- [ADR-0023](../../decisions/0023-validation-and-notification-hooks-extension.md) D2 + D3 + D4 + D5 + D7 — SessionStart state injection + PreToolUse Edit ask + PreToolUse Bash deny + UserPromptSubmit grill-nudge + script-extraction policy
- [ADR-0026](../../decisions/0026-knowledge-architecture-truth-docs.md) D4 — UserPromptSubmit topic-nudge hook
- [ADR-0028](../../decisions/0028-pretooluse-spec-gate.md) — PreToolUse spec-existence gate
- [ADR-0029](../../decisions/0029-stop-reviewer-signoff-gate.md) — Stop hook reviewer-signoff gate
- [ADR-0030](../../decisions/0030-windows-gitbash-hardening.md) — cross-platform Windows Git Bash hardening (D3 = pre-jq allowlist position fix; D4 = SessionStart jq-missing warning) (this ADR's home)

Configuration + scripts:

- `.claude/settings.json` — hook registration (matcher + command bindings)
- `.claude/hooks/session-start.sh` — SessionStart additionalContext injector
- `.claude/hooks/pre-tool-edit.sh` — spec-gate + rule-#10 ask fallback
- `.claude/hooks/pre-tool-bash.sh` — push-to-main deny
- `.claude/hooks/user-prompt-submit.sh` — grill-me nudge
- `.claude/hooks/user-prompt-submit-topic-nudge.sh` — current-state-reader nudge
- `.claude/hooks/stop-reviewer-gate.sh` — Stop event reviewer-signoff gate
- `.claude/topics.json` — topic-keyword registry consumed by the topic-nudge hook

CLAUDE.md: "Pipeline operational logic" section + cross-cutting rule #12 — narrative entry pointing here.

External: backlog [#219](https://github.com/vojtech-stas/project-claude/issues/219) — origin of the spec-gate; backlog [#173](https://github.com/vojtech-stas/project-claude/issues/173) — origin of the SessionStart additionalContext injection; backlog [#220](https://github.com/vojtech-stas/project-claude/issues/220) — origin of the Stop hook reviewer-signoff gate (realized by [ADR-0029](../../decisions/0029-stop-reviewer-signoff-gate.md)).
