---
id: "ADR-0003"
status: "accepted"
supersedes:
  - "ADR-0001"
superseded_by: []
scope: "pipeline"
rule_ids:
  - "PIP-002"
  - "PIP-003"
  - "PIP-004"
  - "PIP-005"
---
# ADR-0003: Autonomous multi-stage pipeline with adversarial critics

- **Status:** Accepted
- **Date:** 2026-05-13
- **Extends:** ADR-0002 (autonomous merge policy) — generalizes its implementer-reviewer loop to every generation stage
- **Supersedes:** ADR-0001 D3 (PRDs as repo files) and parts of D6 (slicing convention)
- **Decided in:** Grill session "workflow logic revision" (this conversation)

---

## Context

ADR-0002 established autonomous merge at the PR level: a `reviewer` subagent gates merges via APPROVE/BLOCK loops, with the human checkpoint moved to PRD-completion via `qa-plan`. The implementer-reviewer pair is one adversarial loop in the pipeline.

The owner challenged whether the rest of the pipeline (PRD authoring, slice decomposition) should be similarly autonomous, and pressed on three questions:

1. **Hierarchy.** Our docs say "Slice = INVEST vertical unit, one per PR." Industry research showed our 3-tier "PRD → Feature → Slice" implicitly assumed PRDs span multiple features — the *exception* across mature orgs, not the rule.
2. **Parallelism.** Multiple agent slices in flight risk file conflicts and dependency ordering. We hadn't specified the orchestration.
3. **Autonomy.** Should the pipeline run from grill-me through merge without human gates between stages, relying on adversarial critics for quality?

This ADR resolves those.

---

## Decisions

### D1: Three-tier hierarchy — PRD → Slice → PR

The unit of delivery hierarchy is exactly three tiers:

- **PRD** (GitHub Issue, label `prd`) — one feature-sized deliverable. One PRD = one feature. Multi-feature PRDs are a smell.
- **Slice** (GitHub sub-issue under PRD, label `slice`) — one INVEST-shaped vertical that fits in one PR. Walking-skeleton first; iterate.
- **PR** — one merged change, closes one slice.

Industry research (Linear, Shape Up, Meta, Stripe, GitHub, Atlassian, Google) showed *modal industry shape is 4 tiers* (Initiative → Feature-doc → Story → Atomic change) but with PRD-equivalent always at the *feature* tier, never spanning multiple features. We collapse the Initiative tier — defer until we run ≥2 PRDs in flight. We collapse the Story tier — adopt 3-tier with a strong slicer-critic instead (see D4), since at our slice size (≤300 LoC hard cap) the Story tier adds ritual without quality gain.

**Implications:**
- Drop the `feature` label proposed earlier in this grill. PRD plays that role.
- Reserve GitHub Milestones for *Releases* (groups of merged PRDs), not Features.
- `slice-N-foo` numbering is retired; GitHub issue numbers replace it.

### D2: Five-stage pipeline with critics at every generation stage

```
1. grill-me            [skill, human-in-loop]
2. to-prd + prd-critic [skill + subagent loop, autonomous]
3. slicer + slicer-critic [subagent + subagent loop, autonomous]
4. implementer + reviewer [subagent + subagent loop, autonomous; per slice, parallel]
5. qa-plan             [skill, terminal human checkpoint]
```

Every generation stage is paired with an adversarial critic. The pattern (generator proposes → critic challenges against explicit criteria → generator revises → loop ≤3 rounds → APPROVE or escalate) is the same one ADR-0002 established for implementer-reviewer. We apply it uniformly.

**Critic rubrics:**
- `prd-critic` checks: problem clarity, goal verifiability, non-goals explicit, appetite-vs-scope coherence, rabbit-holes named, open questions surfaced (no hallucinated answers).
- `slicer-critic` checks: INVEST per slice, walking-skeleton-first, SPIDR splitability, no slice violates PRD non-goals, no slice walks into a rabbit-hole, dependency ordering correct.
- `reviewer` (existing): scope compliance, test coverage, conventional commits, ADR consistency, ≤300 LoC cap.

Grounded in: Constitutional AI (Anthropic), Multi-agent debate (Du et al. 2023), Reflexion (Shinn et al. 2023). All show adversarial / self-critique loops materially improve generation quality on hard tasks.

### D3: Multi-option exploration at the slicer stage (N=3)

The slicer subagent generates **three alternative decompositions** of the PRD. The slicer-critic scores all three against the rubric, picks the best with explicit rationale, then iterates on the chosen one.

PRD and implementation stages do *not* use N-option exploration:
- PRD is synthesis from a single grill session — not a branching task.
- Implementation has one right shape per slice; multiplicity creates noise.

Slicing is the right place for N-option exploration because slicing has *many valid decompositions* and the choice between them is the highest-leverage decision in the pipeline.

### D4: No human gates between pipeline stages

The human enters the pipeline at exactly two points:
1. **`grill-me`** — defines what to build (the *what*).
2. **`qa-plan`** — verifies it was built correctly (the *acceptance test*).

Everything in between — PRD authoring, slicing, implementation, review, merge — is fully autonomous. The owner's reasoning:

> *"If the critics and the workflow we have is good enough, we should be able to have human only in the grill me session… I as human will not be able to give proper feedback and figure this out better."*

This is a stronger autonomy posture than ADR-0002 (which kept the human at PRD-completion checkpoint). It generalizes the same principle: humans evaluate the *output* (QA), not each *stage*.

**Risk acknowledged:** compounding errors across stages with no human catch until QA. **Mitigation:**
- Critic loops at every stage shorten the error chain.
- Critic rubrics use explicit criteria (INVEST, SPIDR, non-goals, etc.) not vibes — reduces shared-blind-spot risk between generator and critic.
- Hard cap of 3 critic rounds before escalation prevents infinite ping-pong.
- QA-plan failure is *traceable* — if it fails, we audit which stage produced the bad output and tune that critic.

### D5: Pessimistic locking dropped; merge queue when CI exists

An earlier proposal in the grill session was to declare `Touches: <paths>` on slice issues and refuse to mark dependent slices `ready` if file paths overlapped with in-flight work. Research showed this reinvents pessimistic locking — a pattern Google, Meta, Uber, and Shopify all abandoned ~15 years ago in favor of **optimistic concurrency + a merge queue that rebases-and-retests at the gate.**

We drop the `Touches:` mechanism and the file-conflict refusal logic. Conflict resolution moves to:
- Git's native merge mechanism when slices touch overlapping files (`reviewer` BLOCKs on non-trivial conflicts).
- **GitHub's native merge queue**, enabled when branch protection is turned on (slice 7+).

Until merge queue exists, the orchestrator's only job is `Depends on:` promotion — promote `slice:blocked → slice:ready` when listed dependencies close. Single state predicate, no file-overlap logic.

### D6: Skills for human-facing stages, subagents for autonomous stages

| Pipeline piece | Type | Why |
|---|---|---|
| `grill-me`, `to-prd`, `qa-plan`, `/ship` | Skill | Need main agent context — conversation history, user interaction |
| `prd-critic`, `slicer`, `slicer-critic`, `implementer`, `reviewer` | Subagent | Clean input → output contract benefits from isolated context, narrow tools, focused prompt |

The principle: skill = lives in the conversation; subagent = isolated worker. Skills consume context; subagents don't.

### D7: `/ship` orchestrator skill (lightweight, version 1)

A meta-skill `/ship` chains the autonomous stages. The human invokes it once after `/grill-me` and it runs the rest:

```
/ship → to-prd → prd-critic loop → post PRD
      → slicer (N=3) → slicer-critic → post slices
      → (per slice, parallel) implementer → reviewer → merge
      → qa-plan
```

`/ship` is a skill, not a subagent — it needs to invoke other agents. Initial version is sequential through stages 2-3, then dispatches stage 4 in parallel. Step (5) ends with the qa-plan output handed back to the human.

A persistent orchestrator daemon (loop agent or GitHub Action) is deferred. `/ship` is sufficient until we run multiple PRDs concurrently.

### D8: ADR-writing happens in two places in the pipeline

- **Macro-ADRs** — at the `grill-me → to-prd` boundary. The `to-prd` skill, when synthesizing the PRD, also drafts any ADRs the grill session warrants. `prd-critic` reviews both. They ship together in slice 1 of the implementation.
- **Micro-ADRs** — during implementation. If a slice's implementer hits an unexpected design decision, it writes an ADR inline with that slice. `reviewer` checks: "decision worth preserving? If yes, ADR exists?"

Heuristic for "ADR warranted": (a) the decision was hard to make (real trade-offs surfaced), (b) it constrains future work, or (c) future maintainers would ask "why?" If none → no ADR. Trivial features don't need them.

---

## Consequences

### Positive

- **End-to-end autonomy.** Two human commands per feature: `/grill-me`, then `/ship`. Throughput dominated by AI, not human availability.
- **Quality through adversarial loops.** Critics at every generation stage catch issues before they cascade.
- **Industry-aligned hierarchy.** PRD-as-feature matches Linear / Shape Up / Meta / Stripe; merge-queue conflict resolution matches Google / Meta / Uber / Shopify.
- **Forces critic rubric quality.** A bad critic means bad merges; that pressure surfaces rubric flaws early.
- **Single source of truth per artifact.** PRD on GitHub, slices on GitHub, ADRs in repo, no duplication.

### Negative / accepted trade-offs

- **Token cost.** N=3 slicer generations × ≤3 critic rounds + ≤3 prd-critic rounds + reviewer loops = significant per-PRD cost. Worth it for autonomy; budget it.
- **Compounding-error risk.** Bad PRD → bad slices → bad impl; no human catches it until QA-plan. Accepted because (a) critics shorten the chain, (b) QA-plan is traceable, (c) reverts are cheap.
- **Critic blind spots.** Generator and critic share the same model; may share blind spots. Mitigation: explicit rubric criteria (not vibes), and future direction (D9) of ensemble critics with different models.
- **Bootstrap cost.** Building the full pipeline (prd-critic, slicer, slicer-critic, implementer, /ship) is several slices of work before we get end-to-end autonomy. Accepted — first slice establishes ADR + CLAUDE.md only, subsequent slices flesh out each pipeline piece.
- **`grill-me` dominates.** Pipeline quality is gated by grill-me quality. The owner must invest in grilling well; the pipeline will faithfully execute even a flawed problem statement.

---

## Alternatives considered

### Alt-A: Keep 3-tier hierarchy with "Feature" as a parent Issue (earlier grill proposal)
Rejected. With PRD = Feature established, the `feature` parent Issue becomes redundant — the PRD plays that role. Simpler and matches industry standard ("one PRD = one feature").

### Alt-B: 4-tier hierarchy (PRD → Story → Slice → PR)
Rejected for now. Pro: sharper slicer input (story-scoped); richer "why" context for implementers; clean per-story QA-plan trigger. Con: at our slice size (≤300 LoC) the story tier adds ritual without quality gain. The slicer-critic already does the work the story tier would do. Revisit if dogfooding shows slices regularly exceed cap or implementer struggles with size.

### Alt-C: Human gates between every stage
Rejected. The owner's stated preference is "human only at grill-me and QA." Per-stage human gates re-introduce the bottleneck ADR-0002 explicitly removed. The critic pattern is the autonomous substitute for human review.

### Alt-D: Human gate after PRD only (my own initial recommendation)
Rejected by the owner in favor of full autonomy after grill-me. Honest trade-off: cheaper insurance against PRD hallucination, but contradicts the autonomy thesis. Owner is explicit that the critic loop must be strong enough that human review wouldn't add value — and that if critic quality is insufficient, the right fix is better critics, not human gates.

### Alt-E: Pessimistic file-conflict refusal (declared `Touches:` paths)
Rejected. Reinvents pessimistic locking; industry abandoned this 15 years ago. Optimistic concurrency + merge queue is strictly more correct because the queue retests post-merge state, catching semantic conflicts that file-path overlap misses.

### Alt-F: Orchestrator as a long-running loop agent or GitHub Action (rather than `/ship` skill)
Considered for the future. Deferred until we run multiple PRDs concurrently. `/ship` is sufficient for the v1 case where the human runs one PRD at a time.

### Alt-G: Single-shot slicing (no N-alternative exploration)
Rejected. Slicing has many valid decompositions; comparing them surfaces tradeoffs the critic can articulate ("decomposition #2 isolates the risky integration in slice 1"). Cost is bounded; benefit is large. Industry analog: AlphaCode's N-solution generation + filtering.

---

## Open questions deferred

| Question | Deferred to |
|---|---|
| Exact N for slicer alternatives (initial: 3) | Tune after first 3 real slicer runs |
| Critic-loop max rounds per stage (initial: 3, matches reviewer) | Tune after dogfooding |
| Whether `prd-critic` and `slicer-critic` should run on different models than their generators (cross-model adversarial) | Slice 7+ when ensemble pattern is implemented |
| Whether `/ship` should parallelize implementer subagents from slice 1 or roll out parallelism gradually | First multi-slice PRD |
| Whether macro-ADRs should be drafted by `to-prd` skill itself or by a separate `to-adr` skill invoked alongside | Decide after the first auto-PRD-with-ADR run |
| Whether `qa-plan` should run automatically when all slices merge, or only on human invocation | Decide after first auto-PRD ships |
| When to upgrade `/ship` skill to a persistent orchestrator (loop or GitHub Action) | When ≥2 PRDs run concurrently |

---

## Future direction: ensemble critics

ADR-0002 already flagged multi-reviewer ensembles (different models, same prompt) as a post-MVP direction. This ADR generalizes that: **ensemble critics at any generation stage**, not just reviewer. For high-stakes PRDs or contentious slicing decisions, run N critics in parallel (e.g., Opus + Sonnet + Haiku), require unanimous APPROVE for autonomous progression, escalate to human on split verdict.

Same pattern as ADR-0002's reviewer ensemble. Same cost/benefit logic — cheap insurance for high-stakes work, overkill for routine work, applied selectively via a label like `requires-ensemble`.

Trigger to build: same as ADR-0002 — after the single-critic flow has shipped several PRDs and we have evidence about where the single-critic loop fails.

---

## References

- [ADR-0001](0001-foundational-design.md) — foundational design; D3 (PRDs as repo files) superseded, D6 (slicing) refined
- [ADR-0002](0002-autonomous-merge-policy.md) — autonomous merge at PR level; this ADR generalizes its loop to every stage
- Grill session "workflow logic revision" — this conversation
- Industry research: [Linear hierarchy](https://linear.app/docs/initiatives), [Shape Up pitch structure](https://basecamp.com/shapeup/1.5-chapter-06), [Atlassian PRD template](https://www.atlassian.com/software/confluence/templates/product-requirements), [Google design docs](https://www.industrialempathy.com/posts/design-docs-at-google/), [Lenny's PRD template](https://www.lennysnewsletter.com/p/prds-1-pagers-examples), [Shopify merge queue](https://shopify.engineering/successfully-merging-work-1000-developers), [Uber SubmitQueue](https://www.uber.com/blog/research/keeping-master-green-at-scale/), [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/), [Tim Pope on commits](https://cbea.ms/git-commit/), [Trunk-Based Development](https://trunkbaseddevelopment.com/), [Constitutional AI (Anthropic)](https://www.anthropic.com/research/constitutional-ai-harmlessness-from-ai-feedback), [Multi-agent debate (Du et al. 2023)](https://arxiv.org/abs/2305.14325), [Reflexion (Shinn et al. 2023)](https://arxiv.org/abs/2303.11366), [SPIDR (Mike Cohn)](https://www.mountaingoatsoftware.com/blog/five-simple-but-powerful-ways-to-split-user-stories)
- [`.claude/skills/to-prd/SKILL.md`](../.claude/skills/to-prd/SKILL.md) — to be updated per D2 / D6
- [`.claude/skills/to-issues/SKILL.md`](../.claude/skills/to-issues/SKILL.md) — to be replaced by `slicer` + `slicer-critic` subagents per D2
- [`.claude/agents/reviewer.md`](../.claude/agents/reviewer.md) — existing implementer-reviewer loop is the template for D2
