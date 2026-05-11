# ADR-0001: Foundational design of project_claude

- **Status:** Accepted
- **Date:** 2026-05-12
- **Decided in:** A `grill-me` session (captured during slice 2 of the project's own development)
- **Stakeholders:** Vojtech Stas (senior engineer / project owner), Claude (AI agent under supervision)

---

## Context

The owner is a Python developer (data scientist by trade) who increasingly uses AI agents to build applications. He has observed three recurring failure modes in AI-coded development:

1. **Agents over-build** — they add code that wasn't asked for ("exploding code")
2. **Agents drift from scope** — they take liberties beyond what was agreed
3. **Agents skip the sync-with-the-deployer step** — they start coding before fully understanding intent

Twenty years of software-engineering best practice has answers to all three: small agile planning, fast feedback, expectation-sync meetings before implementation, vertical slicing, PR-style scope review. But these practices are designed for human teams. **`project_claude` is the experiment of replicating that environment with AI agents instead of humans.**

The owner plays **senior engineer**. AI agents play **the team**. He is never the one writing code; his job is to define scope, review PRs, and reject anything beyond the agreed slice.

The project is also a **clone-as-template starter** — once the workflow stabilizes here, future projects clone this repo as their starting point and inherit the workflow.

---

## Decisions

### D1. Reuse model: clone-as-template

Future projects start with `git clone vojtech-stas/project-claude my-new-app`. Everything (`.claude/`, `CLAUDE.md`, decisions, etc.) travels with the clone. Each project owns its own copy and can diverge. Updates to project_claude don't auto-propagate — clones re-pull or cherry-pick consciously.

Skill installation in slice 1 (`grill-me`) was done at BOTH user scope (`~/.claude/skills/`) and project scope (`F:\project_claude\.claude\skills\`) to support the dev workflow on this machine AND the clone model for future projects.

### D2. Stack: agnostic with Python as practical default

The template is workflow-only — no language tooling baked into the base. Python is the practical default because the owner is a Python developer, but the workflow does not depend on the language. Future stack-specific add-on modules MAY be developed but are NOT in scope for the initial template.

### D3. Visibility: public on GitHub

Repo lives at `vojtech-stas/project-claude` — public from day one. The owner wants to dogfood publicly so the workflow can be shared. License is **MIT** (permissive + attribution required), aligning with his stated wish: *"shoutout when using my code, people use it and show my workflow, I get some gain from it."* The "gain" interpretation: reputation via required attribution + network effects via stars/forks.

### D4. Issue tracker: GitHub Issues

The kanban for PRD-derived tasks lives as GitHub Issues. Rationale: integrates naturally with PRs (`closes #42`), `gh` CLI is the integration surface, free, no vendor lock-in. The `to-issues` skill (slice 3) will call `gh issue create`. GitHub Projects can provide a kanban view if needed.

### D5. Workflow pipeline

The senior-engineer-with-developers workflow has eight stages:

```
1. idea (grilled)
2. research / evaluate options
3. prototype (× N parallel options)
4. PRD (Product Requirements Document)
5. PRD → kanban issues
6. implement (TDD red → green)
7. review (AI reviewer + human final gate)
8. QA plan for human verification
```

Each stage has its own skill or subagent. The orchestrator that chains them (`/new-feature`) is built LAST, not first.

### D6. Agent topology — main agent + specialist subagents

| Stage | Where | Why |
|---|---|---|
| grill-me, PRD, issues | **Main agent** (skills) | Needs the conversation context with user |
| Research / evaluate | **Subagent** | Main only wants results, not the research process |
| Prototype × N | **Parallel subagents** | Each tries a different approach; main picks winner |
| Implementer | **Subagent** (cheap model, experimental) | Clean per-task context; cheap model OK for mechanical work; fall back to "shares main context" if quality suffers |
| Reviewer | **Subagent** (stronger model, restricted tools) | Mandatory isolation: different model, no Edit, clean judgment |
| QA plan | TBD (probably main) | Synthesis task |

Future option (not v0.1): parallel implementers all committing to one branch, single PR at end of issue batch.

### D7. Practices placement — colocated, with cross-cutting rules in CLAUDE.md

Each skill body IS the practice for its stage. Each subagent system prompt IS the practice for its role. No separate `docs/practices/` folder.

EXCEPTION: rules that apply EVERYWHERE (YAGNI, Conventional Commits, never-push-to-main, walking-skeleton mindset, branch naming, slicing logic) live in **`CLAUDE.md`** (auto-loaded by Claude Code on every session). This satisfies DRY without sacrificing visibility.

### D8. Orientation artifacts — required vs deferred

**Required in the template:**
- `CLAUDE.md` (auto-loaded; cross-cutting rules + map + operational git workflow)
- `README.md` (human-facing)
- `decisions/` (numbered ADRs)

**Skipped intentionally:**
- `CHANGELOG.md` — `git log` IS the changelog (DRY)
- Audit log files — `git log` IS the audit trail
- Daily journal files — overlap with git history

**Roadmap (NOT built unless we feel the need):**
- A custom `orient` skill that reads CLAUDE.md + recent git log + open issues + latest ADR → summarizes "where are we?"
- Matt's `handoff` skill for mid-task agent-to-agent transfer

The CLAUDE.md design pattern is **map, not duplicate**: it tells you WHERE to look (`git log` for recent work, `gh issue list` for in-flight, `decisions/` for design rationale) rather than restating those contents.

### D9. PR gate — hybrid reviewer with human as final merge

- Implementer (junior model subagent) opens the PR
- Reviewer subagent (stronger model) reviews automatically:
  - **Blocks** on hard rules: scope drift, missing tests, YAGNI violations
  - **Recommends** (non-blocking) on subjective items
- If blocked → back to implementer (loop with a maximum-rounds cap, TBD in slice 7)
- If approved → human (owner) reviews and clicks merge
- Branch protection on `main` enforces no direct commits

Until the reviewer subagent exists (slice 7), the human reviews every PR by reading the diff.

### D10. Walking skeleton — build the whole pipeline crudely first, then iterate

Originally the slice roadmap was "build each primitive perfectly, then orchestrate at the end." This was REJECTED during grilling in favor of a walking-skeleton approach: **the smallest possible end-to-end version of the whole pipeline runs first, then we iterate on the weakest stage.**

Reasons:
- Fast feedback on the whole flow — integration issues surface early
- The pipeline is always runnable, never half-built
- The orchestrator emerges naturally instead of being a big-bang final step
- Always something to demo

### D11. Slice roadmap (revised, walking-skeleton-aligned)

| # | Slice | Scope |
|---|---|---|
| 1 | ✓ done | Install `grill-me` skill (user + project scope) |
| 2 | THIS | Foundation: git init, GitHub repo, LICENSE, .gitignore, CLAUDE.md, README, ADR-0001 |
| 3 | next | Walking-skeleton kit: install Matt's `to-prd` + `to-issues` skills, build custom `reviewer` subagent |
| 4 | dogfood | Run the pipeline end-to-end to build a `commit` skill (Conventional Commits standard) |
| 5+ | iterate | Address whichever stage was weakest in slice 4; add subagents/skills only when their absence hurts |

### D12. Hard rules (must be obeyed by every agent action)

1. YAGNI (rule #1) — never add code outside scope
2. Never push directly to `main`
3. Every change ships through a PR
4. Conventional Commits format for every commit
5. Practices live in the skill/subagent that uses them; cross-cutting rules in CLAUDE.md only
6. Build primitives first, orchestrate last
7. One in-flight slice / PR at a time

---

## Consequences

### Positive

- **Scope discipline by design.** YAGNI is rule #1, enforced by a reviewer subagent, enforced by branch protection, enforced by required PR review. Multiple layers prevent "exploding code."
- **Fast feedback.** Walking-skeleton means we ship end-to-end early; pain surfaces immediately.
- **Reusable.** Clone-as-template makes every future project inherit the discipline for free.
- **Dogfooded.** The template is built using its own workflow, so the workflow has to actually work before we trust it elsewhere.
- **DRY documentation.** `git log` is the changelog; CLAUDE.md is a map not a duplicate; practices colocate with the thing that uses them.

### Negative / accepted trade-offs

- **Setup overhead.** New projects inherit a workflow with non-trivial moving parts (skills, subagents, hooks). Mitigation: walking-skeleton means each piece is added only when needed.
- **GitHub lock-in.** GitHub Issues + `gh` CLI are baked into the workflow. Migrating to another tracker later requires the `to-issues` skill to be re-pointed.
- **Public from day one.** Every commit, including messy early ones, is internet-visible. Accepted in exchange for public dogfooding value.
- **Reviewer subagent quality risk.** The blocking-on-hard-rules behavior depends on tuning. Loop-count cap (TBD slice 7) is the safety valve.
- **Human is the bottleneck.** Every merge requires the owner to click. Accepted — that's the whole point ("senior engineer over agents").

---

## Alternatives considered (and rejected)

### Alt-A: Dev workspace for user-scoped `~/.claude/` config (no clone-as-template)
Rejected. The owner explicitly wants future projects to inherit the workflow as a self-contained starter; user-scoped config doesn't travel with projects (bad for sharing, bad for new machines, bad for CI).

### Alt-B: Markdown files as issue tracker (no GitHub Issues)
Rejected. GitHub Issues integrates with PRs and is `gh`-native; markdown files would require a custom skill to manage state transitions and don't get the kanban view for free.

### Alt-C: Linear for issues
Rejected for v0.1. Slick UX but paid, vendor-locked, and creates real Linear issues during dogfooding. GitHub Issues better for early iteration. Linear remains an option later via an adapter on `to-issues`.

### Alt-D: Build each pipeline primitive to perfection, then orchestrate at the end
Rejected. This was the original plan but the owner correctly invoked the walking-skeleton / tracer-bullet pattern. Building the orchestrator last after months of primitive work risks integration surprise and a half-built pipeline for too long.

### Alt-E: Separate `docs/practices/` folder for best practices
Rejected. Violates DRY — practices already live in the skill/subagent that uses them. A separate folder creates two sources of truth that drift.

### Alt-F: Single PRACTICES.md file at root
Rejected for the same DRY reason; this would just be a less-organized version of E. Cross-cutting rules go in `CLAUDE.md` (auto-loaded); per-stage practices go in their skill body.

### Alt-G: Subagent per stage from day one (all 8 stages as subagents upfront)
Rejected. Violates walking-skeleton (speculative architecture). Only the reviewer mandatorily needs to be a subagent (different model, restricted tools, clean judgment). Other stages CAN graduate to subagents as pain emerges.

### Alt-H: All-in-one main agent (no subagents anywhere, not even reviewer)
Rejected. The reviewer is structurally different — it judges work done by another agent. Same-agent self-review has known failure modes (positive bias, blind spots).

### Alt-I: Auto-merge after AI reviewer approves (no human gate)
Rejected. The owner's core thesis is "senior engineer over agents" — removing the human merge gate removes the senior engineer from the loop, defeating the project's purpose.

### Alt-J: Permissive PR workflow (agent can commit to main on small changes)
Rejected. The owner explicitly fears scope drift ("exploding code"); without a hard gate, the YAGNI rule erodes.

### Alt-K: Private GitHub repo
Considered. The owner consciously chose Public for dogfooding visibility. Trade-off accepted: messy early state is visible.

### Alt-L: Apache 2.0 or GPL license
Considered. Apache adds patent grant complexity not needed here. GPL's copyleft would discourage adoption. MIT is the cleanest match for "permissive + attribution required + I get reputation gain."

---

## Open questions deferred to future slices

| Question | Deferred to |
|---|---|
| Exact YAGNI/scope-drift detection rules for the reviewer subagent | Slice 7 |
| Which model for reviewer (Opus? stricter-prompted Sonnet?) | Slice 7 |
| Branch protection settings: force-push rules, status checks | Slice 7 |
| Max review-loop count before escalating to human | Slice 7 |
| Whether `/new-feature` is a skill or a custom subagent | Slice 8+ |
| First parallel-prototyper invocation pattern | Slice 5+ |
| Implementer model choice (cheap subagent vs main-context fallback) | Slice 5, decided by observed quality |

---

## References

- Matt Pocock's skills repo: https://github.com/mattpocock/skills
- The slice 1 plan (grill-me install): `~/.claude/plans/hey-before-even-creating-piped-squirrel.md`
- The slice 2 plan (this foundation slice): `~/.claude/plans/slice-2-foundation.md`
- *The Pragmatic Programmer* (Hunt & Thomas) — "The rate of feedback is your speed limit"
