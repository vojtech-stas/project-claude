# ADR-0028: PreToolUse spec-existence gate — artifact-gated tracked-file edits

- **Status:** Accepted
- **Date:** 2026-05-26
- **Supersedes:** none
- **Extends:** [ADR-0015](0015-claude-code-hooks-adoption.md) D2 (hook scope policy — D2 below honors logging/validation/notification by adding a VALIDATION layer; no skill/subagent invocation); [ADR-0023](0023-validation-and-notification-hooks-extension.md) D3 (PreToolUse Edit|Write hook — extended additively with spec-gate logic BEFORE the existing rule-#10 escalate-to-ask fallback); [ADR-0023](0023-validation-and-notification-hooks-extension.md) D7 (hook scripts under `.claude/hooks/` — same placement); [ADR-0026](0026-knowledge-architecture-truth-docs.md) D1+D2+D4+D5+D7 (truth-doc surface — this ADR ships `docs/current/hooks.md` as the third topic backfill after `qa-automation.md` (PRD-K) and `subagents.md` (PRD-LM, per ADR-0027); registers `hooks` in `.claude/topics.json` per D4 topic-nudge hook wiring extended by D6 below); [ADR-0004](0004-bypass-prevention.md) D2 (bootstrap-mode policy cited by D7); [ADR-0008](0008-workflow-autolog-bootstrap-and-naming.md) D7 (6-critic-cap meta-rule — preserved per D8); [decisions/README.md](README.md) *"What an ADR is"* (ADR immutability — this ADR doesn't edit prior ADRs).

## Context

User stated (2026-05-26): *"it is hard to start the workflow without grill me or even deeper."*

Current PreToolUse Edit|Write hook per ADR-0023 D3 emits `permissionDecision: "ask"` when the main agent edits a tracked file. This is a NUDGE, not a BLOCK. The user has to click "allow once" to proceed, but nothing prevents editing tracked files outside the `/grill-me → /ship` pipeline.

CLAUDE.md rule #10 ("main agent never hand-authors any tracked file") is enforced by:
1. CLAUDE.md prose (squishy — relies on agent obedience)
2. ADR-0023 D3 PreToolUse "ask" hook (relies on user clicking the right button)

There is no **artifact-gated** enforcement — no mechanical check that an approved spec (a `prd`-labeled OR `slice`-labeled open GitHub issue + matching branch naming `<type>/<issue#>-...`) exists before tracked-file edits are allowed.

Captured backlog [#219](https://github.com/vojtech-stas/project-claude/issues/219) proposes artifact-gated enforcement: extend the PreToolUse Edit|Write hook to BLOCK (`permissionDecision: "deny"`) when no in-flight PRD/slice issue exists for the current branch, with trivial-lane (hotfix) carveout preserved.

This ADR codifies that extension + ships `docs/current/hooks.md` as the third topic backfill truth-doc per ADR-0026 D7 bootstrap-mode forward (after `qa-automation.md` from PRD-K and `subagents.md` from PRD-LM).

## Decisions

### D1: Spec-gate runs BEFORE the existing rule-#10 ask fallback

The PreToolUse Edit|Write hook chain is extended additively:
1. (preserved) Subagent context skip → exit 0
2. (preserved) `tool-results/` allowlist → exit 0
3. (NEW) Spec-gate: branch + issue check (D2)
4. (preserved) Rule-#10 escalate-to-ask fallback

Spec-gate either DENIES (no matching issue or no matching branch pattern) OR falls through to the existing fallback (matching issue exists; preserve user choice on whether to proceed without further interruption).

### D2: Spec-gate logic

Parse current branch with `git rev-parse --abbrev-ref HEAD`. Extract issue number via regex:
- Branch `<type>/<N>-<slug>` where `<type>` ∈ {feat, fix, docs, chore, refactor, test, perf, style, build, ci} → extract `<N>`; standard pipeline
- Branch `hotfix/<N>-<slug>` → extract `<N>`; trivial-lane (I3) carveout (issue must still exist, but the slice/prd label is optional)
- Other branches (no match) → deny with: *"Branch does not match `<type>/<issue#>-...` pattern. Run /grill-me + /ship to create a PRD/slice before editing tracked files."*

For matched branches, run `gh issue view <N> --json state,labels` and check:
- Issue exists + open → fall through to existing rule-#10 ask fallback
- Issue closed → deny with: *"Issue #<N> is closed; current branch references a closed issue. Run /grill-me + /ship for a fresh PRD/slice."*
- Issue doesn't exist (gh returns error) → deny with: *"Issue #<N> doesn't exist; branch references a stale or invalid issue number. Run /grill-me + /ship for a fresh PRD/slice."*

### D3: Trivial-lane (I3) carveout preserved

`hotfix/<N>-<slug>` branches allow tracked-file edits if issue `<N>` exists + is open. The trivial-lane (per CLAUDE.md I3) accepts PRs ≤10 LoC with `trivial` label without full PRD/slice ceremony, but does require an audit-trail issue. The hook checks issue existence, not label match — the reviewer enforces the `trivial` label at PR time.

### D4: Soft-degrade behavior when `gh` is unavailable

If `command -v gh` returns false, the spec-gate falls through to the existing rule-#10 ask fallback (does NOT deny). Defense-in-depth: when the validation tool is unavailable, the user retains the rule-#10 ask mechanism per existing behavior. Avoids hard-blocking the user when GitHub CLI is missing.

Same soft-degrade applies if `gh issue view <N>` returns a network error (rate limit, transient API failure): treat as "can't verify" and fall through to ask, not deny.

### D5: New `docs/current/hooks.md` truth-doc

Per ADR-0026 D1 format. Single H1 / Status / Date / Active synthesis (markdown table of all current hooks) / Sources. Hook table columns: event | script | when fires | what it does | scope policy | ADR. Lists 7 hook entries across 5 events: SessionStart, PreToolUse Edit|Write, PreToolUse Bash, UserPromptSubmit grill-nudge, UserPromptSubmit topic-nudge, PostToolUse logging, Stop logging.

Per ADR-0026 D7 bootstrap-mode forward: this is the third topic backfill after `qa-automation.md` from PRD-K and `subagents.md` from PRD-LM. Subsequent PRDs adding or modifying a `decisions/NNNN-*.md` ADR file that affects the hooks topic (e.g., PRD-P Stop hook signoff per #220) must amend this truth-doc per R-TRUTH-DOC.

### D6: `.claude/topics.json` gains `hooks` entry

Per ADR-0026 D4 topic-nudge hook wiring. Keywords: `["hook", "hooks", "PreToolUse", "PostToolUse", "SessionStart", "UserPromptSubmit", "Stop hook", "spec-gate"]`. Implementer adjusts per OQ-6.

### D7: Bootstrap-mode acknowledgment (per ADR-0004 D2)

Spec-gate binds FORWARD from slice 1 merge:
- Existing branches at merge time get the new check on next tracked-file edit; if they don't match the pattern (e.g., old `wip/...` branch), user creates a proper issue + branch
- No retroactive sweep of stale branches
- Hook tested on PR's own branch as dogfood (slice 1 must demonstrate it self-validates)

### D8: 6-critic-cap honored per ADR-0008 D7

ADR-0028 adds NO new critic. Extension is purely hook-layer (validation script). Critic count remains 6.

### D9: R-TRUTH-DOC self-satisfaction

PR touches `decisions/0028-pretooluse-spec-gate.md` (NEW) AND `docs/current/hooks.md` (NEW) → R-TRUTH-DOC SATISFIED in same PR per ADR-0026 D5. Third topic backfill exercise of the rule after PRD-K's inaugural (qa-automation.md) and PRD-LM's second (subagents.md).

### D10: Cascade-doc updates

- `.claude/hooks/pre-tool-edit.sh` — spec-gate logic added per D2 (preserved fallback per D1)
- `decisions/0028-pretooluse-spec-gate.md` — this ADR (NEW)
- `decisions/README.md` — ADR-0028 index row in numerical order
- `docs/current/hooks.md` — NEW truth-doc per D5
- `.claude/topics.json` — `hooks` entry per D6
- `CLAUDE.md` — NO update (truth-doc is canonical; CLAUDE.md slim is PRD-R territory)
- `README.md` — NO update (truth-doc surface generically mentioned by PRD-N)

## Consequences

### Positive

- **Mechanical /grill-me enforcement** — user can no longer start a feature in raw conversation without going through the pipeline. Spec-gate physically denies the edit.
- **Defense-in-depth preserved** — rule-#10 ask fallback still catches edge cases the spec-gate doesn't cover.
- **Trivial-lane preserved** — I3 hotfix workflow unchanged for legitimate small fixes.
- **Soft-degrade graceful** — gh-unavailable case doesn't hard-block.
- **Second topic-backfill exercise of R-TRUTH-DOC** — hooks.md truth-doc proves PRD-K's mechanism scales to multiple topics.
- **6-critic-cap preserved.**
- **Subagent context skip preserved** — subagents continue to work without prompts (the legitimate PR pipeline path).

### Negative / Accepted

- **gh API per edit costs latency** — ~200-500ms per tracked-file edit. Mitigated by spec-gate firing only on first edit per branch (Claude Code caches the permission decision per session per file pattern). Future PRD may cache.
- **Branch-pattern parser brittle to typos** — `feat/999-foo` parses but `feat999-foo` (missing slash) doesn't. Accepted; the brittleness IS the enforcement (forces canonical branch names).
- **Stale branch on rebase** — if user rebases onto main after the issue is closed, edits get blocked. Forces fresh branch; consistent with rule #10 intent.
- **Truth-doc maintenance** — `docs/current/hooks.md` must update with every hook change. Acceptable per ADR-0026 R-TRUTH-DOC pattern.
- **No CLAUDE.md rule #15** — spec-gate enforces existing rule #10 rather than introducing a new rule. Accepted; reduces rule sprawl.

## Alternatives considered

- **Alt-A: Hard-deny ALL tracked-file edits without spec-gate carveouts.** Rejected — too restrictive; user couldn't even hotfix.
- **Alt-B: Add CLAUDE.md cross-cutting rule #15** ("spec-gate requires PRD"). Rejected — squishy; rule is already #10 + mechanical enforcement codified here.
- **Alt-C: New `spec-gate-critic` subagent.** Rejected — breaches 6-critic-cap; hook layer is the right home.
- **Alt-D: Pre-commit git hook instead of PreToolUse Claude hook.** Rejected — pre-commit fires too late (after edit + add); PreToolUse fires BEFORE the write.
- **Alt-E: `/audit-meta` rule for spec-gate drift.** Captured for future PRD; not in slice 1 scope.
- **Alt-F: Cache `gh issue list --label slice,prd --state open` for the session.** Rejected — slice 1 ships per-invocation `gh issue view` for accuracy; cache is OQ-1 deferred.
- **Alt-G: Skip truth-doc update.** Rejected — R-TRUTH-DOC mechanically forces it; would BLOCK at reviewer.
- **Alt-H: Combine with PRD-P (Stop hook signoff) in one ADR.** Rejected — distinct concerns (PreToolUse vs Stop event); separate ADRs cleaner.

## Open questions deferred

- OQ-1: per-invocation `gh issue view` vs cached `gh issue list`
- OQ-2: trivial-lane carveout scope (hotfix only vs also chore)
- OQ-3: exact deny message wording per case
- OQ-4: soft-degrade behavior detail
- OQ-5: retroactive applicability to existing branches
- OQ-6: topics.json keyword precision

## Future direction

- `/audit-meta` rule for spec-gate drift (per Alt-E)
- Cached `gh issue list` per OQ-1 if perf bites
- Extending spec-gate to PreToolUse Bash for git-shape commands editing tracked files

## References

- 2026-05-26 user mandate (verbatim in §1)
- captured #219 — origin of this PRD
- [ADR-0015](0015-claude-code-hooks-adoption.md) D2 — hook scope policy
- [ADR-0023](0023-validation-and-notification-hooks-extension.md) D3+D7 — extended
- [ADR-0026](0026-knowledge-architecture-truth-docs.md) D1+D2+D4+D5+D7 — truth-doc surface
- [ADR-0027](0027-subagent-model-selection.md) — precedent for topic-backfill truth-doc (subagents.md)
- CLAUDE.md rule #10 — main-agent meta-output discipline (enforced mechanically by this ADR)
- `.claude/hooks/pre-tool-edit.sh` — file extended
- `docs/current/hooks.md` — file created
