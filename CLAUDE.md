# project-claude — agent rules

This file is auto-loaded by Claude Code on every session in this repo. It contains the rules of the road for AI agents working here, plus a map of where things live. Read it first; refer back to it when unsure.

---

## Cross-cutting rules (apply to every action you take)

1. **YAGNI — rule #1.** Never add code outside the current slice's scope. Reviewer's first job is to enforce this. If you feel the urge to add something "while you're here", STOP and ask the user.
2. **Walking-skeleton mindset.** Smallest end-to-end version first; iterate on the weakest stage. Never build a primitive perfectly before the whole pipeline runs.
3. **Build primitives first, orchestrate last.** Do not write an orchestrator before the things it orchestrates exist and have been dogfooded.
4. **Never push directly to `main`.** Every change ships through a feature branch + PR. Branch protection (when configured) enforces this; meanwhile it's a discipline rule.
5. **Conventional Commits, tightened.** Every commit message follows `<type>(<optional scope>): <subject>`. Types: `feat`, `fix`, `docs`, `chore`, `refactor`, `test`, `perf`, `style`, `build`, `ci`. Additional hard rules:
   - **Lowercase subject** after the colon (`feat: add ship skill`, not `feat: Add Ship Skill`).
   - **≤72 character hard cap** on the subject line.
   - **`Closes #<slice-issue>`** belongs in the PR body, not the commit subject (reviewer enforces).
   - **`Co-authored-by:` trailer** on every agent-authored commit.
   - Body (after blank line) explains WHY, not what.
6. **`git log` is the changelog.** Don't create a separate CHANGELOG file. Good commit messages do the job.
7. **Practices are colocated.** Skills/subagents embody their own practice in their own body. No separate `docs/practices/` folder. Cross-cutting rules (this list) live HERE.
8. **One thing at a time.** One in-progress todo. One in-flight PR per slice.
9. **DRY for docs.** Don't duplicate info. Link/point to where the canonical version lives.

---

## Hierarchy — PRD → Slice → PR (3-tier)

Per [ADR-0003](decisions/0003-autonomous-pipeline-with-critics.md) D1, the unit-of-delivery hierarchy is exactly three tiers:

- **PRD** — GitHub Issue, label `prd`. One feature-sized deliverable per PRD. Multi-feature PRDs are a smell.
- **Slice** — GitHub sub-issue under the PRD (linked via the native sub-issue mechanism), label `slice`. One INVEST-shaped vertical, fits in one PR.
- **PR** — one merged change, closes exactly one slice via `Closes #<slice-issue>` in the PR body.

**Labels:**
- Use `prd` and `slice` exclusively for hierarchy. **There is no `feature` label** — the PRD plays that role.
- `trivial` for the trivial lane (see I3 below).
- `needs-human` is applied by the reviewer on round-3 BLOCK escalation (see I5 below).

**Milestones** are reserved for **Releases** (groups of merged PRDs). Not in use yet — left empty until the first release ships.

---

## Workflow improvements I1–I5

These are load-bearing conventions that supplement the cross-cutting rules. Per PRD #3 §4 and [ADR-0003](decisions/0003-autonomous-pipeline-with-critics.md).

- **I1 — Skills know the hierarchy.** `/to-prd` and `/to-issues` produce/consume the 3-tier hierarchy and the `prd`/`slice` labels (delivered by PRD #3 slices 2 and 3).
- **I2 — Slice-grabbing protocol.** The first agent to run `gh issue edit <slice> --add-assignee @me` owns the slice. The reviewer enforces "one assignee per open slice" — if a second agent grabs an already-assigned slice, reviewer BLOCKs the resulting PR.
- **I3 — Trivial lane.** PRs ≤10 LoC of runtime-artifact diff with no behavior change MAY skip PRD/slice ceremony. Branch: `hotfix/<short-summary>`. Add the `trivial` label to the PR; the reviewer fast-paths it.
- **I4 — Slice size cap & staleness.** Slice PRs cap at **≤300 LoC of runtime-artifact diff**. The canonical definition of "runtime artifact" lives in [`.claude/agents/reviewer.md`](.claude/agents/reviewer.md) (rule R-LOC) — do not restate it here. A slice issue open >7 days is marked stale by the reviewer.
- **I5 — Escalation surface.** On round-3 BLOCK, the reviewer applies the `needs-human` label to the PR AND posts a comment on the parent PRD issue summarizing the stuck slice. Humans run `gh pr list --label needs-human` at session start to find what's waiting on them.

---

## Map — where things live

| Looking for… | Find it at | Lookup command |
|---|---|---|
| Pipeline skills | `.claude/skills/<name>/SKILL.md` | `ls .claude/skills/` |
| `/ship` orchestrator | `.claude/skills/ship/SKILL.md` | `cat .claude/skills/ship/SKILL.md` |
| Subagents (reviewer, slicer, slicer-critic, prd-critic) | `.claude/agents/<name>.md` | `ls .claude/agents/` |
| Settings, permissions, hooks | `.claude/settings.json` | `cat .claude/settings.json` (none yet) |
| Pre-commit hooks (workflow enforcement) | `.githooks/pre-commit`, `.githooks/install.sh` | `ls .githooks/` |
| Decisions (ADRs) | `decisions/NNNN-<slug>.md` | `ls decisions/` |
| PRDs (future repo-local) | `docs/prds/NNNN-<slug>.md` | `ls docs/prds/` (created when first PRD lands there; current PRDs live on GitHub Issues per ADR-0003 D1) |
| Current work in flight | GitHub Issues + branches | `gh issue list` ; `git branch` |
| Recent activity | git history | `git log --oneline -20` |

---

## Operational git workflow

Follow this EVERY time. This is the operational logic — not just the principle.

### Starting a slice

```bash
git checkout main
git pull --ff-only origin main          # always start from latest main
git checkout -b <type>/<issue-number>-<kebab-summary>
gh issue edit <issue-number> --add-assignee @me   # claim the slice (I2)
```

**Branch naming:** `<type>/<issue-number>-<kebab-summary>` — where `<type>` is from the Conventional Commits set (`feat`, `fix`, `docs`, `chore`, `refactor`, `test`, `perf`, `style`, `build`, `ci`) plus `hotfix/` for the trivial lane (I3). Examples:
- `feat/4-ship-orchestrator-skeleton`
- `feat/7-reviewer-enforcement-additions`
- `docs/8-claude-md-conventions-rollup`
- `hotfix/fix-typo-in-readme`

The `slice-N-<name>` pattern from earlier slices is retired; GitHub issue numbers replace the slice number.

### Working within a slice

- Commit at meaningful checkpoints, not just at the end. Each commit = one coherent step.
- Apply rule #5 (Conventional Commits, tightened): lowercase subject, ≤72 char cap, `Co-authored-by:` trailer for agent commits.
- Message body (after blank line) explains WHY. Bullet points OK.
- If the slice grows beyond its planned scope → **STOP** and discuss with the user. Don't sneak extras in.

### Finishing a slice

```bash
git push -u origin <branch>
gh pr create --title "<conv-commits-style title>" --body "<see template below>"
```

**PR body MUST include:**
- **`Closes #<slice-issue>`** — links the PR to its slice (reviewer enforces).
- **Scope** — what's in.
- **Out-of-scope** — what's deliberately NOT in this slice.
- **Verification** — concrete steps to confirm it works.
- **ADR reference** — link to any new ADR if this slice made a design decision.

### Reviewing

Per [ADR-0002](decisions/0002-autonomous-merge-policy.md) (autonomous merge at PR level) and [ADR-0003](decisions/0003-autonomous-pipeline-with-critics.md) D4 (no human gates between pipeline stages), the `reviewer` subagent is the **sole gate per PR**. There are no per-stage human checkpoints in the standard flow — the human enters at `/grill-me` (input) and `/qa-plan` (acceptance), nothing in between.

The reviewer:
- Reads PR body + diff + CLAUDE.md + ADRs + linked slice issue.
- Posts a structured verdict comment via `gh pr comment`.
- **APPROVE** → auto-merges with `gh pr merge --squash --delete-branch`. No human action.
- **BLOCK** → returns the PR to the implementer for fixes. On round-3 BLOCK, applies the `needs-human` label and posts to the parent PRD (I5).

**Bootstrap exception (PRD #3 only):** the slices of PRD #3 ran with per-stage human checkpoints to validate the pipeline before fully enabling it. That exception ends with PRD #3's merge. From PRD #4 onward, reviewer is the sole gate per PR; no human checkpoints between stages.

### Merging

- `reviewer` subagent merges with `gh pr merge --squash --delete-branch` on APPROVE only (per ADR-0002). Never on BLOCK.
- Merge style: **squash-and-merge** always — one commit per slice on `main`, clean history.
- After merge (`--delete-branch` auto-deletes the remote branch):
  ```bash
  git checkout main
  git pull --ff-only origin main
  ```

### What NOT to do

- ❌ `git push --force` to a shared branch (use `--force-with-lease` if rewriting a feature branch is truly necessary)
- ❌ Commits on `main` directly
- ❌ Long-running branches (>1 week without merge) — split into smaller slices instead; reviewer marks stale per I4
- ❌ Bundle multiple unrelated changes in one commit
- ❌ Vague messages: `fix stuff`, `update`, `wip`, `final`

---

## Slicing logic — what makes a good slice

A good slice is:

- **Vertical** — ships end-to-end value, not a horizontal layer
- **Small** — completable in roughly one work session; ≤300 LoC runtime-artifact diff (I4)
- **Self-contained** — has its own PR, and its own ADR if it makes a real design decision
- **Reversible** — can be `git revert`-ed without breaking other slices
- **Explicitly out-of-scope-bounded** — the PR body lists what is NOT in this slice (to prevent drift)

If a planned slice feels too big → split it. If it's a one-liner (typo) → use the trivial lane (I3) and skip the ceremony.

---

## Pipeline operational logic

The HOW for each pipeline stage. Per [ADR-0003](decisions/0003-autonomous-pipeline-with-critics.md) D2, every generation stage is paired with an adversarial critic.

### How to grill (idea capture) — ✓ available
See [`.claude/skills/grill-me/SKILL.md`](.claude/skills/grill-me/SKILL.md). Invoked via `/grill-me` or natural-language match. Interviews user one question at a time, recommends an answer for each, walks the decision tree.

### How to ship a PRD end-to-end — ✓ available
See [`.claude/skills/ship/SKILL.md`](.claude/skills/ship/SKILL.md). Invoked via `/ship` after `/grill-me`. The orchestrator chains `to-prd → prd-critic → slicer → slicer-critic → gh issue create` for PRD and sub-issues. Single human command per feature after the grill session.

### How to write a PRD — ✓ available
See [`.claude/skills/to-prd/SKILL.md`](.claude/skills/to-prd/SKILL.md) — **canonical home of the 6-section PRD template** (Problem / Goal / Non-goals / Appetite / Solution sketch / Rabbit-holes & Open questions). The skill invokes [`.claude/agents/prd-critic.md`](.claude/agents/prd-critic.md) in a ≤3-round APPROVE/BLOCK loop before posting, and drafts any warranted macro-ADRs alongside the PRD per ADR-0003 D8. Normally invoked indirectly via `/ship`.

### How to create slices/issues from a PRD — ✓ available
See [`.claude/skills/to-issues/SKILL.md`](.claude/skills/to-issues/SKILL.md). Thin wrapper that delegates to [`.claude/agents/slicer.md`](.claude/agents/slicer.md) (produces N=3 alternative decompositions per ADR-0003 D3) and [`.claude/agents/slicer-critic.md`](.claude/agents/slicer-critic.md) (picks best of N, then single revision loop). Invocation shape `/to-issues` preserved; new internals. Output: GitHub Issues (one per vertical slice) with the `slice` label and sub-issue link to the parent PRD.

### How to research / evaluate options — ⏳ future
Will be a `researcher` subagent with restricted tools (read + WebFetch only). Returns clean findings to the main agent.

### How to prototype — ⏳ future
Will be N parallel `prototyper` subagents, each trying a different approach in isolation. Main agent picks the winner.

### How to implement (TDD red → green → refactor) — ⏳ future
Will be the `tdd` skill (Matt's) + `implementer` subagent (cheap model, isolated context per issue).

### How to review a PR — ✓ available
See [`.claude/agents/reviewer.md`](.claude/agents/reviewer.md). Invoked via `Agent` tool with `subagent_type: "reviewer"`. Reads PR body + diff + CLAUDE.md + ADRs + linked issues. Posts a structured verdict comment. On APPROVE → auto-merges via `gh pr merge --squash --delete-branch`. On BLOCK → returns PR to the implementer. Enforces I4 (LoC cap), I5 (escalation), and `Closes #<slice-issue>` per ADR-0002 / ADR-0003.

### How to write a QA plan — ✓ available
See [`.claude/skills/qa-plan/SKILL.md`](.claude/skills/qa-plan/SKILL.md). Invoke when all GitHub issues for a PRD have been merged. Generates a structured acceptance-test checklist as a comment on the PRD issue. The human runs the tests and marks pass/fail. **This is the terminal human checkpoint** in the autonomous pipeline per ADR-0003 D4.

---

## Where to look for more

- Autonomous merge policy: [`decisions/0002-autonomous-merge-policy.md`](decisions/0002-autonomous-merge-policy.md)
- Autonomous multi-stage pipeline with critics: [`decisions/0003-autonomous-pipeline-with-critics.md`](decisions/0003-autonomous-pipeline-with-critics.md)
- Matt Pocock's upstream skills: https://github.com/mattpocock/skills
