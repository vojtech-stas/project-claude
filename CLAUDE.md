# project-claude — agent rules

This file is auto-loaded by Claude Code on every session in this repo. It contains the rules of the road for AI agents working here, plus a map of where things live. Read it first; refer back to it when unsure.

---

## 1. Cross-cutting constraints (apply to every action you take)

1. **YAGNI — rule #1.** Never add code outside the current slice's scope. If you feel the urge to add something "while you're here", STOP and ask the user. (Reviewer's first enforcement job.)
2. **Walking-skeleton mindset — rule #2.** Smallest end-to-end version first; iterate on the weakest stage. Never build a primitive perfectly before the whole pipeline runs.
3. **Build primitives first, orchestrate last — rule #3.** Do not write an orchestrator before the things it orchestrates exist and have been dogfooded.
4. **Never push directly to `main` — rule #4.** Every change ships through a feature branch + PR. Branch protection (when configured) enforces this; meanwhile it's a discipline rule.
5. **Conventional Commits, tightened — rule #5.** Every commit message follows `<type>(<optional scope>): <subject>`. Types: `feat`, `fix`, `docs`, `chore`, `refactor`, `test`, `perf`, `style`, `build`, `ci`. Additional hard rules:
   - **Lowercase subject** after the colon (`feat: add ship skill`, not `feat: Add Ship Skill`).
   - **≤72 character hard cap** on the subject line.
   - **`Closes #<slice-issue>`** belongs in the PR body, not the commit subject (reviewer enforces).
   - **`Co-authored-by:` trailer** on every agent-authored commit.
   - Body (after blank line) explains WHY, not what.
6. **`git log` is the changelog — rule #6.** Don't create a separate CHANGELOG file. Good commit messages do the job.
8. **One PR per slice — rule #8.** One PR per slice (1:1); independent slices may run in parallel; only dependent work serializes. Per [ADR-0036](decisions/0036-worktree-isolation-all-dispatches.md) D1–D3.
9. **DRY for docs — rule #9.** Don't duplicate info. Link/point to where the canonical version lives.
10. **Main-agent meta-output discipline — rule #10.** Main agent never hand-authors ANY tracked file. All edits to tracked files flow through the PRD/slice/PR pipeline via `/to-prd`, `/to-issues`, `/ship`, an implementer Agent invocation, the trivial-lane (I3) workflow, or any other reviewer-gated PR channel. Per [ADR-0009](decisions/0009-discipline-tightening.md) D1 (supersedes [ADR-0004](decisions/0004-bypass-prevention.md) D4's enumerated-path scope).

### Capture discipline

11. **Surface deferred work as captured issues — rule #11.** Every agent MUST capture every deferred or follow-up item it encounters as a `captured`-labeled GitHub issue. When in doubt, capture it — `backlog-critic` filters quality downstream; agents are not the bouncer. Shape: open forward-work (any form). Per [ADR-0006](decisions/0006-backlog-and-session-continuity.md) D4 + [ADR-0009](decisions/0009-discipline-tightening.md) D2.
13. **Root-cause workflow capture — rule #13.** When any agent encounters a workflow mistake, it MUST capture a `captured`-labeled GitHub issue with a 3-part body: (a) **symptom** observed, (b) **root cause** analyzed, (c) **proposed** workflow change. Symptom-only fixes are necessary but insufficient. Shape: 3-part backward/root-cause analysis. Per [ADR-0024](decisions/0024-root-cause-workflow-capture-discipline.md) D2/D3.

Both rules share the same downstream mechanism: `backlog-critic` filters `captured` → `backlog` via the `promote-to-backlog` skill per [ADR-0008](decisions/0008-workflow-autolog-bootstrap-and-naming.md) D3/D4. Rule #11 = forward-work (open shape); rule #13 = backward/root-cause (3-part shape). Complementary per [ADR-0024](decisions/0024-root-cause-workflow-capture-discipline.md) D2.

12. **Claude Code hooks are logging/validation/notification only — rule #12.** Hooks may NOT auto-invoke skills or subagents. See [ADR-0015](decisions/0015-claude-code-hooks-adoption.md) for full scope policy.

15. **Every feature is production-verified before "done" — rule #15.** `qa-tester` must return `PRODUCTION_VERIFY: PASS` (via `/build` step 5 or `/ship` step 6) before a feature is complete. Per [ADR-0037](decisions/0037-production-verification-gate.md) D1.

_(Rule #14 RETIRED per [ADR-0032](decisions/0032-workflow-only-architecture.md) D2. Slot explicitly retired; the separate KB layer no longer exists. Future rules may use #15+.)_

16. **Slice-decomposition is the slicer's job — rule #16.** How many slices, where boundaries fall, and the walking-skeleton cut are owned by the `slicer` + `slicer-critic`. The grill / PRD-authoring phase settles design + acceptance criteria, then hands off — never decide slicing during grill. Per [ADR-0013](decisions/0013-slicer-n3-contract-refined.md) (decomposition contract) + [ADR-0005](decisions/0005-output-shape-and-slicing-methodology.md) D3 (cascade-doc identification at decomposition time).
17. **Skill-vs-subagent litmus — rule #17.** Subagent = isolated-context + handed-a-task + returns-a-result. Skill = the orchestrator's own interactive/orchestrating/multi-step procedure. Only the main agent dispatches subagents; subagents never dispatch subagents. Per [ADR-0038](decisions/0038-skill-vs-agent-rule.md) D1.
18. **Never cite an ADR decision-ID from memory — rule #18.** Before citing `ADR-NNNN D<n>` in any drafted ADR/PRD/doc, open the cited ADR and read the actual `### D<n>` heading — the citation's characterization MUST match that heading. `decisions/README.md` is the decision index; consult it to find the right ADR. Per [ADR-0045](decisions/0045-adr-citation-consult-discipline.md).
19. **Revise the whole flagged class — rule #19.** When revising in response to a critic BLOCK, fix the ENTIRE flagged defect class (sweep every instance of the cited pattern — e.g. every `ADR-NNNN D<n>` cite, every over-cap commit), not just the single instance the critic named. A round-3 BLOCK is strict-stop (escalate via `needs-human`) — there is no fix-and-ship exception. Per [ADR-0048](decisions/0048-critic-loop-r3-policy-and-complete-class-revision.md).

---

## 2. Naming

**Commits and branches:** follow Conventional Commits (rule #5 above). Branch names: `<type>/<N>-<kebab-summary>` for slices; `hotfix/<short-summary>` for trivial lane (I3).

**Issue titles:** Posted PRDs follow the canonical `PRD: <one-line feature summary>` form. Backlog issue titles are descriptive only — a short noun phrase, no codename prefixes. Session codenames (PRD-A, PRD-B, …) are conversation shortcuts only; they never appear in tracked artifact titles. On promotion `backlog` → `prd`, the title is rewritten into `PRD:` form. Per [ADR-0008](decisions/0008-workflow-autolog-bootstrap-and-naming.md) D5.

---

## 3. Hierarchy + workflow conventions

### PRD → Slice → PR (3-tier)

Per [ADR-0003](decisions/0003-autonomous-pipeline-with-critics.md) D1, the unit-of-delivery hierarchy is exactly three tiers:

- **PRD** — GitHub Issue, label `prd`. One feature-sized deliverable per PRD. Multi-feature PRDs are a smell.
- **Slice** — GitHub sub-issue under the PRD (linked via the native sub-issue mechanism), label `slice`. One INVEST-shaped vertical, fits in one PR.
- **PR** — one merged change, closes exactly one slice via `Closes #<slice-issue>` in the PR body.

**Labels:**
- Use `prd` and `slice` exclusively for hierarchy. **There is no `feature` label** — the PRD plays that role.
- `trivial` for the trivial lane (see I3 below).
- `needs-human` is applied by the reviewer on round-3 BLOCK escalation (see I5 below).

**Milestones** are reserved for **Releases** (groups of merged PRDs). Not in use yet — left empty until the first release ships.

### Workflow improvements I1–I6

These are load-bearing conventions that supplement the cross-cutting rules. Per PRD #3 §4 and [ADR-0003](decisions/0003-autonomous-pipeline-with-critics.md).

- **I1 — Skills know the hierarchy.** `/to-prd` and `/to-issues` produce/consume the 3-tier hierarchy and the `prd`/`slice` labels (delivered by PRD #3 slices 2 and 3).
- **I2 — Slice-grabbing protocol.** The first agent to run `gh issue edit <slice> --add-assignee @me` owns the slice. The reviewer enforces "one assignee per open slice" — if a second agent grabs an already-assigned slice, reviewer BLOCKs the resulting PR.
- **I3 — Trivial lane.** PRs ≤10 LoC of runtime-artifact diff with no behavior change MAY skip PRD/slice ceremony. Branch: `hotfix/<short-summary>`. Add the `trivial` label to the PR; the reviewer fast-paths it.
- **I4 — Slice size cap & staleness.** Slice PRs cap at **≤300 LoC of runtime-artifact diff**. The canonical definition of "runtime artifact" lives in [`.claude/agents/reviewer.md`](.claude/agents/reviewer.md) (rule R-LOC) — do not restate it here. A slice issue open >7 days is marked stale by the reviewer.
- **I4a — Subagent dispatch isolation.** All `implementer` and `reviewer` subagent dispatches — by `/ship` OR the main agent dispatching manually — MUST pass `isolation: "worktree"`, so a dispatched subagent never mutates the orchestrator's session worktree or the root repo (per [ADR-0036](decisions/0036-worktree-isolation-all-dispatches.md)). After each dispatch returns, the orchestrator MUST run the post-dispatch guard (`bash tools/worktree-guard.sh branch-restore <expected>`) to ff-restore if the worktree drifted; after a merge, run `bash tools/worktree-guard.sh root-sync` to ff-sync the root repo to `origin/main`, then `bash tools/worktree-guard.sh prune` to remove landed worktrees (per [ADR-0041](decisions/0041-origin-main-source-of-truth.md) D1/D3).
- **I5 — Escalation surface.** On round-3 BLOCK, the reviewer applies the `needs-human` label to the PR AND posts a comment on the parent PRD issue summarizing the stuck slice. Humans run `gh pr list --label needs-human` at session start to find what's waiting on them.
- **I6 — Drift detection: deterministic (per-PR) + judgment (per-PRD).** R-BOY-SCOUT was retired per [ADR-0046](decisions/0046-codebase-critic-and-parsimony-reframe.md) D5. The current two-layer model: (1) **per-PR deterministic detection** — `audit-meta` + `tools/ci-checks.sh` ([ADR-0017](decisions/0017-audit-meta-consolidation.md) + [ADR-0042](decisions/0042-github-actions-ci-gate-r4.md) D1) catch structural/mechanical drift via greps/counts on every PR; (2) **per-PRD judgment detection** — the `codebase-critic` subagent ([ADR-0046](decisions/0046-codebase-critic-and-parsimony-reframe.md) D3) fires once at the closing slice of each PRD, before that slice's reviewer pass, and reviews the cumulative PRD change for semantic doc currency, architectural drift, and refactoring opportunities. See [`.claude/agents/codebase-critic.md`](.claude/agents/codebase-critic.md) for the full rubric.

### Meta-rule: critic parsimony

Per [ADR-0046](decisions/0046-codebase-critic-and-parsimony-reframe.md) D1 (reframing [ADR-0008](decisions/0008-workflow-autolog-bootstrap-and-naming.md) D7), the gate on adding a critic is **not a number** but a **parsimony principle**: minimize critics; each must earn its place against a distinct concern that no existing critic's rubric absorbs; adding one requires an ADR that makes that justification explicit. The default disposition for future critic-shaped problems is "extend an existing critic"; net-new critics are the exception, not the rule.

The project currently runs **7 critics**: `reviewer`, `prd-critic`, `adr-critic`, `slicer-critic`, `glossary-critic`, `backlog-critic`, `codebase-critic`. The `codebase-critic` (added per [ADR-0046](decisions/0046-codebase-critic-and-parsimony-reframe.md) D2) earned its place as the first critic to provide per-PRD macro judgment over cumulative codebase change — a concern no existing critic absorbs.

---

## 4. Map + Glossary

### Map — where things live

_Note: Each skill and subagent embodies its own practice in its own body file (former rule #7, demoted per [ADR-0043](decisions/0043-claude-md-restructure.md) D5). No separate `docs/practices/` folder._

| Thing | Path | Summary |
|---|---|---|
| Pipeline skills | `.claude/skills/<name>/SKILL.md` | `ls .claude/skills/` for the full list |
| `/ship` orchestrator | `.claude/skills/ship/SKILL.md` | autonomous PRD-to-merge chain |
| Subagents | `.claude/agents/<name>.md` | `ls .claude/agents/` for the full list |
| implementer subagent | `.claude/agents/implementer.md` | slice → PR, auto-invoked by `/ship` stage 4 |
| qa-tester subagent | `.claude/agents/qa-tester.md` | dual-mode bash/ui executor of QA plans |
| codebase-critic subagent | `.claude/agents/codebase-critic.md` | per-PRD macro critic — reference/doc currency + architectural drift + refactoring proposals; fires at the last slice before the reviewer; per [ADR-0046](decisions/0046-codebase-critic-and-parsimony-reframe.md) |
| `/audit-subagents` skill | `.claude/skills/audit-subagents/SKILL.md` | mechanical 10-check rubric audit of subagent prompts |
| `/audit-meta` skill | `.claude/skills/audit-meta/SKILL.md` | structure + docs-currency periodic audit |
| `/glossary` skill (add\|fold subcommands) | `.claude/skills/glossary/SKILL.md` | interactive single-entry (`add`) and bulk fold (`fold`) flows for the glossary INDEX; per [ADR-0038](decisions/0038-skill-vs-agent-rule.md) D3 |
| Fresh-clone setup | `bootstrap.sh` at repo root | per [ADR-0008](decisions/0008-workflow-autolog-bootstrap-and-naming.md) D6 |
| Cascade-aware deps | `tools/cascade-finder.py` | advisory tool for cascade-aware workflow; see [tools/README.md](tools/README.md) |
| Settings + Claude Code hooks | `.claude/settings.json` | per [ADR-0015](decisions/0015-claude-code-hooks-adoption.md); scripts in `.claude/hooks/<name>.sh` |
| Workflow event log | `.claude/logs/workflow-events.jsonl` (gitignored) | JSONL of agent/bash/stop events per [ADR-0016](decisions/0016-workflow-event-log-jsonl.md) |
| Pre-commit hooks | `.githooks/pre-commit`, `.githooks/install.sh` | workflow enforcement |
| Decisions (ADRs) | `decisions/NNNN-<slug>.md` | immutable; supersede rather than edit |
| Decisions index | `decisions/README.md` | one row per ADR (number, title, Status); consult before citing a D-ID (rule #18) |
| PRDs (future repo-local) | `docs/prds/NNNN-<slug>.md` | current PRDs live on GitHub Issues per [ADR-0003](decisions/0003-autonomous-pipeline-with-critics.md) D1 |
| In-flight work | GitHub Issues + branches | `gh issue list` ; `git branch` |
| Backlog (forward queue) | `gh issue list --label backlog` + Backlog column on project board #2 | curated by `backlog-critic` |
| Captured tier | `gh issue list --label captured` + Captured column on project board #2 | autopilot pre-backlog |
| Workflow dashboard | `dashboard/` | local web visualizer (architecture + health); see [dashboard/README.md](dashboard/README.md) |
| `/build` orchestrator skill | `.claude/skills/build/SKILL.md` | full-lifecycle thin conductor: dashboard-check → `/grill-me` (conditional) → `/ship` → regenerate-docs → `/qa-plan`; per [ADR-0034](decisions/0034-build-orchestrator-and-generated-docs.md) D1 |
| README template | `README.template.md` | source of truth for README.md — static prose + `{{GENERATED:*}}` placeholders; per [ADR-0034](decisions/0034-build-orchestrator-and-generated-docs.md) D4 |
| README generator | `dashboard/server.py --generate-readme` | reads template + filesystem → writes `README.md`; reuses dashboard's `discover_*` engine; no LLM calls; per [ADR-0034](decisions/0034-build-orchestrator-and-generated-docs.md) D7 |
| `/qa-review` skill | `.claude/skills/qa-review/SKILL.md` | clears `needs-human-check` QA residual queue: lists open issues, presents each via `AskUserQuestion`, accept→close / reject→relabel+capture; per [ADR-0040](decisions/0040-qa-human-residual-model.md) D4 |
| CI gate workflow | `.github/workflows/ci.yml` | GitHub Actions workflow; fires on pull_request; runs `tools/ci-checks.sh`; job name `ci` is the R4 required-status-check context; per [ADR-0042](decisions/0042-github-actions-ci-gate-r4.md) D1 |
| CI check script | `tools/ci-checks.sh` | deterministic CLI-runnable checks (settings.json validity, README regen-clean, ≤72-char commit subjects, dangling ADR links, decisions/README.md index); run locally before pushing; per [ADR-0042](decisions/0042-github-actions-ci-gate-r4.md) D1 |

---

### Glossary (key terms)

Auto-loaded project vocabulary. Soft cap ~35 entries per [ADR-0012](decisions/0012-glossary-consolidation-single-tier.md) D5. To add a term: run `/glossary add` (gated by [`glossary-critic`](.claude/agents/glossary-critic.md) per [ADR-0007](decisions/0007-vocabulary-glossary-and-grill-me-extension.md) D5).

- **PRD** — feature-sized Product Requirements Document captured as a GitHub Issue labeled `prd`; top tier of the PRD→Slice→PR hierarchy; one feature-sized deliverable per PRD.
- **ADR** — Architecture Decision Record; immutable, supersession-based numbered file in `decisions/`; never edited, only superseded by a newer ADR.
- **backlog** — curated forward work queue of `backlog`-labeled GitHub Issues + project board #2 Backlog column; filtered from the `captured` tier by `backlog-critic`.
- **bootstrap-mode** — new conventions bind FORWARD from the slice that ships them; no retroactive sweep of existing artifacts; prior state is grandfathered.
- **cascade-doc check** — the slicer's responsibility to identify docs that should update to reflect a new feature even when not strictly required by acceptance criteria; a formal slicer responsibility per ADR-0005 D3.
- **Conventional Commits** — `<type>(<optional scope>): <subject>` commit format; tightened here with lowercase subject, ≤72-char cap, and mandatory `Co-authored-by:` trailer on every agent-authored commit.
- **critic** — adversarial subagent that gates another pipeline stage's output via an APPROVE/BLOCK verdict; never edits the artifact it reviews.
- **CRITIC trailer** — canonical fenced field-schema block (`VERDICT`/`REASON`/`ROUND` + optionals) appended to every critic verdict message for programmatic parsing by the orchestrator.
- **GENERATOR trailer** — canonical fenced field-schema block (`RESULT`/`REASON`/`ARTIFACTS` + per-agent extensions such as `PR_URL`, `BRANCH_NAME`, `SLICE_ISSUE`) appended to every output-emitting generator's response.
- **hamburger method** — Gojko Adzic's vertical-slicing technique; slice 1 of any PRD must cut through every pipeline layer end-to-end rather than building one layer completely before the next.
- **INVEST** — Bill Wake's six-property check (Independent, Negotiable, Valuable, Estimable, Small, Testable) used here as the gate criterion for slice shape; a slice that fails any letter requires a SPIDR split before implementation.
- **joint-APPROVE gate** — when a PRD ships with a macro-ADR draft, BOTH `prd-critic` AND `adr-critic` must APPROVE before `/to-prd` posts the PRD issue and slice issues; either BLOCK halts the pipeline.
- **R-CLOSES** — reviewer rule 10: every slice PR body must contain `Closes #<n>` pointing to a valid `slice`-labeled open issue; PRs without it are BLOCKed (trivial-lane and prd-only PRs are exempted).
- **R-LOC** — reviewer rule 9: caps slice PR diff at ≤300 LoC of runtime-artifact changes (canonical "runtime artifact" definition lives in `.claude/agents/reviewer.md` under R-LOC).
- **R-META** — reviewer rule 11: NEW ADR files added in a PR must show subagent provenance via `Closes #N` to a slice/prd issue OR a `Co-Authored-By: Claude` commit trailer.
- **session** — a single Claude Code conversation window; cross-session continuity is maintained via live state reconstruction from GitHub Issues and git log, not via a formal handoff artifact.
- **slice** — INVEST-shaped vertical sub-issue under a PRD (labeled `slice`), delivered in one PR capped at ≤300 runtime LoC; middle tier of the PRD→Slice→PR hierarchy.
- **SPIDR** — Mike Cohn's 5 slice-split fallbacks (**S**pike, **P**ath, **I**nterface, **D**ata, **R**ules); S (spike/research), I (interface split), and R (rules split) are dominant in this project.
- **subagent** — specialist Claude agent invoked via the `Agent` tool with its own system prompt, restricted tool set, and isolated context window; runs as a sub-process of the main agent.
- **trivial lane** — fast-path workflow (I3) for PRs ≤10 LoC with no behavior change; uses `hotfix/<short-summary>` branch + `trivial` label; skips PRD/slice ceremony and gets a fast-path reviewer check.
- **walking-skeleton** — practice of shipping the smallest end-to-end version of the whole pipeline first, then iterating on the weakest stage; slice 1 of every multi-slice PRD must be a walking-skeleton per SC-WALKING-SKELETON.
- **YAGNI** — "You Aren't Gonna Need It"; rule #1 — never add code or content outside the current slice's scope; the reviewer's first job is to enforce this on every PR.
