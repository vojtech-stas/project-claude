# project-claude

A clone-as-template starter for AI-coded projects, replicating the workflow of a **senior engineer overseeing a small team of developers** — but with AI agents instead of humans. Built on 20-year-old software engineering practices (small slices, fast feedback, git-tracked changes, PR review, scope discipline) and heavy borrowing from [Matt Pocock's skills repo](https://github.com/mattpocock/skills).

> **New here? Start here →** Jump to the [5-Minute Quickstart](#5-minute-quickstart) for a literal first-use cycle. Skim the [Concepts cheat sheet](#concepts-cheat-sheet) for one-line definitions. Hit the [FAQ](#frequently-asked-questions) for common newcomer questions. For deep theory, scroll to *What's the idea*; for the architecture, see [CLAUDE.md](CLAUDE.md).

## What's the idea

You play **senior engineer**. AI agents play **the team**. The template ships an autonomous pipeline with **exactly two human-touch points**:

- **Start — `/grill-me`** — the agent interviews you about the idea until both of you share the same picture of what's being built.
- **End — `/qa-plan`** — after every slice of the PRD has merged, the agent produces a human-runnable acceptance checklist. You verify; you sign off.

Everything in between — PRD authoring, slice decomposition, implementation, review, merge — is autonomous, gated by adversarial AI critics rather than per-stage human approval.

The middle is glued together by one command: **`/ship`**. After `/grill-me`, you invoke `/ship` and the pipeline chains `to-prd → prd-critic → slicer → slicer-critic → implementer → reviewer → merge` per slice until the PRD is done. Stage 4 (implementation) is autonomous via the [`implementer`](.claude/agents/implementer.md) subagent — `/ship` auto-invokes it on each posted slice with DAG-aware parallel batching, no manual implementation trigger needed (per [ADR-0010](decisions/0010-implementer-subagent-auto-pipeline.md)). See [ADR-0003](decisions/0003-autonomous-pipeline-with-critics.md) D2 for the 5-stage pipeline and [ADR-0003](decisions/0003-autonomous-pipeline-with-critics.md) D4 for why there are no human gates in the middle.

**QA stage (Tier 1, ADR-0020 — runnable end-to-end via `/qa-plan`).** The terminal `/qa-plan` checkpoint is a writer/executor split: the writer (skill, main-agent context) LLM-extracts each PRD §2 acceptance criterion into a mechanical bash check or a `JUDGMENT` flag, persists the plan as a PRD comment for audit + re-runnability, then dispatches the [`qa-tester`](.claude/agents/qa-tester.md) generator subagent (tools: Read/Bash/Grep only) to execute the plan and return a per-criterion verdict table. Judgment rows and EXTRACT_FAILED rows are surfaced to you via `AskUserQuestion`; on all-PASS + all-judgment-ACCEPT the PRD auto-closes. Shipped through the autonomous pipeline as the QA writer/executor split per [ADR-0020](decisions/0020-qa-automation-writer-executor.md). Per [ADR-0020](decisions/0020-qa-automation-writer-executor.md) D9 + [ADR-0008](decisions/0008-workflow-autolog-bootstrap-and-naming.md) D7 the 6-critic-cap is honored — qa-tester is the 3rd generator (alongside `slicer` and `implementer`), not a 7th critic.

**Forward queue.** Future-PRD ideas live as `backlog`-labeled GitHub Issues + a "Backlog" column on the project board (per [ADR-0006](decisions/0006-backlog-and-session-continuity.md)). Browse with `gh issue list --label backlog`. Promotion to a PRD: `gh issue edit <N> --remove-label backlog --add-label prd` + `/grill-me #<N>`.

**Captured → backlog autopilot.** Per [ADR-0008](decisions/0008-workflow-autolog-bootstrap-and-naming.md), any agent that surfaces a deferred-work idea writes it as a `captured`-labeled issue and invokes the [`/promote-to-backlog`](.claude/skills/promote-to-backlog/SKILL.md) skill inline. The [`backlog-critic`](.claude/agents/backlog-critic.md) subagent gates the promotion against a 4-criterion rubric (actionable / scoped / not duplicate / clear); on APPROVE the autopilot swaps labels `captured` → `backlog`, on BLOCK the item stays in the captured tier as a graveyard for lazy human review (default-conservative per [ADR-0008](decisions/0008-workflow-autolog-bootstrap-and-naming.md) D4).

**Why two tiers?** `captured` is a low-bar safety net — agents capture deferred work indiscriminately (CLAUDE.md rule #11) so nothing gets lost; the autopilot's `backlog-critic` filters them down to the curated `backlog` queue you actually pick PRDs from. BLOCKed captures stay in the captured-tier graveyard for lazy human review — three options per item: cull (close), rescue (manually relabel `captured` → `backlog`), or restructure-and-recapture.

**Session continuity.** New Claude Code sessions reconstruct state from live state (`git log`, `gh issue list`, `gh pr list`, project board) — no formal handoff document. See the "Session continuity" section in [CLAUDE.md](CLAUDE.md) for the canonical procedure.

## 5-Minute Quickstart

A literal walkthrough of the first full feature cycle. Pick something tiny — e.g., a `/say-hello` skill that prints a greeting. (Real PRDs are bigger; we use `/say-hello` here purely to make the example fit in 5 minutes.)

**1. Clone + bootstrap (one-time, ~30 seconds):**

```bash
git clone https://github.com/vojtech-stas/project-claude my-new-project
cd my-new-project
./bootstrap.sh         # creates labels, installs git hooks, applies branch protection
```

**2. Open the repo in Claude Code.** `CLAUDE.md` auto-loads; the agents are oriented.

**3. Grill the idea (~2 minutes).** Run `/grill-me I want a /say-hello skill that prints a friendly greeting`. The agent interviews you one question at a time:

```
Agent:  1. Should /say-hello take an optional name argument, or always greet "world"?
        Recommendation: 1B (optional argument) — slightly more useful, same LoC.
        1A. always "Hello, world!"     pros: dead simple; cons: not personalizable
        1B. optional name argument     pros: useful; cons: trivially more code
        1C. read name from git config  pros: zero-arg + personal; cons: edge cases
You:    1B
Agent:  2. Should output go to stdout, or use AskUserQuestion?
        ...
```

After 3-5 questions the agent confirms the settled design and returns.

**4. Ship it (autonomous, ~2 minutes wall-clock for a trivial example).** Run `/ship`. The orchestrator chains: `to-prd` → `prd-critic` (≤3 APPROVE/BLOCK rounds) → `slicer` → `slicer-critic` → posts the PRD + slice issues → `implementer` writes the code per slice → `reviewer` audits the PR → auto-merges on APPROVE. You watch; you don't touch.

**5. Verify (~30 seconds).** When the last slice merges, run `/qa-plan <PRD-number>`. The `qa-tester` subagent walks each acceptance criterion mechanically; subjective ones surface via `AskUserQuestion`. On all-PASS the PRD auto-closes.

That's the full loop. Two human commands (`/grill-me`, `/qa-plan`), one orchestration command (`/ship`), and the rest is autonomous.

## Concepts cheat sheet

One-line definitions of the load-bearing terms. For the full canonical glossary (with authority citations), see [CLAUDE.md `## Glossary`](CLAUDE.md#glossary).

- **PRD** — feature-sized GitHub issue (label `prd`); top of the PRD → Slice → PR hierarchy.
- **slice** — INVEST-shaped sub-issue of a PRD (label `slice`); one PR; ≤300 LoC diff.
- **skill** — user-invocable command at `.claude/skills/<name>/SKILL.md` (e.g., `/ship`).
- **subagent** — specialist at `.claude/agents/<name>.md` with isolated context + restricted tools.
- **critic** — adversarial subagent judging a stage's output with APPROVE/BLOCK (≤3 rounds).
- **generator** — subagent producing output (decompositions, code, test plans); paired with a critic.
- **autopilot** — inline-firing mechanism (e.g., `/promote-to-backlog` after a captured-label issue).
- **trivial-lane** — fast path (I3) for PRs ≤10 LoC; branch `hotfix/<N>-...`, label `trivial`.

## Frequently asked questions

### Do I have to use `/grill-me`?

Recommended for any new feature. Skippable for the trivial lane (I3 — PRs ≤10 LoC, no behavior change, branch `hotfix/<N>-...`). The `/to-prd` skill also accepts a clear pre-written spec if you'd rather draft offline. The autopilot enforces no hard requirement today, though a future PRD may make `/grill-me` mechanically required for new features.

### Why is Claude asking permission to edit every file?

The `PreToolUse(Edit|MultiEdit|Write)` hook ([ADR-0023](decisions/0023-validation-and-notification-hooks-extension.md) D3) emits `permissionDecision: "ask"` when the **main agent** (not a subagent) writes a tracked file. This is the mechanical enforcement of CLAUDE.md rule #10 — main-agent meta-output discipline. Subagent edits (e.g., `implementer` shipping a slice) skip the prompt entirely. If you see prompts on every edit including untracked / gitignored files, you may be hitting captured issue #222 — make sure `jq` is installed and on your PATH.

### What if I want to skip critics?

You can't via the pipeline. The joint-APPROVE gate ([ADR-0004](decisions/0004-bypass-prevention.md) D1) is non-negotiable, and `reviewer` is the sole gate per PR ([ADR-0002](decisions/0002-autonomous-merge-policy.md)). You CAN, however, escalate a round-3 BLOCK to a `needs-human` label and apply your own judgment in a manual PR — that's the designed escape valve.

### How do I add a new subagent?

Author `.claude/agents/<name>.md` per [ADR-0001](decisions/0001-foundational-design.md) D6; declare tool boundaries in the frontmatter; write the body per the standards in [`/best-practice-subagents`](.claude/skills/best-practice-subagents/SKILL.md). If your new subagent is a critic, honor the 6-critic-cap meta-rule ([ADR-0008](decisions/0008-workflow-autolog-bootstrap-and-naming.md) D7) — a new ADR must justify why an existing critic's rubric can't absorb the concern.

### Why so many ADRs?

Each ADR is one architectural decision frozen at its moment per [`decisions/README.md`](decisions/README.md) "What an ADR is". The count reflects the template's walking-skeleton evolution — superseded decisions live on for audit + history, never edited in place. If you fork the template and decide differently for your project, you write new ADRs; the originals remain as the historical record.

### What does it mean if I see a `needs-human` label?

The reviewer applies `needs-human` on round-3 BLOCK ([ADR-0003](decisions/0003-autonomous-pipeline-with-critics.md) I5) — three rounds of generator/critic disagreement is the autonomy ceiling. A human needs to decide. Find them at session start with `gh pr list --label needs-human` and `gh issue list --label needs-human`. The reviewer also posts a summary to the parent PRD issue so you don't have to guess what's stuck.

## Pipeline diagram

The whole autonomous composition at a glance: the human enters at **`/grill-me`** and exits at **`/qa-plan`**, with everything in between — PRD authoring, slice decomposition, implementation, review, merge — chained by **`/ship`** and gated by adversarial critic loops (≤3 rounds each). The joint `prd-critic` + `adr-critic` gate, the `reviewer` auto-merge red-gate, and the `needs-human` forward-block paths are all shown; side workflows (`/audit-subagents`, `/glossary-add`, captured→backlog autopilot) live in their own subgraph or fire transparently around the main pipeline.

{{GENERATED:pipeline-diagram}}

### Legend

| Color | Class | Node type | Examples in the diagram |
|---|---|---|---|
| 🟦 Blue | `human` | Human checkpoint | `User` (input at `/grill-me`, acceptance at `/qa-plan`) |
| 🟩 Teal | `skill` | User-invocable skill | `/grill-me`, `/ship`, `/to-prd`, `/to-issues`, `/qa-plan`, `/audit-subagents`, `/promote-to-backlog`, `/glossary-add` |
| 🟢 Green | `gen` | Generator subagent | `slicer` (N=3 or N=1 decompositions per ADR-0013), `implementer` (slice → PR) |
| 🟧 Orange | `critic` | Adversarial critic (≤3-round loop) | `prd-critic`, `adr-critic`, `slicer-critic`, `glossary-critic`, `backlog-critic` |
| 🟥 Red | `reviewer` | Auto-merge gate (per [ADR-0002](decisions/0002-autonomous-merge-policy.md)) | `reviewer` — the only critic that auto-merges on APPROVE |
| ⬜ Gray | `artifact` | GitHub artifact | PRD issue, slice issues, PR, merged commit, `needs-human` / `backlog` labels |

## Hierarchy — PRD → Slice → PR

Per [ADR-0003](decisions/0003-autonomous-pipeline-with-critics.md) D1, the unit-of-delivery hierarchy is exactly three tiers:

- **PRD** — GitHub Issue (label `prd`). One feature per PRD.
- **Slice** — GitHub sub-issue under the PRD (label `slice`). One INVEST-shaped vertical, fits in one PR.
- **PR** — one merged change, closes one slice via `Closes #<slice-issue>` in the PR body.

No `feature` label, no `slice-N-foo` branch names. Branches use Conventional Commits prefixes — `<type>/<issue-number>-<kebab-summary>`. See [CLAUDE.md](CLAUDE.md) "Hierarchy" and "Operational git workflow" for the full operational logic.

## Adversarial critics

Per [ADR-0003](decisions/0003-autonomous-pipeline-with-critics.md) D2, every generation stage in the pipeline is paired with an adversarial critic running a ≤3-round APPROVE/BLOCK loop. The project honors the **6-critic-cap meta-rule** per [ADR-0008](decisions/0008-workflow-autolog-bootstrap-and-naming.md) D7 — promoting a new critic requires a new ADR explicitly justifying why an existing critic's rubric cannot absorb the concern. Today's critics:

- **`prd-critic`** — gates PRD drafts.
- **`adr-critic`** — gates ADR drafts. Per [ADR-0004](decisions/0004-bypass-prevention.md) D1, when a macro-ADR is drafted alongside a PRD, `prd-critic` and `adr-critic` run as a **joint-APPROVE gate** — both must APPROVE before `/to-prd` posts.
- **`slicer-critic`** — picks best of N slicer decompositions (typically 3; may be 1 for degenerate cases per ADR-0013), then iterates.
- **`reviewer`** — gates every PR; auto-merges on APPROVE, returns to implementer on BLOCK, escalates with `needs-human` on round-3 BLOCK.
- **`glossary-critic`** — gates additions to the consolidated CLAUDE.md glossary (see "Shared vocabulary" below). Added per [ADR-0007](decisions/0007-vocabulary-glossary-and-grill-me-extension.md) D5; rubric updated to 5 rules per [ADR-0012](decisions/0012-glossary-consolidation-single-tier.md) D4.
- **`backlog-critic`** — gates `captured` → `backlog` label promotions against a 4-criterion rubric (actionable / scoped / not duplicate / clear); fires once inline via the `/promote-to-backlog` autopilot, default-conservative on BLOCK (the item stays in the captured tier as a graveyard for lazy human review). Per [ADR-0008](decisions/0008-workflow-autolog-bootstrap-and-naming.md) D4.

The loop convention (generator proposes → critic challenges against explicit rubric → generator revises → ≤3 rounds → APPROVE or escalate) is the canonical pattern from [ADR-0003](decisions/0003-autonomous-pipeline-with-critics.md) D2.

## Workflow enforcement

Per [ADR-0004](decisions/0004-bypass-prevention.md) D3, three independent failure-domain defenses prevent the pipeline from being bypassed:

1. **Pre-commit hook** — [`.githooks/pre-commit`](.githooks/pre-commit) checks branch-name regex and refuses commits to `main`. Install with `.githooks/install.sh` (idempotent `git config core.hooksPath .githooks`).
2. **Branch protection R1 + R2** — live on `main`: no direct push (R1), require pull request (R2). R3 (required approving reviews) and R4 (required CI status checks) are deferred to a future PRD that bundles bot identity + GitHub Actions.
3. **Reviewer rule R-CLOSES** — PRs without `Closes #<slice-issue>` referencing a valid `slice`-labeled issue are BLOCKed at review time.

The workflow is no longer "discipline-only convention" — these three layers enforce it mechanically.

Per [ADR-0018](decisions/0018-boy-scout-reviewer-rule.md), a fourth (discretionary, defense-in-depth) layer rides on the reviewer's existing gate: the **R-BOY-SCOUT** rule fires when a PR touches audit-relevant files (`.claude/agents/*.md`, `.claude/skills/*/SKILL.md`, `decisions/*.md`, `CLAUDE.md`, `README.md`) and applies the relevant `/audit-subagents` + `/audit-meta` rubric checks inline against the touched files only. Default-conservative-toward-Recommendation; only zero-false-positive findings with mechanical fixes BLOCK.

The pipeline is complemented at the Claude Code session level by **hooks** ([`.claude/settings.json`](.claude/settings.json)) configured per [ADR-0015](decisions/0015-claude-code-hooks-adoption.md) for logging / validation / notification (no skill auto-invocation; that requires session interaction). Current count: **9 outer hook entries** (1 SessionStart + 2 UserPromptSubmit + 2 PreToolUse + 3 PostToolUse + 1 Stop) → **10 inner hook commands** (Stop has 2 commands) → **6 scripts** (`session-start.sh`, `user-prompt-submit.sh`, `user-prompt-submit-topic-nudge.sh`, `pre-tool-edit.sh`, `pre-tool-bash.sh`, `stop-reviewer-gate.sh` per [ADR-0029](decisions/0029-stop-reviewer-signoff-gate.md)) + **4 inline jq one-liners** (Edit/MultiEdit/Write logger, Agent logger, Bash logger, Stop JSONL logger).

**Layer 4 — Claude Code session hooks** (per [ADR-0023](decisions/0023-validation-and-notification-hooks-extension.md), extending [ADR-0015](decisions/0015-claude-code-hooks-adoption.md) D6; 6 hooks across the full ADR-0015 → ADR-0023 → ADR-0028 → ADR-0029 → ADR-0030 wave):

1. **SessionStart state injection** — [`.claude/hooks/session-start.sh`](.claude/hooks/session-start.sh) emits `additionalContext` with branch + divergence vs `origin/main` + recent commits + open slice/PR/captured counts; mitigates the recurring stale-worktree false-alarm (#173) at the moment of session start.
2. **PreToolUse rule-#10 escalation** — `PreToolUse(Edit|MultiEdit|Write)` emits `permissionDecision: "ask"` when the main agent (not a subagent) writes a tracked file; preserves trivial-lane I3 ergonomics over hard-deny.
3. **PreToolUse dangerous-git deny** — `PreToolUse(Bash)` emits `permissionDecision: "deny"` on `git push ... origin main` (any flavor), mechanically enforcing rule #4.
4. **UserPromptSubmit grill-suggestion** — feature-request-shaped prompts get a non-blocking nudge toward `/grill-me` before `/ship` if the prompt does not already invoke a pipeline command.
5. **UserPromptSubmit topic-nudge** — per [ADR-0026](decisions/0026-knowledge-architecture-truth-docs.md) D4, prompts mentioning a covered topic (slicing, output-shape, hooks, etc.) trigger an `additionalContext` nudge; the hook script `user-prompt-submit-topic-nudge.sh` fires inline to provide current-state context.
6. **Stop reviewer-signoff gate** — [ADR-0029](decisions/0029-stop-reviewer-signoff-gate.md) `stop-reviewer-gate.sh`: blocks session-stop if any in-flight PR lacks a reviewer `APPROVE` comment; `STOP_GATE_BYPASS=1` env-var override.

**Recent hook wave (ADR-0028–ADR-0030):**

- [ADR-0028](decisions/0028-pretooluse-spec-gate.md) — **PreToolUse spec-existence gate** (spec-gate): artifact-gated enforcement of rule #10; BLOCKs tracked-file edits when no in-flight PRD/slice issue + matching branch exist; extends [ADR-0023](decisions/0023-validation-and-notification-hooks-extension.md) D3 with a deny-layer before the existing ask fallback; trivial-lane (`hotfix/`) carveout preserved.
- [ADR-0029](decisions/0029-stop-reviewer-signoff-gate.md) — **Stop reviewer-signoff gate** (`stop-reviewer-gate.sh`): the 6th `.claude/hooks/` script; blocks session-stop without reviewer `APPROVE`; `STOP_GATE_BYPASS=1` override.
- [ADR-0030](decisions/0030-windows-gitbash-hardening.md) — **Windows Git Bash hardening**: `bootstrap.sh` adds idempotent jq + Playwright install; `pre-tool-edit.sh` allowlist restructured for `/` and `\` portability.

**Workflow event log.** Per [ADR-0016](decisions/0016-workflow-event-log-jsonl.md), three additional hooks (`PostToolUse(Agent)`, `PostToolUse(Bash)`, `Stop`) append JSONL events to [`.claude/logs/workflow-events.jsonl`](.claude/logs/) for run-time observability — which subagents fired, which bash commands ran, where session boundaries fell. Greppable from any session (`grep '"event":"agent_complete"' .claude/logs/workflow-events.jsonl`) and read by future audit-meta tooling.

## Output-shape standard

The critics and the output-emitting skills (`slicer`, `qa-plan`, `ship`) conform to a canonical output shape. The canonical verdict template and the CRITIC / GENERATOR trailer schemas are defined in [ADR-0005](decisions/0005-output-shape-and-slicing-methodology.md) D1 and restated in the subagent/skill prompts themselves (DRY per [CLAUDE.md](CLAUDE.md) rule #9).

## Use it

```bash
git clone https://github.com/vojtech-stas/project-claude my-new-project
cd my-new-project
./bootstrap.sh         # one-time: labels, git hooks, branch protection (idempotent)
# open in Claude Code — CLAUDE.md auto-loads, the agents are oriented
```

[`bootstrap.sh`](bootstrap.sh) is the canonical fresh-clone setup per [ADR-0008](decisions/0008-workflow-autolog-bootstrap-and-naming.md) D6: it creates the 6 repo labels (`prd`, `slice`, `backlog`, `captured`, `trivial`, `needs-human`), installs the pre-commit hook via `core.hooksPath`, detects the GitHub Project v2 board, and applies branch protection R1+R2 to `main`. Every step is idempotent (safe to re-run) and best-effort (single-step failures warn-and-continue).

Then: `/grill-me` to start a new feature, `/ship` to hand off to the autonomous pipeline, `/qa-plan` to verify when the last slice merges.

## What's inside

- **[CLAUDE.md](CLAUDE.md)** — auto-loaded operating system; canonical home for cross-cutting rules + Map + Glossary INDEX.
- **[`.claude/skills/`](.claude/skills/)** and **[`.claude/agents/`](.claude/agents/)** — pipeline skills and subagents. See the Map table in [CLAUDE.md](CLAUDE.md) for what lives where.
- **[`decisions/`](decisions/)** — Architecture Decision Records. See [`decisions/README.md`](decisions/README.md) for the index, conventions, and the strict immutability rule.

All operational content lives in skills + subagents + CLAUDE.md + ADRs; no separate KB layer per [ADR-0032](decisions/0032-workflow-only-architecture.md).

- **[`bootstrap.sh`](bootstrap.sh)** — fresh-clone setup script (labels, git hooks, branch protection); see [ADR-0008](decisions/0008-workflow-autolog-bootstrap-and-naming.md) D6.
- **[`.githooks/`](.githooks/)** — workflow-enforcement pre-commit hook.
- This README.

### Dashboard

Dashboard auto-starts on session start via the `dashboard-autostart.sh` SessionStart hook (per [ADR-0033](decisions/0033-tooling-spawn-hook-scope.md)). Visit `http://localhost:8765` — **Architecture**, **Live event stream**, and **Health** tabs. Architecture shows the pipeline diagram and auto-discovered component graph (skills, agents, hooks, ADRs) with click-to-view file content. Live streams real-time events from `.claude/logs/workflow-events.jsonl` with filter chips (Critics / Generators / Skills / Hooks / Bash) and click-to-expand detail. Health shows pass/fail grids for DOCS-1..DOCS-10 and AS-* checks. Python stdlib only — no `pip install` needed. Manual start: `python dashboard/server.py`. See [`dashboard/README.md`](dashboard/README.md) for configuration and cross-platform notes.

## Component map

{{GENERATED:component-map}}

## Subagent-quality maintenance

Per [ADR-0011](decisions/0011-subagent-quality-framework.md), subagent prompts drift silently between slices (the 2026-05-19 audit demonstrated: 5 subagent files unchanged for multiple PRDs still instructed `--label backlog` instead of `--label captured`, bypassing the autopilot). The **`/audit-subagents`** skill ([`.claude/skills/audit-subagents/SKILL.md`](.claude/skills/audit-subagents/SKILL.md)) is the mechanical drift-detector: no-args invocation globs `.claude/agents/*.md`, applies a 10-check `scope`-tagged grep rubric (frontmatter, tool boundaries, references, surfacing convention, mandatory-reading-order, default-BLOCK clause, adversarial mindset, CRITIC trailer, 5-section verdict, GENERATOR trailer), and emits a single Markdown PASS/FAIL report. The skill is a GENERATOR per ADR-0005 D1c — advisory only, no auto-capture, no PR, no critic gate. Honors the [ADR-0008](decisions/0008-workflow-autolog-bootstrap-and-naming.md) D7 6-critic-cap (skill ownership, not a 7th critic). Invoke periodically or after merging a convention-changing ADR.

Per [ADR-0017](decisions/0017-audit-meta-consolidation.md), the sibling **`/audit-meta`** skill ([`.claude/skills/audit-meta/SKILL.md`](.claude/skills/audit-meta/SKILL.md)) covers the adjacent meta-quality concerns: codebase **structure** (file-counts, file-sizes, depth, naming conventions) and **documentation currency** (dangling refs, supersession notes, concrete drift detectors). Subcommand architecture: `/audit-meta` (no-args = both), `/audit-meta --structure`, `/audit-meta --docs`. Same advisory-only contract.

## Shared vocabulary

Per [ADR-0007](decisions/0007-vocabulary-glossary-and-grill-me-extension.md) (consolidated to single-tier per [ADR-0012](decisions/0012-glossary-consolidation-single-tier.md) D1), the project anchors load-bearing terms (e.g., *slice*, *critic*, *trivial*, *PRD*) in a **single-tier glossary** so agents and humans share the same definitions:

- **`## Glossary` in [CLAUDE.md](CLAUDE.md)** — auto-loaded by Claude Code on every session. Soft cap ~35 entries per [ADR-0012](decisions/0012-glossary-consolidation-single-tier.md) D5.

To add a term, run **`/glossary-add`** — it interviews you for the entry shape (definition, scope category, authority) and gates the addition through the `glossary-critic` subagent's 5-rule rubric (including ADR-0012 D2's ≥3-citations-across-≥2-directories inclusion threshold) before opening a trivial-lane PR.

## Status

Walking-skeleton phase. The pipeline is being built incrementally **on the project itself** — dogfooding from day one. The autonomous loop now ships PRDs end-to-end with all five stages live: `/grill-me` → `to-prd`+critics → `to-issues`+slicer-critic → `implementer`+`reviewer` (per slice, DAG-batched) → `/qa-plan` at acceptance. All operational content lives in skills + subagents + CLAUDE.md + ADRs per [ADR-0032](decisions/0032-workflow-only-architecture.md).

{{GENERATED:counts}}

## License

MIT — use it, fork it, ship it. A shoutout is appreciated.

## Credits

Inspired by [Matt Pocock's skills repo](https://github.com/mattpocock/skills) and the senior-engineer-overseen-agents workflow pattern.
