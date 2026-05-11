# project-claude — agent rules

This file is auto-loaded by Claude Code on every session in this repo. It contains the rules of the road for AI agents working here, plus a map of where things live. Read it first; refer back to it when unsure.

For the FULL design rationale behind these rules, read [`decisions/0001-foundational-design.md`](decisions/0001-foundational-design.md).

---

## Cross-cutting rules (apply to every action you take)

1. **YAGNI — rule #1.** Never add code outside the current slice's scope. Reviewer's first job is to enforce this. If you feel the urge to add something "while you're here", STOP and ask the user.
2. **Walking-skeleton mindset.** Smallest end-to-end version first; iterate on the weakest stage. Never build a primitive perfectly before the whole pipeline runs.
3. **Build primitives first, orchestrate last.** Do not write an orchestrator before the things it orchestrates exist and have been dogfooded.
4. **Never push directly to `main`.** Every change ships through a feature branch + PR. Branch protection (when configured) enforces this; meanwhile it's a discipline rule.
5. **Conventional Commits.** Every commit message follows `<type>(<optional scope>): <subject>`. Types: `feat`, `fix`, `docs`, `chore`, `refactor`, `test`, `perf`, `style`, `build`, `ci`. Body explains WHY, not what.
6. **`git log` is the changelog.** Don't create a separate CHANGELOG file. Good commit messages do the job.
7. **Practices are colocated.** Skills/subagents embody their own practice in their own body. No separate `docs/practices/` folder. Cross-cutting rules (this list) live HERE.
8. **One thing at a time.** One in-progress todo. One in-flight PR per slice.
9. **DRY for docs.** Don't duplicate info. Link/point to where the canonical version lives.

---

## Map — where things live

| Looking for… | Find it at | Lookup command |
|---|---|---|
| Pipeline skills | `.claude/skills/<name>/SKILL.md` | `ls .claude/skills/` |
| Subagents | `.claude/agents/<name>.md` | `ls .claude/agents/` (empty until slice 7) |
| Settings, permissions, hooks | `.claude/settings.json` | `cat .claude/settings.json` (none yet) |
| Decisions (ADRs) | `decisions/NNNN-<slug>.md` | `ls decisions/` |
| PRDs (future) | `docs/prds/NNNN-<slug>.md` | `ls docs/prds/` (created when first PRD lands) |
| Current work in flight | GitHub Issues + branches | `gh issue list` ; `git branch` |
| Recent activity | git history | `git log --oneline -20` |
| Full design rationale | ADR-0001 | `cat decisions/0001-foundational-design.md` |
| Plan files for slices | `~/.claude/plans/*.md` | `ls ~/.claude/plans/` |

---

## Operational git workflow

Follow this EVERY time. This is the operational logic — not just the principle.

### Starting a slice

```bash
git checkout main
git pull --ff-only origin main          # always start from latest main
git checkout -b slice-N-<short-name>
```

**Branch naming:** `slice-<number>-<kebab-case-summary>` — e.g., `slice-2-foundation`, `slice-3-walking-skeleton-kit`, `slice-4-commit-skill`.

### Working within a slice

- Commit at meaningful checkpoints, not just at the end. Each commit = one coherent step.
- One Conventional Commits message per commit. Examples:
  - `feat: add grill-me skill at user + project scope`
  - `chore: scaffold foundation (LICENSE, .gitignore, CLAUDE.md, README, ADR-0001)`
  - `docs: refine git workflow operational logic in CLAUDE.md`
- Message body (after blank line) explains WHY. Bullet points OK.
- If the slice grows beyond its planned scope → **STOP** and discuss with the user. Don't sneak extras in.

### Finishing a slice

```bash
git push -u origin slice-N-<short-name>
gh pr create --title "<conv-commits-style title>" --body "<see template below>"
```

**PR body MUST include:**
- **Scope** — what's in
- **Out-of-scope** — what's deliberately NOT in this slice
- **Verification** — concrete steps to confirm it works
- **ADR reference** — link to any new ADR if this slice made a design decision

### Reviewing

- **Now (until slice 7):** human (you) reviews every PR by reading the diff in GitHub UI.
- **After slice 7:** the `reviewer` subagent leaves a comment (`LGTM` or `Changes requested: ...`). It BLOCKS on hard rules (scope drift, missing tests, YAGNI violations) and RECOMMENDS on subjective items. Human is always the final merge gate.

### Merging

- ONLY the human clicks merge in GitHub UI.
- Merge style: **squash-and-merge** by default (cleaner `main` history). Use a Conventional Commits message in the squash commit.
- After merge:
  ```bash
  git checkout main
  git pull --ff-only origin main
  git branch -d slice-N-<short-name>
  ```

### What NOT to do

- ❌ `git push --force` to a shared branch (use `--force-with-lease` if rewriting a feature branch is truly necessary)
- ❌ Commits on `main` directly
- ❌ Long-running branches (>1 week without merge) — split into smaller slices instead
- ❌ Bundle multiple unrelated changes in one commit
- ❌ Vague messages: `fix stuff`, `update`, `wip`, `final`

---

## Slicing logic — what makes a good slice

A good slice is:

- **Vertical** — ships end-to-end value, not a horizontal layer
- **Small** — completable in roughly one work session
- **Self-contained** — has its own PR, and its own ADR if it makes a real design decision
- **Reversible** — can be `git revert`-ed without breaking other slices
- **Explicitly out-of-scope-bounded** — the PR body lists what is NOT in this slice (to prevent drift)

If a planned slice feels too big → split it. If it's a one-liner (typo) → just commit on a branch and merge without ceremony.

---

## Pipeline operational logic (stubs — filled as skills/subagents land)

The HOW for each pipeline stage. Most are stubs until the relevant skill/subagent is built.

### How to grill (idea capture) — ✓ available
See [`.claude/skills/grill-me/SKILL.md`](.claude/skills/grill-me/SKILL.md). Invoked via `/grill-me` or natural-language match. Interviews user one question at a time, recommends an answer for each, walks the decision tree.

### How to research / evaluate options — ⏳ slice 5+
Will be a `researcher` subagent with restricted tools (read + WebFetch only). Returns clean findings to the main agent.

### How to prototype — ⏳ slice 5+
Will be N parallel `prototyper` subagents, each trying a different approach in isolation. Main agent picks the winner.

### How to write a PRD — ⏳ slice 3
Will be the `to-prd` skill (Matt's). Output: `docs/prds/NNNN-<slug>.md`.

### How to create tasks/issues from a PRD — ⏳ slice 3
Will be the `to-issues` skill (Matt's). Output: GitHub Issues via `gh issue create`.

### How to implement (TDD red → green → refactor) — ⏳ slice 5+
Will be the `tdd` skill (Matt's) + `implementer` subagent (cheap model, isolated context per issue).

### How to review a PR — ⏳ slice 7
Will be the `reviewer` subagent (stronger model, read + comment tools only). Blocks on hard rules, recommends on subjective.

### How to write a QA plan — ⏳ later
Emerges in a later slice. Human runs the QA plan; AI generates it from the PRD + the merged code.

---

## Where to look for more

- Full design rationale: [`decisions/0001-foundational-design.md`](decisions/0001-foundational-design.md)
- Slice planning files: `~/.claude/plans/*.md`
- Matt Pocock's upstream skills: https://github.com/mattpocock/skills
