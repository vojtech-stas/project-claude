---
title: best-practices — Claude Code hooks (design)
summary: Docs-first authoritative guidance for Claude Code hooks — Pre vs PostToolUse, where hook scripts live, scope policy, blocking semantics, SessionStart additionalContext, and the git hook taxonomy. 7 numbered rules distilled from docs.claude.com/hooks{,-guide} + git-scm/githooks per ADR-0022 D1 with mechanical Grep+Target audit hooks.
tags: [best-practice, hooks, docs-first, topic, claude-code]
type: topic
last_updated: 2026-05-27
sources:
  - .claude/skills/best-practice-hooks/SKILL.md
  - decisions/0022-docs-first-kb-pattern.md
  - decisions/0015-claude-code-hooks-adoption.md
  - decisions/0016-workflow-event-log-jsonl.md
---

# best-practices — Claude Code hooks

The canonical KB-layer home of docs-first authoritative guidance for Claude Code **hook design questions** (PreToolUse vs PostToolUse, where hook scripts live, scope policy, blocking semantics, SessionStart `additionalContext`, the git hook taxonomy). Authority: [ADR-0022](../../../decisions/0022-docs-first-kb-pattern.md) D1 (4-section shape) and D8 (PRD-C in the DAG). This topic page is content-equivalent to [`.claude/skills/best-practice-hooks/SKILL.md`](../../../.claude/skills/best-practice-hooks/SKILL.md) on origin/main as of 2026-05-27.

Per [ADR-0031](../../../decisions/0031-knowledge-architecture-v2.md) D10 step 5 of 9, the canonical home of this synthesis is **here in `docs/current/topics/`**, not in the skill body. T5-S8 (#315) thins the skill body to a thin dispatcher shell pointing here; until that ships, edits to either location must update both to prevent drift.

This synthesis encapsulates the rules Anthropic publishes at `docs.claude.com/en/docs/claude-code/{hooks-guide,hooks}` so the project doesn't re-derive them per session or per critic round. On-demand-loaded per ADR-0022 D2 Tier-1 source priority — **zero CLAUDE.md bloat** per the rationale in ADR-0022 Context.

**Distinction from [`topics/hooks`](hooks.md).** That sibling topic is the **current-state capability table** for the hooks wired into THIS project right now (8 entries across 5 events, per ADR-0026 D5 R-TRUTH-DOC regeneration cadence). This topic is the **docs-first authoritative reference** for hook design questions in general — the *why* behind each convention, not the *what is currently wired*.

**Authority chain.** Tier 1 is `docs.claude.com` (canonical, Anthropic-maintained). Tier 3 is `docs/best-practices/*.md` video distillations — none of the existing 5 distillations focus on hooks per `grep -l hook docs/best-practices/*.md`, so the Supplementary section below is intentionally empty (acceptable per ADR-0022 D2 — Tier-3 is supplementary, not required). The Authoritative-guidance section cites Tier 1 only.

**Default conservative.** When a hook question has no rule below that obviously applies, answer "load the canonical page directly: `https://docs.claude.com/en/docs/claude-code/hooks`" rather than guessing. The cost of a wrong rule-projection is a downstream hook built on a false premise (e.g., a PreToolUse hook that exits 1 thinking it blocks — it doesn't; only exit 2 blocks); the cost of an honest "go read the source" is one extra navigation step.

## Authoritative guidance

The 7 numbered rules below distill the hook-relevant guidance from the 2 canonical Anthropic-maintained pages fetched 2026-05-22 (`docs.claude.com/en/docs/claude-code/hooks-guide` and `.../hooks`) plus the canonical git hook taxonomy at `git-scm.com/docs/githooks` (Rule 7). Rules 1, 2, 3, 5, and 7 carry `**Grep:**` + `**Target:**` audit hooks consumable by the future PRD-D `/audit-against-best-practices` skill per ADR-0022 D1; Rules 4 and 6 are judgment-only.

### Rule 1: Hooks are shell commands — they can validate, log, or notify, but cannot invoke skills or subagents

**Rule:** A hook is a shell command (or HTTP/MCP/prompt/agent handler) executed by Claude Code at a lifecycle event. Command hooks communicate ONLY through stdin (JSON input), stdout (JSON output or context text), stderr, and exit codes. They CANNOT trigger `/`-commands, cannot invoke skills, and cannot directly call subagents from a settings-defined hook. Text returned via `additionalContext` is injected as a system reminder Claude reads as plain text, not as an actuator. Honor this scope when designing any new hook.
**Why:** Misunderstanding this is the single most common hook anti-pattern — designers try to use hooks as an orchestration replacement ("auto-fire /audit-subagents after every subagent edit"), which is technically impossible. The project's `ADR-0015 D2` reality-check codifies the same constraint at the project policy level.
**Grep:** `^\s*"type":\s*"command"`
**Target:** `.claude/settings.json`
**Authority:** `https://docs.claude.com/en/docs/claude-code/hooks-guide` — "Limitations: Command hooks communicate through stdout, stderr, and exit codes only. They cannot trigger `/` commands or tool calls."

### Rule 2: Pick the hook event by what you want to do — Pre to gate, Post to react, Session/Stop for boundaries

**Rule:** The 28 hook events Anthropic ships fall into a handful of usage shapes: `PreToolUse` to gate a tool call before it runs (the only event where you can `deny`/`ask` a tool); `PostToolUse` / `PostToolUseFailure` to react after a tool has already executed (cannot undo); `SessionStart` to inject context at session boot; `Stop` / `SubagentStop` to mark boundaries; `UserPromptSubmit` to inspect/block user input; `Notification` for "Claude needs you" alerts. Pick the event by intent, not by guess.
**Why:** Choosing the wrong event silently produces dead code — e.g., a `PostToolUse` hook with exit 2 cannot block (the tool already ran); a `PreToolUse` hook on `Stop` never fires.
**Grep:** `^\s*"(PreToolUse|PostToolUse|SessionStart|Stop|UserPromptSubmit|Notification|SubagentStop|PostToolUseFailure)":`
**Target:** `.claude/settings.json`
**Authority:** `https://docs.claude.com/en/docs/claude-code/hooks` — "Hook lifecycle" + "Exit code 2 behavior per event" table (lists which events are blockable).

### Rule 3: Configuration scope determines who the hook binds — choose project / user / local deliberately

**Rule:** Hooks live in one of four settings files, in descending precedence: Managed (organization policy) > `.claude/settings.local.json` (project-local, gitignored, per-machine overrides) > `.claude/settings.json` (project-wide, committed) > `~/.claude/settings.json` (user-wide, applies across all your projects). Pick the scope by ownership: team-wide convention → `.claude/settings.json`; personal preference (notification sounds, editor integration) → `~/.claude/settings.json`; per-machine experiment → `.claude/settings.local.json`.
**Why:** A team-wide rule placed in user scope binds only the one developer who configured it. A personal preference placed in project scope leaks per-developer config into the team repo.
**Grep:** `^\s*"hooks"\s*:`
**Target:** `.claude/settings.json`
**Authority:** `https://docs.claude.com/en/docs/claude-code/hooks` — "Hook locations" table (4 scopes with shareability matrix).

### Rule 4: Hook command contract — read JSON from stdin, write JSON to stdout, exit 0 succeeds, exit 2 blocks

**Rule:** Each command hook receives a JSON object on stdin with at least `session_id`, `cwd`, `hook_event_name`, plus event-specific fields like `tool_name` / `tool_input` for tool events. Exit code 0 means success and Claude Code parses stdout for JSON output fields (`continue`, `suppressOutput`, `hookSpecificOutput`, `additionalContext`). Exit code 2 means blocking error: stdout is ignored, stderr is fed back to Claude. Any other non-zero exit is non-blocking error. Use `"${CLAUDE_PROJECT_DIR}"` to reference scripts portably across worktrees, and always quote shell variables (`"$VAR"` not `$VAR`) per the docs' security best-practices section. Hook output is capped at 10,000 characters.
**Why:** Conflating exit 1 with "block" is the most common scripting bug — only exit 2 blocks (except `WorktreeCreate` where any non-zero aborts). Unquoted variables in shell hooks expose path-traversal and command-injection risk on filenames containing spaces or shell metacharacters.
**Authority:** `https://docs.claude.com/en/docs/claude-code/hooks` — "Common input fields", "Exit code output", "JSON output", "Security best practices" (the 10,000-char cap + `${CLAUDE_PROJECT_DIR}` guidance + always-quote-variables rule).

### Rule 5: PreToolUse decisions go in `hookSpecificOutput.permissionDecision` — allow / deny / ask / defer

**Rule:** A `PreToolUse` hook controls a tool call by exiting 0 and emitting JSON with `hookSpecificOutput.permissionDecision` set to one of `allow` (force-allow, skipping permission prompt), `deny` (block with `permissionDecisionReason` shown to Claude), `ask` (escalate to user prompt even if a deny rule would normally skip it), or `defer` (fall through to the normal permission flow). Hooks can tighten restrictions but not loosen past explicit deny rules. PreToolUse fires before any permission-mode check, so a `deny` decision blocks tools even in `bypassPermissions` mode — this is the supported way to enforce policy users cannot opt out of.
**Why:** Hard-blocking with exit 2 from a `PreToolUse` hook is coarser than the JSON `permissionDecision` shape: with JSON you can `ask` (escalate to user) instead of `deny` (silent block), which is the right answer for "legitimate trivial-lane edit might match my pattern by accident."
**Grep:** `"permissionDecision"\s*:\s*"(allow|deny|ask|defer)"`
**Target:** `.claude/settings.json`
**Authority:** `https://docs.claude.com/en/docs/claude-code/hooks` — "PreToolUse" event section + "Decision control" table + "Hooks and permission modes" section ("PreToolUse hooks fire before any permission-mode check ... lets you enforce policy that users cannot bypass").

### Rule 6: SessionStart `additionalContext` is the highest-leverage state-injection pattern — use it for branch / issue / config state

**Rule:** A `SessionStart` hook (matchers: `startup` / `resume` / `clear` / `compact`) can emit `hookSpecificOutput.additionalContext` (or print directly to stdout — for this event, plain stdout is also added as context). Use this to inject "current branch", "uncommitted changes", "active issue / PRD", "deployment target", "feature flags" — anything that changes per-session and that Claude should know at turn 1. For static content that never changes, prefer `CLAUDE.md` — it loads without running a script. SessionStart re-fires on `--resume` / `--continue` / `/resume`, so timestamps and live state stay fresh.
**Why:** Without a SessionStart context injection, every new session burns its first 2-3 turns reconstructing state via `git status` / `gh issue list` / `tail logs`. A 5-line SessionStart hook collapses that to one injected reminder block — the single highest-leverage hook pattern in the docs.
**Authority:** `https://docs.claude.com/en/docs/claude-code/hooks` — "SessionStart" event section (additionalContext / initialUserMessage / watchPaths fields) + "Add context for Claude" + "For instructions that never change, prefer CLAUDE.md."

### Rule 7: Git hook taxonomy — pre-commit ≠ commit-msg ≠ pre-push

**Rule:** Pick the right git hook by what input it receives and when it fires relative to `$EDITOR`. The 5 most-conflated types: `pre-commit` — no args; fires BEFORE `$EDITOR`; no commit-message access (use for branch-name / lint-staged / etc.). `prepare-commit-msg` — receives `$1=COMMIT_EDITMSG path` + `$2=source` BEFORE `$EDITOR` (use for pre-populating messages). `commit-msg` — receives `$1=COMMIT_EDITMSG path` AFTER `$EDITOR` closes (use for commit-message-content validation: conv-commits regex, etc.). `pre-push` — receives `$1=remote-name` + `$2=remote-url` + reads ref pairs on stdin (use for pre-push gating). `post-commit` — no args; fires AFTER commit succeeds (use for notification only — cannot block).
**Why:** Conflating hook types causes mis-targeted validation behavior; commit-message-content checks require `commit-msg` (or `prepare-commit-msg`), NOT `pre-commit`. Seed example: PRD-V round 1 BLOCK ([#187](https://github.com/vojtech-stas/project-claude/issues/187)) on `.githooks/pre-commit` trying to validate commit-message content.
**Grep:** `COMMIT_EDITMSG`
**Target:** `.githooks/*`
**Authority:** `https://git-scm.com/docs/githooks` — canonical git documentation enumerating each hook's name, argument signature, invocation timing, and exit-code semantics.

## Supplementary

No hook-focused video distillation exists under `docs/best-practices/` as of 2026-05-22 (`grep -l hook docs/best-practices/*.md` returns only the London keynote, which mentions hooks only adjacently). Per ADR-0022 D2, Tier-3 supplementary citations are optional; this section is intentionally empty. If/when a hook-focused video lands under `docs/best-practices/`, add a pointer here.

## How to apply to this project

Concrete checks against current project files (run these when authoring a new hook, when this skill is invoked for a hook audit, or when reviewing a PR that touches `.claude/settings.json`):

- **Rule 1 check (scope policy):** [ADR-0015](../../../decisions/0015-claude-code-hooks-adoption.md) D2 codifies the project's matching rule: hooks may log, validate by exit code, or notify via stderr — they MAY NOT auto-invoke skills / subagents (technically impossible per the docs.claude.com Limitations section) or bypass existing convention layers (e.g., ADR-0008 D3 inline-firing, ADR-0009 D2 mandatory capture). A new hook proposal that wants to "auto-fire `/audit-subagents`" is rejected at PR time by `reviewer` per ADR-0015 D2.
- **Rule 2 check (event choice):** the 5 hooks currently in `.claude/settings.json` are 4× `PostToolUse` (`Edit|MultiEdit|Write`, `Agent`, `Bash`) + 1× `Stop` — all pure-logging events per ADR-0015 D3 + [ADR-0016](../../../decisions/0016-workflow-event-log-jsonl.md) D3. (For the live current-state table of every hook actually wired right now, see [`topics/hooks`](hooks.md).) A new hook should pick its event by reading the Rule 2 mapping above; if "what does this hook actually need to do" doesn't match an event's matrix row, it's the wrong event.
- **Rule 3 check (scope):** the project uses `.claude/settings.json` (Project scope, committed) for every hook per ADR-0015 D1 — correct for team-wide policy. No `.claude/settings.local.json` is committed (correct — Local scope is gitignored). User-scope (`~/.claude/settings.json`) is per-developer and out-of-repo.
- **Rule 4 check (command contract):** every current hook command in `.claude/settings.json` follows the canonical pattern established by PR #135: `jq -r '.tool_input.<field>' </dev/stdin` to parse, `${CLAUDE_PROJECT_DIR}` for portable script paths, always-quoted shell variables, `mkdir -p` before append. New hooks must mirror this pattern; the `jq` dependency is a soft-required tool per ADR-0016 (degrades silently on missing-jq machines).
- **Rule 5 check (PreToolUse decisions):** no `PreToolUse` hooks currently exist in the project. A future PRD will add the first PreToolUse blocking hook (likely commit-message-format validation or similar) per ADR-0015 D6's amendment path; until then the project has zero hook-side blocking and relies on `.githooks/pre-commit` for server-side git-level enforcement.
- **Rule 6 check (SessionStart):** no `SessionStart` hook currently exists. The project's session-continuity story relies on `ADR-0006 D2` live-state reconstruction (`git log` + `gh issue list` + `tail .claude/logs/workflow-events.jsonl`). A `SessionStart` `additionalContext` injection (current branch + open slices + last workflow events) would be a high-value future addition; capture as a backlog candidate per CLAUDE.md rule #11 if you find yourself wanting it.
- **Rule 7 check (git hook taxonomy):** the project ships 2 git hooks under `.githooks/`, both correctly typed per Rule 7. `.githooks/pre-commit` enforces branch-name + main-block (no commit-message access required — correctly uses the no-arg `pre-commit` event). `.githooks/commit-msg` validates conv-commits subject + ≤72-char cap + Co-Authored-By trailer presence (correctly receives `$1=COMMIT_EDITMSG` AFTER `$EDITOR` per ADR-0023 D6).

## Common pitfalls

Anti-patterns drawn from the docs + project history:

- **Trying to use a hook to invoke `/audit-subagents` (or any skill).** Technically impossible — command hooks communicate only via stdin/stdout/stderr/exit-code; they cannot call `/`-commands or load skills. This is the canonical hook anti-pattern, called out explicitly in ADR-0015 D2 reality-check. The closest legitimate substitute is a `PostToolUse(Edit)` hook that LOGS "consider running /audit-subagents" so the user manually invokes — which is exactly the slice-1 hook pattern shipped per ADR-0015 D3.
- **Hooks-as-orchestration-replacement.** Trying to replace the project's ADR-0008 D3 inline-firing convention (agents call `/promote-to-backlog` inline after `gh issue create --label captured`) with a hook bypasses the agent-discipline layer. ADR-0015 D2 explicitly rejects this: hooks are additive enforcement, not replacement. Inline-firing stays the canonical mechanism for skill-invocation chains.
- **User-scope hook for project-wide policy.** A hook meant to bind every contributor must live in `.claude/settings.json` (Project scope, committed). Putting it in `~/.claude/settings.json` (User scope) binds only the one developer who configured it. Run `/hooks` and confirm scope before assuming a hook is shared.
- **PreToolUse hook that hard-blocks legitimate edits.** Using exit 2 from a `PreToolUse(Edit)` hook to enforce "no edits outside the current slice" will silently block legitimate trivial-lane (CLAUDE.md I3) edits or main-agent meta-output (rule #10) flows. Prefer `permissionDecision: "ask"` to escalate to user prompt instead of `"deny"` to hard-block, per Rule 5.
- **Exit code 1 = "blocks the tool".** Only exit code 2 blocks (except `WorktreeCreate`, where any non-zero aborts). Exit 1 is treated as non-blocking error: the tool runs, the transcript shows a warning, execution continues. If your hook means to enforce policy, `exit 2`.
- **Forward-reference reminder.** A future PRD will introduce PreToolUse blocking hooks (commit-message-format validation, branch-name validation, similar) per ADR-0015 D6's amendment path; until that PRD ships, no validation hooks are present in this project and `reviewer` + `.githooks/pre-commit` are the only enforcement layers below the agent-discipline conventions. Treat `asyncRewake` background-monitoring as a tertiary docs feature out of scope here — mention only if a use case forces it.

## Tool boundaries

The `/best-practice-hooks` skill that hosts this content has:

Allowed: `Read`, `Grep`, `Glob` — the skill is a reference text; it reads project files only to answer "is this rule honored here?" when asked. It does not edit anything.

Forbidden: `Edit`, `Write` (no project mutations from a best-practice reference); `Bash` (no shell execution from a doc skill — if a user wants to run the rule's Grep, they can copy it themselves); `Agent` (no recursive subagent invocation — this is a leaf reference skill); any `gh` / `git` operation (no GitHub mutations from a doc skill).

## References

- [ADR-0022](../../../decisions/0022-docs-first-kb-pattern.md) — D1 (4-section skill shape + Grep/Target audit-hook schema), D2 (Tier-1/2/3 source priority), D3 (`.claude/skills/best-practice-<topic>/` location convention), D5 (hand-curated curl-based ingest), D8 (PRD-A → PRDs B+C parallel DAG; this is PRD-C), D9 (existing video distillations preserved as Tier 3 supplementary).
- [ADR-0015](../../../decisions/0015-claude-code-hooks-adoption.md) — D1 (hooks live in `.claude/settings.json`), D2 (scope policy: logging/validation/notification ONLY; no skill auto-invocation), D3 (walking-skeleton PostToolUse(Edit) hook), D4 (`.claude/logs/` location, gitignored), D5 (bootstrap-mode forward-binding), D6 (future hook additions via new PRD / trivial-lane / within-existing-PRD).
- [ADR-0016](../../../decisions/0016-workflow-event-log-jsonl.md) — D1 (JSONL format), D2 (hook-based delivery only), D3 (3 event types: `agent_complete` / `bash_complete` / `session_stop`), D4 (`.claude/logs/workflow-events.jsonl` location).
- [ADR-0011](../../../decisions/0011-subagent-quality-framework.md) — D2 (mechanical/grep-only rubric pattern extended into ADR-0022 D1's Grep/Target schema), D5 (advisory-only single-Markdown-report precedent).
- [ADR-0001](../../../decisions/0001-foundational-design.md) D6 — canonical subagent frontmatter convention (sources Rule 1's project-side enforcement of the docs' "hooks are shell commands" constraint).
- [ADR-0031](../../../decisions/0031-knowledge-architecture-v2.md) D10 step 5 — the slice that moved this synthesis from skill body to KB topic.
- `https://docs.claude.com/en/docs/claude-code/hooks-guide` — tutorial guide; Rules 1, 2.
- `https://docs.claude.com/en/docs/claude-code/hooks` — full 28-event reference + JSON schema; Rules 1, 2, 3, 4, 5, 6.

## Edges

- **part_of:** [[entities/skills/best-practice-hooks]]
- **related_to:** [[topics/best-practices-workflow]]
- **related_to:** [[topics/best-practices-subagents]]
- **related_to:** [[topics/hooks]]
- **related_to:** [[entities/skills/audit-subagents]]
- **related_to:** [[entities/skills/distill-video]]
