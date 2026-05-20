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
10. **Main-agent meta-output discipline.** Main agent never hand-authors ANY tracked file. All edits to tracked files flow through the PRD/slice/PR pipeline via `/to-prd`, `/to-issues`, `/ship`, an implementer Agent invocation, the trivial-lane (I3) workflow, or any other reviewer-gated PR channel. Per [ADR-0009](decisions/0009-discipline-tightening.md) D1 (supersedes [ADR-0004](decisions/0004-bypass-prevention.md) D4's enumerated-path scope).
11. **Surface deferred work as captured issues.** Every agent MUST capture every deferred or follow-up item it encounters as a `captured`-labeled GitHub issue (per [ADR-0006](decisions/0006-backlog-and-session-continuity.md) D4 as amended forward by [ADR-0008](decisions/0008-workflow-autolog-bootstrap-and-naming.md) D8). The autopilot's `backlog-critic` filters quality downstream per [ADR-0008](decisions/0008-workflow-autolog-bootstrap-and-naming.md) D2 — agents are not the bouncer. When in doubt about whether an item is worth capturing, capture it; the autopilot will BLOCK noise into the captured-tier graveyard where lazy human review can cull. Per [ADR-0009](decisions/0009-discipline-tightening.md) D2 (supersedes [ADR-0006](decisions/0006-backlog-and-session-continuity.md) D4's discretionary phrasing).

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

### Issue-title naming convention

Per [ADR-0008](decisions/0008-workflow-autolog-bootstrap-and-naming.md) D5:

- **Posted PRDs** follow the canonical `PRD: <one-line feature summary>` form (every issue from #3 onward).
- **Backlog issue titles** are descriptive only — a short noun phrase that names what the item IS. No codename prefixes (`PRD-C —`), no topical classifiers (`PRD-qa-automation:`).
- **Session codenames** (PRD-A, PRD-B, PRD-C, PRD-D, …) are conversation/transcript shortcuts only; they never appear in tracked artifact titles.
- On promotion `backlog` → `prd`, the title is rewritten into the canonical `PRD:` form.

Rationale: codename-prefixed titles in `backlog` pre-bias candidate selection (they read as "this WILL be next" rather than "this is a candidate"). The backlog must function as a neutral pool from which `/grill-me` picks based on current priorities. Binds forward per ADR-0008 D8; no retroactive sweep beyond the 2026-05-16 cleanup of #47 and #57.

---

## Workflow improvements I1–I5

These are load-bearing conventions that supplement the cross-cutting rules. Per PRD #3 §4 and [ADR-0003](decisions/0003-autonomous-pipeline-with-critics.md).

- **I1 — Skills know the hierarchy.** `/to-prd` and `/to-issues` produce/consume the 3-tier hierarchy and the `prd`/`slice` labels (delivered by PRD #3 slices 2 and 3).
- **I2 — Slice-grabbing protocol.** The first agent to run `gh issue edit <slice> --add-assignee @me` owns the slice. The reviewer enforces "one assignee per open slice" — if a second agent grabs an already-assigned slice, reviewer BLOCKs the resulting PR.
- **I3 — Trivial lane.** PRs ≤10 LoC of runtime-artifact diff with no behavior change MAY skip PRD/slice ceremony. Branch: `hotfix/<short-summary>`. Add the `trivial` label to the PR; the reviewer fast-paths it.
- **I4 — Slice size cap & staleness.** Slice PRs cap at **≤300 LoC of runtime-artifact diff**. The canonical definition of "runtime artifact" lives in [`.claude/agents/reviewer.md`](.claude/agents/reviewer.md) (rule R-LOC) — do not restate it here. A slice issue open >7 days is marked stale by the reviewer.
- **I5 — Escalation surface.** On round-3 BLOCK, the reviewer applies the `needs-human` label to the PR AND posts a comment on the parent PRD issue summarizing the stuck slice. Humans run `gh pr list --label needs-human` at session start to find what's waiting on them.

### Meta-rule: critic count cap

Per [ADR-0008](decisions/0008-workflow-autolog-bootstrap-and-naming.md) D7, the project currently runs **6 critics** (`reviewer`, `prd-critic`, `adr-critic`, `slicer-critic`, `glossary-critic`, `backlog-critic`). Promoting a **7th critic requires a new ADR that explicitly justifies why an existing critic's rubric cannot absorb the concern**. The default disposition for future critic-shaped problems is "extend an existing critic"; net-new subagents are the exception, not the rule.

---

## Map — where things live

| Looking for… | Find it at | Lookup command |
|---|---|---|
| Pipeline skills | `.claude/skills/<name>/SKILL.md` | `ls .claude/skills/` |
| `/ship` orchestrator | `.claude/skills/ship/SKILL.md` | `cat .claude/skills/ship/SKILL.md` |
| Subagents (full list via `ls`) | `.claude/agents/<name>.md` | `ls .claude/agents/` |
| implementer subagent (slice → PR; auto-invoked by `/ship` stage 4) | `.claude/agents/implementer.md` | `cat .claude/agents/implementer.md` |
| `/audit-subagents` skill (periodic subagent-prompt quality audit per [ADR-0011](decisions/0011-subagent-quality-framework.md)) | `.claude/skills/audit-subagents/SKILL.md` | `cat .claude/skills/audit-subagents/SKILL.md` |
| Fresh-clone project setup | `bootstrap.sh` at repo root (per [ADR-0008](decisions/0008-workflow-autolog-bootstrap-and-naming.md) D6) | `./bootstrap.sh` |
| Settings, permissions, hooks | `.claude/settings.json` | `cat .claude/settings.json` (none yet) |
| Pre-commit hooks (workflow enforcement) | `.githooks/pre-commit`, `.githooks/install.sh` | `ls .githooks/` |
| Decisions (ADRs) | `decisions/NNNN-<slug>.md` | `ls decisions/` |
| PRDs (future repo-local) | `docs/prds/NNNN-<slug>.md` | `ls docs/prds/` (created when first PRD lands there; current PRDs live on GitHub Issues per ADR-0003 D1) |
| Current work in flight | GitHub Issues + branches | `gh issue list` ; `git branch` |
| Recent activity | git history | `git log --oneline -20` |
| Forward-looking work queue (backlog) | `gh issue list --label backlog` + Backlog column on project board #2 | — |
| Captured tier (autopilot pre-backlog) | `gh issue list --label captured` + Captured column on project board #2 | — |

---

## Glossary (key terms)

Auto-loaded project vocabulary per [ADR-0007](decisions/0007-vocabulary-glossary-and-grill-me-extension.md) D1 (single-tier consolidation per [ADR-0012](decisions/0012-glossary-consolidation-single-tier.md) D1). Soft cap ~35 entries (per ADR-0012 D5). Each entry follows the canonical shape from [ADR-0007](decisions/0007-vocabulary-glossary-and-grill-me-extension.md) D2 (term + one-sentence definition + authority + see-also). To add a term, run `/glossary-add`; [`glossary-critic`](.claude/agents/glossary-critic.md) gates each addition against the 5-rule rubric (including ADR-0012 D2's ≥3-citations-across-≥2-directories inclusion threshold).

- **PRD** — a feature-sized Product Requirements Document captured as a GitHub Issue labeled `prd`, with the 6-section template (Problem / Goal / Non-goals / Appetite / Solution sketch / Rabbit-holes & Open questions); the top tier of the PRD → Slice → PR hierarchy.
  - *Scope:* (a) project jargon coined here
  - *Authority:* [ADR-0003](decisions/0003-autonomous-pipeline-with-critics.md) D1
  - *See also:* slice; PR
- **ADR** — an Architecture Decision Record stored as `decisions/NNNN-<slug>.md`, immutable after acceptance and superseded by a new ADR rather than edited in place.
  - *Scope:* (b) external standard adopted
  - *Authority:* [ADR-0001](decisions/0001-foundational-design.md) D8
  - *See also:* supersession; bootstrap-mode
- **backlog** — the forward-looking work queue of `backlog`-labeled GitHub Issues plus the Backlog column on project board #2, holding queued ideas not yet ready for full PRD grilling.
  - *Scope:* (c) common word with narrowed meaning here
  - *Authority:* [ADR-0006](decisions/0006-backlog-and-session-continuity.md) D1
  - *See also:* PRD; session
- **bootstrap-mode** — the policy that new conventions bind FORWARD from the slice that ships them, with no retroactive sweep across pre-existing artifacts.
  - *Scope:* (a) project jargon coined here
  - *Authority:* [ADR-0004](decisions/0004-bypass-prevention.md) D2
  - *See also:* ADR
- **cascade-doc check** — the slicer's responsibility to identify docs (README, CLAUDE.md Map rows, ADR index rows) that *should* update to reflect a new feature even when not strictly required by acceptance criteria, and add or fold a slice to cover them.
  - *Scope:* (a) project jargon coined here
  - *Authority:* [ADR-0005](decisions/0005-output-shape-and-slicing-methodology.md) D3
  - *See also:* slice
- **Conventional Commits** — the `<type>(<optional scope>): <subject>` commit-message format (types: `feat`, `fix`, `docs`, `chore`, `refactor`, `test`, `perf`, `style`, `build`, `ci`) applied here with a lowercase subject, ≤72-char cap, and a `Co-authored-by:` trailer on agent commits.
  - *Scope:* (b) external standard adopted
  - *Authority:* https://www.conventionalcommits.org/en/v1.0.0/
  - *See also:* trivial lane
- **critic** — a subagent whose sole job is adversarial scope/quality audit of another stage's output, emitting an APPROVE/BLOCK verdict in the canonical 5-section template; never edits artifacts directly.
  - *Scope:* (c) common word with narrowed meaning here
  - *Authority:* [ADR-0003](decisions/0003-autonomous-pipeline-with-critics.md) D2
  - *See also:* subagent; joint-APPROVE gate; CRITIC trailer
- **CRITIC trailer** — the canonical fenced field-schema block (`VERDICT`, `REASON`, `ROUND`, optional `FAILED_RULES`/`FINDINGS_COUNT`/`ESCALATE`) appended at the end of every critic verdict so consumers can parse it programmatically.
  - *Scope:* (a) project jargon coined here
  - *Authority:* [ADR-0005](decisions/0005-output-shape-and-slicing-methodology.md) D1
  - *See also:* GENERATOR trailer; critic
- **GENERATOR trailer** — the canonical fenced field-schema block (`RESULT`, `REASON`, `ARTIFACTS`, plus per-agent extensions) appended at the end of every output-emitting generator's output (`slicer`, `qa-plan`, `ship`).
  - *Scope:* (a) project jargon coined here
  - *Authority:* [ADR-0005](decisions/0005-output-shape-and-slicing-methodology.md) D1
  - *See also:* CRITIC trailer
- **hamburger method** — a vertical-slicing technique that decomposes a feature into thin end-to-end slices cutting through every layer (schema, logic, UI, test) rather than building one horizontal layer at a time.
  - *Scope:* (b) external standard adopted
  - *Authority:* https://gojko.net/2012/05/01/the-hamburger-method/
  - *See also:* SPIDR; walking-skeleton; slice
- **INVEST** — Bill Wake's six-property check for a well-formed user story (Independent, Negotiable, Valuable, Estimable, Small, Testable) used here as the shape criterion for a slice.
  - *Scope:* (b) external standard adopted
  - *Authority:* [ADR-0003](decisions/0003-autonomous-pipeline-with-critics.md) D1
  - *See also:* slice; SPIDR
- **joint-APPROVE gate** — the rule that when a PRD ships with a macro-ADR draft, BOTH `prd-critic` AND `adr-critic` must APPROVE before `/to-prd` posts anything.
  - *Scope:* (a) project jargon coined here
  - *Authority:* [ADR-0004](decisions/0004-bypass-prevention.md) D1
  - *See also:* critic; ADR
- **R-CLOSES** — the reviewer rule that every slice PR's body must contain a `Closes #<n>` line pointing to a valid `slice`-labeled issue (with exemptions for `trivial`/`prd` PRs against issues of the matching tier).
  - *Scope:* (a) project jargon coined here
  - *Authority:* [`.claude/agents/reviewer.md`](.claude/agents/reviewer.md) rule 10
  - *See also:* R-LOC; R-META; slice
- **R-LOC** — the reviewer rule that caps a slice PR's diff at ≤300 LoC of runtime-artifact code (canonical definition of "runtime artifact" lives in `reviewer.md`).
  - *Scope:* (a) project jargon coined here
  - *Authority:* [`.claude/agents/reviewer.md`](.claude/agents/reviewer.md) rule 9
  - *See also:* R-CLOSES; R-META; slice
- **R-META** — the reviewer rule that NEW ADR files (`decisions/NNNN-*.md`) must show subagent provenance via a `Closes #N` link to a `slice`/`prd` issue OR a `Co-Authored-By: Claude` commit trailer, enforcing main-agent meta-output discipline.
  - *Scope:* (a) project jargon coined here
  - *Authority:* [ADR-0004](decisions/0004-bypass-prevention.md) D4
  - *See also:* R-LOC; R-CLOSES; ADR
- **session** — a single Claude Code conversation in this repo (auto-loaded with `CLAUDE.md` on start), reconstructed by new sessions from live state — `git log`, `gh issue list`, project board — rather than a formal handoff document.
  - *Scope:* (c) common word with narrowed meaning here
  - *Authority:* [ADR-0006](decisions/0006-backlog-and-session-continuity.md) D2
  - *See also:* backlog
- **slice** — a single INVEST-shaped vertical sub-issue under a PRD (labeled `slice`), completable in one PR with ≤300 LoC runtime-artifact diff; the middle tier of the PRD → Slice → PR hierarchy.
  - *Scope:* (c) common word with narrowed meaning here
  - *Authority:* [ADR-0003](decisions/0003-autonomous-pipeline-with-critics.md) D1
  - *See also:* PRD; INVEST; trivial lane; R-LOC
- **SPIDR** — Mike Cohn's five split-fallback techniques (**S**pike, **P**ath, **I**nterface, **D**ata, **R**ules) used here as split hints when a slice approaches the LoC cap, with S/I/R most applicable to this agent-workflow domain.
  - *Scope:* (b) external standard adopted
  - *Authority:* [ADR-0005](decisions/0005-output-shape-and-slicing-methodology.md) D2
  - *See also:* slice; hamburger method; INVEST
- **subagent** — a specialist agent invoked via the `Agent` tool with its own model, restricted tool set, and isolated context window, defined under `.claude/agents/<name>.md`.
  - *Scope:* (c) common word with narrowed meaning here
  - *Authority:* [ADR-0001](decisions/0001-foundational-design.md) D6
  - *See also:* critic; skill
- **trivial lane** — the fast-path workflow (I3) for PRs ≤10 LoC of runtime-artifact diff with no behavior change: branch `hotfix/<short-summary>`, label `trivial`, no PRD/slice ceremony.
  - *Scope:* (a) project jargon coined here
  - *Authority:* [ADR-0003](decisions/0003-autonomous-pipeline-with-critics.md) D1
  - *See also:* slice; Conventional Commits
- **walking-skeleton** — the practice of shipping the smallest possible end-to-end version of the whole pipeline first and then iterating on the weakest stage, rather than perfecting each primitive in isolation.
  - *Scope:* (b) external standard adopted
  - *Authority:* [ADR-0001](decisions/0001-foundational-design.md) D10
  - *See also:* YAGNI; hamburger method
- **YAGNI** — "You Aren't Gonna Need It"; the rule #1 cross-cutting practice that no code is added outside the current slice's scope, enforced by the reviewer.
  - *Scope:* (b) external standard adopted
  - *Authority:* [ADR-0001](decisions/0001-foundational-design.md) D12
  - *See also:* slice; walking-skeleton

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

**Methodology depth** (canonical home of the slicing methodology overview, per [ADR-0005](decisions/0005-output-shape-and-slicing-methodology.md) D2):

- **Hamburger method (Gojko Adzic).** A good slice is *vertical* — it cuts through every layer (schema, logic, UI, test) even if crudely. **Slice 1 of any PRD must satisfy this.** Horizontal layering ("build all the modules first, wire them up later") is the anti-pattern; reject it at slicing time.
- **SPIDR vocabulary (Mike Cohn)** for split-fallback hints when a slice approaches the LoC cap: **S**pike (research/learning slice), **P**ath (different user paths), **I**nterface (split by interface/CLI/API), **D**ata (different data variations), **R**ules (different business rules). For our agent-workflow domain, **S, I, R** are most applicable (no end-user paths; no rich data variation). Path and Data rarely fit; deferred per ADR-0005 D2.
- **Lawrence's story-splitting flowchart.** Full decision tree at https://www.humanizingwork.com/the-humanizing-work-guide-to-splitting-user-stories/ — referenced externally; not inlined in `slicer.md` (per ADR-0005 Alt-G rejection).
- **Cascade-doc check** (slicer responsibility, per [ADR-0005](decisions/0005-output-shape-and-slicing-methodology.md) D3). For each candidate decomposition, identify files that *should* be updated to reflect the new feature even when not strictly required by acceptance criteria — `README.md`, `CLAUDE.md` Map rows, ADR index rows, downstream docs. Add a slice (or merge into an existing slice) to cover each identified cascade-doc. The `slicer-critic`'s rubric includes a matching "Cascade-docs identified and covered" criterion.

The actionable application of hamburger + SPIDR + cascade-doc check lives in [`.claude/agents/slicer.md`](.claude/agents/slicer.md) (operational); the overview above is the cross-agent reference (per ADR-0005 D2).

---

## Output-shape standard for subagents and output-emitting skills

Per [ADR-0005](decisions/0005-output-shape-and-slicing-methodology.md) D1 (canonical home), subagents and output-emitting skills conform to canonical output shapes so cross-agent consumers (`/ship`, future orchestrators) can parse returns via a shared schema and so critic verdict bodies converge across the four critics.

**Scope.** The 4 critics — `reviewer`, `prd-critic`, `adr-critic`, `slicer-critic` — emit the verdict template + CRITIC trailer below. The output-emitting generators — `slicer`, `qa-plan`, `ship` (and the "Final approved decomposition" output of `slicer-critic`) — emit the GENERATOR trailer below; their bodies remain domain-shaped (per ADR-0005 D1c).

### Verdict template (required for the 4 critics)

The critic's emitted output body has **5 required sections, in order**:

1. **Header** — `## <critic-name> verdict: [APPROVE | BLOCK] (round N/3)`
2. **Subject of review** — 2–4 sentences. What is being judged. The critic's restated spec contract.
3. **Rubric** — each criterion: PASS/FAIL + reason. Per-rule line items; numbered.
4. **Findings** — on BLOCK: numbered itemized list, mechanically-actionable (rule + section + diagnosis + concrete fix). On APPROVE: `None.`
5. **Summary** — one paragraph. The synthesis the human reads first.

Then the **CRITIC trailer** (below).

**Permitted critic-specific extensions**, appended *after* Summary, *before* the trailer: Recommendations (non-blocking), Scoring matrix (`slicer-critic`), Tiebreak path, Final approved decomposition (`slicer-critic`), Merge status (`reviewer`). Extensions are named in the critic's own body file; this section does not enumerate them.

### CRITIC trailer field schema

Fenced code block at the end of the verdict output:

```
VERDICT: APPROVE | BLOCK
REASON: <one sentence>
ROUND: <N>/<max>
# On BLOCK additionally:
FAILED_RULES: <comma-separated rule IDs>
FINDINGS_COUNT: <integer>
# On round-max BLOCK additionally:
ESCALATE: needs-human
```

### GENERATOR trailer field schema

Fenced code block at the end of the generator output:

```
RESULT: SUCCESS | STOPPED | INVALID_INPUT
REASON: <one sentence>
ARTIFACTS: <URLs or paths, comma-separated>
# Per-agent extensions follow (e.g., COVERAGE_GAPS, MERGE_STATUS, SLICE_COUNT)
```

**Rule.** Generator output **bodies are NOT standardized** (per ADR-0005 D1c) — each generator's body shape serves its domain (decompositions for `slicer`, test plans for `qa-plan`, chain reports for `ship`). Only the trailer is canonical.

See [ADR-0005](decisions/0005-output-shape-and-slicing-methodology.md) D1 for the canonical specification and rationale; D4 records the bootstrap-mode rollout (each subagent/skill file becomes canonical at the moment its alignment slice merges).

---

## Pipeline operational logic

The HOW for each pipeline stage. Per [ADR-0003](decisions/0003-autonomous-pipeline-with-critics.md) D2, every generation stage is paired with an adversarial critic.

### How to grill (idea capture) — ✓ available
See [`.claude/skills/grill-me/SKILL.md`](.claude/skills/grill-me/SKILL.md). Invoked via `/grill-me` or natural-language match. Interviews user one question at a time, recommends an answer for each, walks the decision tree.

### How to ship a PRD end-to-end — ✓ available
See [`.claude/skills/ship/SKILL.md`](.claude/skills/ship/SKILL.md). Invoked via `/ship` after `/grill-me`. The orchestrator chains `to-prd → prd-critic → slicer → slicer-critic → gh issue create` for PRD and sub-issues, then auto-dispatches `implementer → reviewer → auto-merge` per slice in DAG-aware parallel batches at stage 4 (per [ADR-0010](decisions/0010-implementer-subagent-auto-pipeline.md) D2/D3). Single human command per feature after the grill session; `/qa-plan` is the only remaining human checkpoint.

### How to write a PRD — ✓ available
See [`.claude/skills/to-prd/SKILL.md`](.claude/skills/to-prd/SKILL.md) — **canonical home of the 6-section PRD template** (Problem / Goal / Non-goals / Appetite / Solution sketch / Rabbit-holes & Open questions). The skill invokes [`.claude/agents/prd-critic.md`](.claude/agents/prd-critic.md) in a ≤3-round APPROVE/BLOCK loop before posting, and drafts any warranted macro-ADRs alongside the PRD per ADR-0003 D8. Normally invoked indirectly via `/ship`.

### How to critique an ADR draft — ✓ available
See [`.claude/agents/adr-critic.md`](.claude/agents/adr-critic.md). Invoked by `/to-prd` in parallel with `prd-critic` whenever a macro-ADR is drafted alongside a PRD (per ADR-0004 D1). Mirrors `prd-critic`'s ≤3-round APPROVE/BLOCK loop and I5 escalation surface; rubric is ADR-specific (convention compliance, cross-ADR consistency, supersession explicit by D-ID, bootstrap-mode policy acknowledged, immutability respected). Both critics must APPROVE before `/to-prd` posts.

### How to create slices/issues from a PRD — ✓ available
See [`.claude/skills/to-issues/SKILL.md`](.claude/skills/to-issues/SKILL.md). Thin wrapper that delegates to [`.claude/agents/slicer.md`](.claude/agents/slicer.md) (produces N=3 alternative decompositions per ADR-0003 D3) and [`.claude/agents/slicer-critic.md`](.claude/agents/slicer-critic.md) (picks best of N, then single revision loop). Invocation shape `/to-issues` preserved; new internals. Output: GitHub Issues (one per vertical slice) with the `slice` label and sub-issue link to the parent PRD.

### How to research / evaluate options — ⏳ future
Will be a `researcher` subagent with restricted tools (read + WebFetch only). Returns clean findings to the main agent.

### How to prototype — ⏳ future
Will be N parallel `prototyper` subagents, each trying a different approach in isolation. Main agent picks the winner.

### How to implement a slice — ✓ available
See [`.claude/agents/implementer.md`](.claude/agents/implementer.md). Auto-invoked by the `/ship` orchestrator at stage 4 once `slicer-critic` has posted the slice sub-issues (per [ADR-0010](decisions/0010-implementer-subagent-auto-pipeline.md) D2). For each slice, `implementer` reads the slice body + parent PRD + relevant ADRs, claims the slice (I2), creates a branch per CLAUDE.md naming, implements within scope, commits per Conventional Commits, and opens a PR with `Closes #<slice>`; `reviewer` (per ADR-0010 D8) is its adversarial critic and auto-merges on APPROVE per [ADR-0002](decisions/0002-autonomous-merge-policy.md). `/ship` dispatches ready slices in DAG-aware parallel batches (per ADR-0010 D3); forward-block failure handling per ADR-0010 D4. Tool boundaries per ADR-0010 D6 (Read/Edit/Write/Bash/Glob/Grep; NOT Agent). TDD (Matt's `tdd` skill) is a future enhancement layered atop this subagent.

### How to review a PR — ✓ available
See [`.claude/agents/reviewer.md`](.claude/agents/reviewer.md). Invoked via `Agent` tool with `subagent_type: "reviewer"`. Reads PR body + diff + CLAUDE.md + ADRs + linked issues. Posts a structured verdict comment. On APPROVE → auto-merges via `gh pr merge --squash --delete-branch`. On BLOCK → returns PR to the implementer. Enforces I4 (LoC cap), I5 (escalation), and `Closes #<slice-issue>` per ADR-0002 / ADR-0003.

### How to write a QA plan — ✓ available
See [`.claude/skills/qa-plan/SKILL.md`](.claude/skills/qa-plan/SKILL.md). Invoke when all GitHub issues for a PRD have been merged. Generates a structured acceptance-test checklist as a comment on the PRD issue. The human runs the tests and marks pass/fail. **This is the terminal human checkpoint** in the autonomous pipeline per ADR-0003 D4.

### How to audit subagents — ✓ available
See [`.claude/skills/audit-subagents/SKILL.md`](.claude/skills/audit-subagents/SKILL.md). Invoked via `/audit-subagents` (no-args). The skill globs `.claude/agents/*.md`, classifies each as critic (filename ends `-critic.md` OR is `reviewer.md`) or generator, and applies the 10-check `scope`-tagged grep rubric (ALL-1..5 + CRIT-1..4 + GEN-1 per [ADR-0011](decisions/0011-subagent-quality-framework.md) D4) — 66 check evaluations per run at the current 6-critic + 2-generator baseline. Emits a single Markdown PASS/FAIL report to stdout followed by the canonical GENERATOR trailer per ADR-0005 D1c. Advisory output only — no auto-capture, no PR opened, no critic gate; the user reads the report and captures real drift findings per CLAUDE.md rule #11. Non-recursive per [ADR-0011](decisions/0011-subagent-quality-framework.md) D8: the skill does not audit itself.

### How to promote a captured item to the curated backlog — ✓ available
See [`.claude/skills/promote-to-backlog/SKILL.md`](.claude/skills/promote-to-backlog/SKILL.md) and the [`backlog-critic`](.claude/agents/backlog-critic.md) subagent. Invoked inline by whatever agent just ran `gh issue create --label captured` (per [ADR-0008](decisions/0008-workflow-autolog-bootstrap-and-naming.md) D3). `backlog-critic` evaluates the captured item against the 4-criterion rubric (actionable / scoped / not duplicate / clear, default-conservative per [ADR-0008](decisions/0008-workflow-autolog-bootstrap-and-naming.md) D4); on APPROVE the autopilot swaps labels `captured` → `backlog`, on BLOCK the item stays in the captured tier for lazy user review. Critic fires **once** per item — no ≤3-round loop and no `needs-human` escalation in autopilot mode (per [ADR-0008](decisions/0008-workflow-autolog-bootstrap-and-naming.md) D2).

### Session continuity — how new sessions resume

No formal handoff document. New Claude Code sessions reconstruct state from **live state** per [ADR-0006](decisions/0006-backlog-and-session-continuity.md) D2:

- `git log --oneline -10` — recent commits / branch state
- `gh issue list --state open --label slice` — in-flight slices
- `gh pr list --state open` — in-flight PRs (work under review)
- `gh issue list --label backlog` — forward queue (queued for future PRDs)
- Project board #2 column states — visual progress of in-flight work

The natural pipeline milestones (end of `/grill-me`, `/ship`, `/qa-plan`) always leave a new session in a state where live reconstruction is sufficient. Mid-task interruption (mid-grill or mid-slice) loses conversational context regardless of mechanism; this is an accepted trade-off per ADR-0006 D2.

### Promotion: backlog → PRD

When a `backlog`-labeled issue is ready for full grilling:
1. `gh issue edit <N> --remove-label backlog --add-label prd`
2. `/grill-me #<N>` to refine the body into a 6-section PRD (per ADR-0005 D1)
3. After grill, `/ship` continues the autonomous pipeline as usual

---

## Where to look for more

- Autonomous merge policy: [`decisions/0002-autonomous-merge-policy.md`](decisions/0002-autonomous-merge-policy.md)
- Autonomous multi-stage pipeline with critics: [`decisions/0003-autonomous-pipeline-with-critics.md`](decisions/0003-autonomous-pipeline-with-critics.md)
- Matt Pocock's upstream skills: https://github.com/mattpocock/skills
