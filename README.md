# project-claude

A clone-as-template starter for AI-coded projects, replicating the workflow of a **senior engineer overseeing a small team of developers** — but with AI agents instead of humans. Built on 20-year-old software engineering practices (small slices, fast feedback, git-tracked changes, PR review, scope discipline) and heavy borrowing from [Matt Pocock's skills repo](https://github.com/mattpocock/skills).

## What's the idea

You play **senior engineer**. AI agents play **the team**. The template ships an autonomous pipeline with **exactly two human-touch points**:

- **Start — `/grill-me`** — the agent interviews you about the idea until both of you share the same picture of what's being built.
- **End — `/qa-plan`** — after every slice of the PRD has merged, the agent produces a human-runnable acceptance checklist. You verify; you sign off.

Everything in between — PRD authoring, slice decomposition, implementation, review, merge — is autonomous, gated by adversarial AI critics rather than per-stage human approval.

The middle is glued together by one command: **`/ship`**. After `/grill-me`, you invoke `/ship` and the pipeline chains `to-prd → prd-critic → slicer → slicer-critic → implementer → reviewer → merge` per slice until the PRD is done. See [ADR-0003](decisions/0003-autonomous-pipeline-with-critics.md) D2 for the 5-stage pipeline and [ADR-0003](decisions/0003-autonomous-pipeline-with-critics.md) D4 for why there are no human gates in the middle.

**Forward queue.** Future-PRD ideas live as `backlog`-labeled GitHub Issues + a "Backlog" column on the project board (per [ADR-0006](decisions/0006-backlog-and-session-continuity.md)). Browse with `gh issue list --label backlog`. Promotion to a PRD: `gh issue edit <N> --remove-label backlog --add-label prd` + `/grill-me #<N>`.

**Session continuity.** New Claude Code sessions reconstruct state from live state (`git log`, `gh issue list`, `gh pr list`, project board) — no formal handoff document. See the "Session continuity" section in [CLAUDE.md](CLAUDE.md) for the canonical procedure.

## Hierarchy — PRD → Slice → PR

Per [ADR-0003](decisions/0003-autonomous-pipeline-with-critics.md) D1, the unit-of-delivery hierarchy is exactly three tiers:

- **PRD** — GitHub Issue (label `prd`). One feature per PRD.
- **Slice** — GitHub sub-issue under the PRD (label `slice`). One INVEST-shaped vertical, fits in one PR.
- **PR** — one merged change, closes one slice via `Closes #<slice-issue>` in the PR body.

No `feature` label, no `slice-N-foo` branch names. Branches use Conventional Commits prefixes — `<type>/<issue-number>-<kebab-summary>`. See [CLAUDE.md](CLAUDE.md) "Hierarchy" and "Operational git workflow" for the full operational logic.

## Adversarial critics

Per [ADR-0003](decisions/0003-autonomous-pipeline-with-critics.md) D2, every generation stage in the pipeline is paired with an adversarial critic running a ≤3-round APPROVE/BLOCK loop. Four critics ship today:

- **`prd-critic`** — gates PRD drafts.
- **`adr-critic`** — gates ADR drafts. Per [ADR-0004](decisions/0004-bypass-prevention.md) D1, when a macro-ADR is drafted alongside a PRD, `prd-critic` and `adr-critic` run as a **joint-APPROVE gate** — both must APPROVE before `/to-prd` posts.
- **`slicer-critic`** — picks best of N=3 slicer decompositions, then iterates.
- **`reviewer`** — gates every PR; auto-merges on APPROVE, returns to implementer on BLOCK, escalates with `needs-human` on round-3 BLOCK.

The loop convention (generator proposes → critic challenges against explicit rubric → generator revises → ≤3 rounds → APPROVE or escalate) is the canonical pattern from [ADR-0003](decisions/0003-autonomous-pipeline-with-critics.md) D2.

## Workflow enforcement

Per [ADR-0004](decisions/0004-bypass-prevention.md) D3, three independent failure-domain defenses prevent the pipeline from being bypassed:

1. **Pre-commit hook** — [`.githooks/pre-commit`](.githooks/pre-commit) checks branch-name regex and refuses commits to `main`. Install with `.githooks/install.sh` (idempotent `git config core.hooksPath .githooks`).
2. **Branch protection R1 + R2** — live on `main`: no direct push (R1), require pull request (R2). R3 (required approving reviews) and R4 (required CI status checks) are deferred to a future PRD that bundles bot identity + GitHub Actions.
3. **Reviewer rule R-CLOSES** — PRs without `Closes #<slice-issue>` referencing a valid `slice`-labeled issue are BLOCKed at review time.

The workflow is no longer "discipline-only convention" — these three layers enforce it mechanically.

## Output-shape standard

The four critics and the output-emitting skills (`slicer`, `qa-plan`, `ship`) conform to a canonical output shape defined in [CLAUDE.md](CLAUDE.md) — see the **"Output-shape standard for subagents and output-emitting skills"** section there for the canonical verdict template and the CRITIC / GENERATOR trailer schemas. Templates are not restated here (DRY per [CLAUDE.md](CLAUDE.md) rule #9). Rationale lives in [ADR-0005](decisions/0005-output-shape-and-slicing-methodology.md) D1.

## Use it

```bash
git clone https://github.com/vojtech-stas/project-claude my-new-project
cd my-new-project
.githooks/install.sh   # one-time: enable the pre-commit hook
# open in Claude Code — CLAUDE.md auto-loads, the agents are oriented
```

Then: `/grill-me` to start a new feature, `/ship` to hand off to the autonomous pipeline, `/qa-plan` to verify when the last slice merges.

## What's inside

- **[CLAUDE.md](CLAUDE.md)** — project rules, auto-loaded by Claude Code every session. Canonical home for the cross-cutting rules, hierarchy, slicing methodology overview, and output-shape standard.
- **[`.claude/skills/`](.claude/skills/)** and **[`.claude/agents/`](.claude/agents/)** — pipeline skills and subagents. See the Map table in [CLAUDE.md](CLAUDE.md) for what lives where.
- **[`decisions/`](decisions/)** — Architecture Decision Records. Five ADRs ship today; see [`decisions/README.md`](decisions/README.md) for the index, conventions, and the strict immutability rule.
- **[`.githooks/`](.githooks/)** — workflow-enforcement pre-commit hook.
- This README.

## Status

Walking-skeleton phase. The pipeline is being built incrementally **on the project itself** — dogfooding from day one. The autonomous loop now ships PRDs end-to-end; `implementer` as a packaged subagent is the next bit of the 5-stage pipeline to land.

## License

MIT — use it, fork it, ship it. A shoutout is appreciated.

## Credits

Inspired by [Matt Pocock's skills repo](https://github.com/mattpocock/skills) and the senior-engineer-over-agents workflow pattern.
