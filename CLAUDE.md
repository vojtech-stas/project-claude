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
11. **Surface deferred work as captured issues.** Every agent MUST capture every deferred or follow-up item it encounters as a `captured`-labeled GitHub issue (per [ADR-0006](decisions/0006-backlog-and-session-continuity.md) D4 as amended forward by [ADR-0008](decisions/0008-workflow-autolog-bootstrap-and-naming.md) D8). The autopilot's `backlog-critic` filters quality downstream per [ADR-0008](decisions/0008-workflow-autolog-bootstrap-and-naming.md) D2 — agents are not the bouncer. When in doubt about whether an item is worth capturing, capture it; the autopilot will BLOCK noise into the captured-tier graveyard where lazy human review can cull. Per [ADR-0009](decisions/0009-discipline-tightening.md) D2 (supersedes [ADR-0006](decisions/0006-backlog-and-session-continuity.md) D4's discretionary phrasing). The `captured` tier is the noisy raw layer; `backlog` is the curated forward queue — `backlog-critic` filters one into the other. BLOCKed captures remain visible for rescue if mis-classified.
12. **Claude Code hooks are logging/validation/notification only.** Per [ADR-0015](decisions/0015-claude-code-hooks-adoption.md), Claude Code hooks are configured in `.claude/settings.json` and may log to local files, validate by exit code, or notify via stderr. Hooks may NOT auto-invoke skills or subagents (technically impossible), and they do NOT replace the `.githooks/pre-commit` server-side layer or the ADR-0008 D3 inline-firing convention — they are additive. See ADR-0015 for the scope policy.
13. **Root-cause workflow capture (Symptoms ≠ causes).** When any agent encounters a workflow mistake — a recurring failure pattern, a critic round that should have been one round shorter, a manual orchestration bypass, a cascade-doc conflict, or any "I had to work around this" moment — it MUST capture a `captured`-labeled GitHub issue with a 3-part body naming (a) the **symptom** observed, (b) the **root cause** analyzed, and (c) the **proposed** workflow change that prevents recurrence. Symptom-only fixes in the in-flight PR are necessary but insufficient; the workflow change is the deliverable. Same downstream mechanism as rule #11: `/promote-to-backlog` fires inline per [ADR-0008](decisions/0008-workflow-autolog-bootstrap-and-naming.md) D3 and `backlog-critic`'s 4-criterion rubric (per [ADR-0008](decisions/0008-workflow-autolog-bootstrap-and-naming.md) D4) filters quality. Complementary to rule #11 (forward-work, open shape); rule #13 covers backward/root-cause analyses (3-part shape). Per [ADR-0024](decisions/0024-root-cause-workflow-capture-discipline.md).

15. **Every feature is production-verified before "done".** After all slices merge, `qa-tester` must return `PRODUCTION_VERIFY: PASS` (via `/build` step 5 or standalone `/ship` step 6) before the feature is considered complete. A feature is NOT "done" on reviewer APPROVE alone — the production gate is the final, blocking step. Per [ADR-0037](decisions/0037-production-verification-gate.md) D1.

_(Rule #14 RETIRED per [ADR-0032](decisions/0032-workflow-only-architecture.md) D2. Slot explicitly retired; the separate KB layer no longer exists. Future rules may use #15+.)_

---

## Hierarchy — PRD → Slice → PR (3-tier)

Per [ADR-0003](decisions/0003-autonomous-pipeline-with-critics.md) D1, the unit-of-delivery hierarchy is exactly three tiers:

- **PRD** — GitHub Issue, label `prd`. One feature-sized deliverable per PRD. Multi-feature PRDs are a smell.
- **Slice** — GitHub sub-issue under the PRD (linked via the native sub-issue mechanism), label `slice`. One INVEST-shaped vertical, fits in one PR.
- **PR** — one merged change, closes exactly one slice via `Closes #<slice-issue>` in the PR body.

**Slice decomposition is the slicer's job — not the grill's, not the user's.** How many slices, where the slice boundaries fall, and the walking-skeleton cut are owned by the `slicer` + `slicer-critic` (per [ADR-0013](decisions/0013-slicer-n3-contract-refined.md) + [ADR-0005](decisions/0005-output-shape-and-slicing-methodology.md) D3). The grill / PRD-authoring phase settles **design, acceptance criteria, and appetite** (the rough size/ambition) — then hands the PRD to `/to-issues`, which dispatches the slicer to decompose. Never grill the user with "how should we slice this?" / "how many slices?" — produce the design, let the slicer cut it.

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

## Workflow improvements I1–I6

These are load-bearing conventions that supplement the cross-cutting rules. Per PRD #3 §4 and [ADR-0003](decisions/0003-autonomous-pipeline-with-critics.md).

- **I1 — Skills know the hierarchy.** `/to-prd` and `/to-issues` produce/consume the 3-tier hierarchy and the `prd`/`slice` labels (delivered by PRD #3 slices 2 and 3).
- **I2 — Slice-grabbing protocol.** The first agent to run `gh issue edit <slice> --add-assignee @me` owns the slice. The reviewer enforces "one assignee per open slice" — if a second agent grabs an already-assigned slice, reviewer BLOCKs the resulting PR.
- **I3 — Trivial lane.** PRs ≤10 LoC of runtime-artifact diff with no behavior change MAY skip PRD/slice ceremony. Branch: `hotfix/<short-summary>`. Add the `trivial` label to the PR; the reviewer fast-paths it.
- **I4 — Slice size cap & staleness.** Slice PRs cap at **≤300 LoC of runtime-artifact diff**. The canonical definition of "runtime artifact" lives in [`.claude/agents/reviewer.md`](.claude/agents/reviewer.md) (rule R-LOC) — do not restate it here. A slice issue open >7 days is marked stale by the reviewer.
- **I4a — Subagent dispatch isolation.** All `implementer` and `reviewer` subagent dispatches — by `/ship` OR the main agent dispatching manually — MUST pass `isolation: "worktree"`, so a dispatched subagent never mutates the orchestrator's session worktree or the root repo (per [ADR-0036](decisions/0036-worktree-isolation-all-dispatches.md)). After each dispatch returns, the orchestrator MUST run the post-dispatch guard (`bash tools/worktree-guard.sh branch-restore <expected>`) to ff-restore if the worktree drifted; after a merge, run `bash tools/worktree-guard.sh root-sync` to ff-sync the root repo to `origin/main` (per [ADR-0041](decisions/0041-origin-main-source-of-truth.md) D1/D3).
- **I5 — Escalation surface.** On round-3 BLOCK, the reviewer applies the `needs-human` label to the PR AND posts a comment on the parent PRD issue summarizing the stuck slice. Humans run `gh pr list --label needs-human` at session start to find what's waiting on them.
- **I6 — Boy-scout drift detection at PR time.** Per [ADR-0018](decisions/0018-boy-scout-reviewer-rule.md), the reviewer's discretionary `R-BOY-SCOUT` rule fires when a PR's diff touches audit-relevant files (`.claude/agents/*.md`, `.claude/skills/*/SKILL.md`, `decisions/*.md`, `CLAUDE.md`, `README.md`) and applies the relevant `/audit-subagents` + `/audit-meta` rubric checks inline against the touched files only. Findings emit as BLOCK (when the rule has zero documented false-positive cases AND the fix is mechanical AND the drift materially impacts future readers) or Recommendation otherwise. Default-conservative-toward-REC; the rule is additive defense-in-depth alongside the 11 hard-block reviewer rules, not the primary gate. The canonical rule lives in [`.claude/agents/reviewer.md`](.claude/agents/reviewer.md) under "Discretionary rule — R-BOY-SCOUT" — do not restate it here.

### Meta-rule: critic count cap

Per [ADR-0008](decisions/0008-workflow-autolog-bootstrap-and-naming.md) D7, the project currently runs **6 critics** (`reviewer`, `prd-critic`, `adr-critic`, `slicer-critic`, `glossary-critic`, `backlog-critic`). Promoting a **7th critic requires a new ADR that explicitly justifies why an existing critic's rubric cannot absorb the concern**. The default disposition for future critic-shaped problems is "extend an existing critic"; net-new subagents are the exception, not the rule.

---

## Skill vs subagent — the litmus rule

**Subagent** = isolated-context + handed-a-task + returns-a-result (heavy work / adversarial review / parallel); **skill** = the orchestrator's own interactive/orchestrating/multi-step procedure. Only the main agent dispatches subagents; subagents never dispatch subagents. "Skills dispatch subagents" is the intended topology, not an anti-pattern — it is the only model the runtime permits. Per [ADR-0038](decisions/0038-skill-vs-agent-rule.md).

---

## Map — where things live

| Thing | Path | Summary |
|---|---|---|
| Pipeline skills | `.claude/skills/<name>/SKILL.md` | `ls .claude/skills/` for the full list |
| `/ship` orchestrator | `.claude/skills/ship/SKILL.md` | autonomous PRD-to-merge chain |
| Subagents | `.claude/agents/<name>.md` | `ls .claude/agents/` for the full list |
| implementer subagent | `.claude/agents/implementer.md` | slice → PR, auto-invoked by `/ship` stage 4 |
| qa-tester subagent | `.claude/agents/qa-tester.md` | dual-mode bash/ui executor of QA plans |
| `/audit-subagents` skill | `.claude/skills/audit-subagents/SKILL.md` | mechanical 10-check rubric audit of subagent prompts |
| `/audit-meta` skill | `.claude/skills/audit-meta/SKILL.md` | structure + docs-currency periodic audit |
| `/glossary` skill (add\|fold subcommands) | `.claude/skills/glossary/SKILL.md` | interactive single-entry (`add`) and bulk fold (`fold`) flows for the glossary INDEX; per [ADR-0038](decisions/0038-skill-vs-agent-rule.md) D3 |
| Fresh-clone setup | `bootstrap.sh` at repo root | per [ADR-0008](decisions/0008-workflow-autolog-bootstrap-and-naming.md) D6 |
| Cascade-aware deps | `tools/cascade-finder.py` | advisory tool for cascade-aware workflow; see [tools/README.md](tools/README.md) |
| Settings + Claude Code hooks | `.claude/settings.json` | per [ADR-0015](decisions/0015-claude-code-hooks-adoption.md); scripts in `.claude/hooks/<name>.sh` |
| Workflow event log | `.claude/logs/workflow-events.jsonl` (gitignored) | JSONL of agent/bash/stop events per [ADR-0016](decisions/0016-workflow-event-log-jsonl.md) |
| Pre-commit hooks | `.githooks/pre-commit`, `.githooks/install.sh` | workflow enforcement |
| Decisions (ADRs) | `decisions/NNNN-<slug>.md` | immutable; supersede rather than edit |
| PRDs (future repo-local) | `docs/prds/NNNN-<slug>.md` | current PRDs live on GitHub Issues per [ADR-0003](decisions/0003-autonomous-pipeline-with-critics.md) D1 |
| In-flight work | GitHub Issues + branches | `gh issue list` ; `git branch` |
| Backlog (forward queue) | `gh issue list --label backlog` + Backlog column on project board #2 | curated by `backlog-critic` |
| Captured tier | `gh issue list --label captured` + Captured column on project board #2 | autopilot pre-backlog |
| Workflow dashboard | `dashboard/` | local web visualizer (architecture + health); see [dashboard/README.md](dashboard/README.md) |
| `/build` orchestrator skill | `.claude/skills/build/SKILL.md` | full-lifecycle thin conductor: dashboard-check → `/grill-me` (conditional) → `/ship` → regenerate-docs → `/qa-plan`; per [ADR-0034](decisions/0034-build-orchestrator-and-generated-docs.md) D1 |
| README template | `README.template.md` | source of truth for README.md — static prose + `{{GENERATED:*}}` placeholders; per [ADR-0034](decisions/0034-build-orchestrator-and-generated-docs.md) D4 |
| README generator | `dashboard/server.py --generate-readme` | reads template + filesystem → writes `README.md`; reuses dashboard's `discover_*` engine; no LLM calls; per [ADR-0034](decisions/0034-build-orchestrator-and-generated-docs.md) D7 |
| `/qa-review` skill | `.claude/skills/qa-review/SKILL.md` | clears `needs-human-check` QA residual queue: lists open issues, presents each via `AskUserQuestion`, accept→close / reject→relabel+capture; per [ADR-0040](decisions/0040-qa-human-residual-model.md) D4 |

---

## Glossary (key terms)

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

---

## Where to look for more

- Autonomous merge policy: [`decisions/0002-autonomous-merge-policy.md`](decisions/0002-autonomous-merge-policy.md)
- Autonomous multi-stage pipeline with critics: [`decisions/0003-autonomous-pipeline-with-critics.md`](decisions/0003-autonomous-pipeline-with-critics.md)
- Matt Pocock's upstream skills: https://github.com/mattpocock/skills
