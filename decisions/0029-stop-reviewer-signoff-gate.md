# ADR-0029: Stop hook reviewer-signoff gate — block session-stop if in-flight PR lacks reviewer APPROVE

- **Status:** Accepted
- **Date:** 2026-05-26
- **Supersedes:** none
- **Extends:** [ADR-0002](0002-autonomous-merge-policy.md) (autonomous merge — reviewer is sole gate per PR; this ADR extends the enforcement to Stop event for cases outside /ship); [ADR-0010](0010-implementer-subagent-auto-pipeline.md) D2+D3 (/ship orchestrator dispatches reviewer per slice — preserved; this ADR adds defense-in-depth for cases bypassing /ship); [ADR-0015](0015-claude-code-hooks-adoption.md) D2 (hook scope policy — Stop event is validation/notification only; doesn't invoke skills/subagents); [ADR-0016](0016-workflow-event-log-jsonl.md) (Stop event already used for JSONL logging — coexist, new gate-hook alongside existing logger); [ADR-0023](0023-validation-and-notification-hooks-extension.md) D7 (hook scripts under `.claude/hooks/` — same placement); [ADR-0026](0026-knowledge-architecture-truth-docs.md) D2+D5 (R-TRUTH-DOC enforcement — this PR amends `docs/current/hooks.md` for the new hook); [ADR-0028](0028-pretooluse-spec-gate.md) D5 (hooks truth-doc — being amended, not introduced); [ADR-0004](0004-bypass-prevention.md) D2 (bootstrap-mode policy cited by D7); [ADR-0008](0008-workflow-autolog-bootstrap-and-naming.md) D7 (6-critic-cap meta-rule — preserved per D8); [decisions/README.md](README.md) *"What an ADR is"* (ADR immutability — this ADR doesn't edit prior ADRs).

## Context

User mandate 2026-05-26 task #1 ("ensure the workflow of the agents that we want to have"). Backlog [#220](https://github.com/vojtech-stas/project-claude/issues/220) (captured 2026-05-25, promoted to backlog) proposes a Stop-hook reviewer-signoff gate.

Today's enforcement: reviewer subagent runs at `/ship` stage 4b per ADR-0010 D2/D3, OR via direct dispatch by an aware operator. If main agent operates OUTSIDE `/ship` (user invokes implementer directly, or different orchestration path), nothing mechanically prevents declaring "done" with an unreviewed in-flight PR. Same defect class as the rule #10 "ask"-vs-"deny" gap that ADR-0028 PreToolUse spec-gate addresses — squishy vs mechanical enforcement.

The Stop event fires when Claude finishes responding (per Claude Code hook events per ADR-0015 D2). Today's Stop hook usage: an inline JSONL logger per ADR-0016 — observability, not enforcement. This ADR adds a SECOND Stop hook (`.claude/hooks/stop-reviewer-gate.sh`) for reviewer-signoff enforcement.

## Decisions

### D1: Stop hook checks in-flight PRs for reviewer APPROVE comment

Hook fires on every Stop event. Checks `gh pr list --author @me --state open --json number` for in-flight PRs. For each PR, checks `gh pr view <N> --json comments` for any comment body containing `VERDICT: APPROVE` (the project's reviewer subagent's CRITIC trailer per ADR-0005 D1).

If any in-flight PR lacks an APPROVE comment → emit stderr message + `exit 2` to BLOCK the Stop. Forces the main agent to continue (typically to dispatch the reviewer subagent).

### D2: Override mechanism via `STOP_GATE_BYPASS=1` env var

User can set `STOP_GATE_BYPASS=1` to skip the gate (e.g., "I'm reviewing manually"). Hook emits stderr notification of bypass for audit. Lower friction than sentinel file or per-PR override; env var is session-scoped so doesn't accidentally persist.

### D3: Subagent context skip + soft-degrade

- If `CLAUDE_AGENT_TYPE` set (subagent context) → exit 0 (subagents don't trigger main-agent reviewer-signoff concerns; reviewer subagent's own Stop would otherwise loop)
- If `command -v gh` returns false (gh missing) → exit 0 with stderr warning (defense-in-depth; don't block when validation tool unavailable; matches ADR-0028 D4 pattern)
- If `gh pr list` errors (network / rate-limit) → exit 0 with stderr warning (same logic)

### D4: Coexists with existing JSONL logger Stop hook

Claude Code runs all hooks registered for an event. The existing inline-JSONL Stop logger per ADR-0016 stays unchanged. The new gate hook fires alongside; both can coexist on the same event. settings.json adds a second Stop array entry.

### D5: hooks.md truth-doc AMENDMENT (not new backfill)

Per ADR-0026 D2 + D5 R-TRUTH-DOC, the PR touching `decisions/0029-*.md` must also touch the corresponding `docs/current/<topic>.md` for the hooks topic. The hooks truth-doc was inaugurated by PRD-O (ADR-0028) as the third topic-backfill. This ADR AMENDS that truth-doc to add a new hook row (Stop-reviewer-gate) and updates the Stop event description from "logging only" to "logging + reviewer-signoff gate".

This is the FIRST topic-AMENDMENT exercise of R-TRUTH-DOC (after PRD-K inaugural, PRD-LM/PRD-O backfills); proves the rule scales to incremental updates of existing truth-docs.

### D6: `.claude/topics.json` NO change

`hooks` topic was added by PRD-O. Keywords still cover the new Stop-reviewer-gate per `Stop hook` keyword. No topics.json update needed.

### D7: Bootstrap-mode acknowledgment (per ADR-0004 D2)

Stop-reviewer-gate binds FORWARD from slice 1 merge:
- Existing in-flight PRs (at merge time) get checked on next Stop event; user dispatches reviewer per existing /ship pattern if not already done
- No retroactive sweep of historical sessions
- Hook dogfooded on slice 1's own PR (PR #<this-slice> must satisfy the rule it ships)

### D8: 6-critic-cap honored per ADR-0008 D7

ADR-0029 adds NO new critic. Stop hook is a validation script per ADR-0015 D2; doesn't invoke skills/subagents (hooks can't); doesn't add a critic role. Critic count remains 6.

### D9: R-TRUTH-DOC self-satisfaction

PR touches `decisions/0029-stop-reviewer-signoff-gate.md` (NEW) AND `docs/current/hooks.md` (AMENDED) → R-TRUTH-DOC SATISFIED in same PR per ADR-0026 D5. First truth-doc AMENDMENT exercise of the rule (after 3 topic-backfill inaugurations).

### D10: Cascade-doc updates

- `.claude/hooks/stop-reviewer-gate.sh` — NEW per D1+D2+D3
- `.claude/settings.json` — Stop array gains second entry per D4
- `decisions/0029-stop-reviewer-signoff-gate.md` — this ADR (NEW)
- `decisions/README.md` — ADR-0029 index row in numerical order
- `docs/current/hooks.md` — AMENDED per D5 (add Stop-reviewer-gate row + update Stop event description)
- `.claude/topics.json` — NO change per D6
- `CLAUDE.md` — NO update (truth-doc canonical)
- `README.md` — NO update

## Consequences

### Positive

- **Mechanical reviewer-signoff enforcement** — main agent cannot silently declare done with unreviewed PR.
- **Defense-in-depth** — orthogonal to /ship's reviewer-dispatch (which still works as before for the /ship-led path).
- **Bypass available** — `STOP_GATE_BYPASS=1` for explicit manual-review case; lower friction than per-PR opt-out.
- **Coexists with existing Stop logger** — additive, doesn't break observability.
- **First R-TRUTH-DOC AMENDMENT exercise** — proves rule scales beyond initial topic-backfill.
- **6-critic-cap preserved.**
- **Subagent context skipped** — reviewer subagent's own Stop doesn't loop infinitely.

### Negative / Accepted

- **`gh pr list` latency per Stop** — ~200-500ms; runs on every Stop event. Mitigated by exit-early when no PRs match.
- **`reviewDecision` (gh-native) vs `VERDICT: APPROVE` comment-grep choice** — D1 chooses verdict-comment-grep for project-specific reviewer-subagent fidelity. If a GitHub review (separate from our subagent) approves but our reviewer hasn't, hook still BLOCKs. Accepted tradeoff.
- **Bypass env var requires user remembering** — accepted; manual-review is an exception, not a rule.
- **Cannot auto-dispatch reviewer from hook** (per ADR-0015 D2). Hook nudges via stderr; user/main agent must dispatch.
- **Cannot mechanically detect "I'm reviewing manually" intent** — bypass env var is opt-in by user.

## Alternatives considered

- **Alt-A: PostToolUse hook on Agent dispatch.** Rejected — fires too often (every Agent call); creates noise.
- **Alt-B: Pre-commit git hook on `gh pr merge`.** Rejected — fires too late (merge already happening); also doesn't catch "main agent declares done without merging".
- **Alt-C: GitHub-native reviewDecision check (no comment-grep).** Considered; D1 chose comment-grep for project-specific reviewer-subagent fidelity (the subagent's verdict is the authoritative gate per ADR-0002).
- **Alt-D: New `signoff-critic` subagent.** Rejected — breaches 6-critic-cap; hook layer is the right home.
- **Alt-E: Sentinel file `/tmp/stop-gate-bypass` instead of env var.** Rejected — env var is session-scoped naturally; file persists across sessions.
- **Alt-F: Per-PR override label.** Rejected — too granular; complicates the hook's logic.

## Open questions deferred

- OQ-1: reviewDecision vs verdict-comment-grep (D1 chose latter; implementer can verify)
- OQ-2: bypass mechanism (D2 chose env var)
- OQ-3: fire-on-every-Stop vs context-conditional (D1 chose every Stop)
- OQ-4: exact deny message wording
- OQ-5: dogfood scenario 1 without real unreviewed PR (synthetic input)

## Future direction

- `/audit-meta` rule for stop-gate drift (similar to ADR-0028 future-direction)
- Auto-dispatch hint from hook stderr → main agent reads + acts (not invocation, but instruction)
- Combine with ADR-0028 spec-gate into a unified "workflow enforcement hooks" cluster ADR if pattern grows

## References

- 2026-05-26 user task #1
- captured #220 — origin
- [ADR-0002](0002-autonomous-merge-policy.md) — autonomous merge policy
- [ADR-0010](0010-implementer-subagent-auto-pipeline.md) D2+D3 — /ship reviewer dispatch
- [ADR-0015](0015-claude-code-hooks-adoption.md) D2 — hook scope
- [ADR-0016](0016-workflow-event-log-jsonl.md) — existing Stop logger
- [ADR-0023](0023-validation-and-notification-hooks-extension.md) D7 — hooks under .claude/hooks/
- [ADR-0026](0026-knowledge-architecture-truth-docs.md) D2+D5 — R-TRUTH-DOC
- [ADR-0028](0028-pretooluse-spec-gate.md) D5 — hooks truth-doc (being amended)
- [ADR-0008](0008-workflow-autolog-bootstrap-and-naming.md) D7 — 6-critic-cap (preserved)
- `.claude/hooks/stop-reviewer-gate.sh` — NEW
- `docs/current/hooks.md` — AMENDED
