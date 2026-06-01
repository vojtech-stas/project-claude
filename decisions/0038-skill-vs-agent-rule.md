# ADR-0038: Skill-vs-agent decision rule (the orchestration primitives)

- **Status:** Accepted
- **Date:** 2026-06-01
- **Extends:** [ADR-0010](0010-implementer-subagent-auto-pipeline.md) D6 (subagent tool boundaries — the hard constraint this rule formalizes), [ADR-0003](0003-autonomous-pipeline-with-critics.md) D1 (the pipeline). Honors [ADR-0008](0008-workflow-autolog-bootstrap-and-naming.md) D7 (no new critic).
- **Supersedes:** [ADR-0014](0014-skill-local-vocabulary-and-auto-fold.md) D2 (which created `/glossary-fold` as a standalone skill) and [ADR-0007](0007-vocabulary-glossary-and-grill-me-extension.md) D4 (which created `/glossary-add` as a standalone skill) — D3 below merges both standalone-skill identities into one `/glossary` skill with `add`|`fold` subcommands. (Resolves [ADR-0032](0032-workflow-only-architecture.md) Open-Question-7, which asked whether `glossary-add`+`glossary-fold` should be retired, in the affirmative-via-consolidation. [ADR-0012](0012-glossary-consolidation-single-tier.md) D3 simplified `/glossary-add`'s write path but did not mandate its separateness, so it is not superseded — its simplification carries into the `add` subcommand.)

## Context

The project has 11 skills and 9 subagents, but **no written rule for when a capability should be a skill vs a subagent**. A dogfooding question (2026-06-01) surfaced the gap: "I'm not sure how to decide what should be a skill and what an agent — and skills spawning agents seems like weird logic." Without a rule, the boundary is decided ad-hoc per feature, and the surface drifts (e.g. two glossary skills for one concern; recurring uncertainty about qa-plan/qa-tester).

The "weird logic" reflects a real but *forced* constraint of the Claude Code runtime, which this ADR makes explicit:

- **Only the MAIN agent can dispatch subagents** (the Agent/Task tool). Subagents run in isolated contexts with restricted tool sets and, per [ADR-0010](0010-implementer-subagent-auto-pipeline.md) D6, **cannot dispatch further subagents** (no Agent tool — security-critical).
- A **skill** is not a process; it is a playbook the main agent *loads and executes in its own context*. Therefore **all orchestration — dispatching, looping, deciding — must live in skills** (the main agent's procedures). "A skill spawns an agent" = "the orchestrator's playbook delegates a bounded task to an isolated worker" — and the playbook is the *only* place a dispatch can live. The pattern is not weird; it is the only consistent model the runtime allows.

## Decisions

### D1: The skill-vs-agent decision rule

A capability is a **SUBAGENT** when it needs its **own isolated context** AND is **handed a task and returns a result**. Three justifying reasons to isolate:
1. **Heavy/long work** that would bloat the main agent's context window (e.g. `implementer` writing code, `slicer` generating N=3 decompositions).
2. **Adversarial review that must NOT share the orchestrator's context** — every critic. A critic that could see the context that produced the artifact it judges is compromised; isolation is load-bearing for honest review.
3. **Parallel work** (per [ADR-0036](0036-worktree-isolation-all-dispatches.md), isolated worktrees).

A capability is a **SKILL** when it is the **orchestrator's own procedure** — *interactive* (asks the user via `AskUserQuestion`), *orchestrating* (dispatches subagents, loops, makes decisions), or a *multi-step playbook* the main agent runs. Skills are "the verbs the orchestrator knows."

**Litmus:** isolated-context + handed-a-task + returns-a-result → **subagent**; the-orchestrator's-own-interactive-or-orchestrating-procedure → **skill**. A capability that *needs to ask the user* cannot be a subagent (subagents have no `AskUserQuestion`); a capability that *needs to dispatch other subagents* must be a skill (only the main agent dispatches).

### D2: "Skills dispatch subagents" is the intended topology, not an anti-pattern

It follows directly from D1 + the runtime constraint: orchestration lives in skills; isolated/bounded/adversarial work lives in subagents; so skills dispatch subagents. The orchestration graph is therefore: **orchestrator → skills (its playbooks) → subagents (delegated workers)**. This is documented as the canonical shape (and is what the dashboard topology + README pipeline diagram render). A subagent never dispatching a subagent (ADR-0010 D6) is the dual guarantee that keeps the graph a 2-level-from-orchestrator tree of skills, not an arbitrary mesh.

### D3: Apply the rule — the one consolidation it flags

Auditing the current 11 skills + 9 subagents against D1: **all conform except one redundancy** — `glossary-add` (interactive single entry) and `glossary-fold` (bulk fold) are two *skills* (two playbooks) for one concern. The rule does not split them by skill-vs-agent (both are correctly skills); the redundancy is two-playbooks-one-concern, resolved by **merging them into one `/glossary` skill with `add` | `fold` subcommands** (mirroring the [ADR-0017](0017-audit-meta-consolidation.md) `/audit-meta` subcommand precedent). All other pairs are correct per D1: `/qa-plan` (interactive skill: asks the user about JUDGMENT criteria) + `qa-tester` (isolated mechanical executor subagent); `/glossary` + `glossary-critic` (interactive skill + adversarial isolated critic); `/to-prd` + `/to-issues` (two distinct sequential orchestrator procedures); every critic isolated. No skill should become a subagent and no subagent a skill.

### D4: `/audit-subagents` gains a skill-vs-agent placement check (advisory)

So the rule stays enforced going forward, `/audit-subagents` (the mechanical subagent-quality auditor) gains an advisory check: flag any subagent whose body implies it needs `AskUserQuestion` or dispatches subagents (a skill-vs-agent misplacement per D1). Advisory (WARN), mechanical, no new critic — consistent with [ADR-0011](0011-subagent-quality-framework.md).

### D5: Bootstrap-mode (per [ADR-0004](0004-bypass-prevention.md) D2)

The rule binds FORWARD from merge: it governs new capabilities and the D3 consolidation; it does not force a retroactive re-shaping of conformant existing capabilities (they already conform). Mirrors [ADR-0036](0036-worktree-isolation-all-dispatches.md) D5.

## Consequences

**Positive:**
- A one-line litmus for every future "skill or agent?" decision — removes the ad-hoc boundary that caused the drift.
- Demystifies "skills spawn agents" as the forced, correct model — not an accident.
- Trims one redundant skill (glossary 2→1) and gives `/audit-subagents` a forward guard.

**Negative:**
- The glossary merge is a small refactor touching the two skill bodies + `glossary-critic` + `/ship`/`/build`/CLAUDE.md refs.

**Neutral:**
- No new critic (D4 extends the existing `/audit-subagents`), no new dependency. The rule formalizes existing practice; only the glossary consolidation changes behavior.

## Alternatives considered

- **Alt-A (chosen): write the rule + apply it (merge glossary, keep the rest).** Principled, minimal churn.
- **Alt-B: leave it undocumented (status quo).** Rejected: the boundary keeps getting re-litigated; surface drifts.
- **Alt-C: radically re-shape orchestration (fewer/fatter agents).** Rejected: fights the runtime constraint (agents can't dispatch agents; only the main agent orchestrates) — any redesign re-derives skills-spawn-agents at higher cost.
- **Alt-D: merge to-prd+to-issues and/or qa-plan+qa-tester too.** Rejected: the rule says they're correctly split (distinct stages; interactive-skill + isolated-executor) — merging would violate single-responsibility or fuse interactive + isolated concerns.

## References
- [ADR-0010](0010-implementer-subagent-auto-pipeline.md) D6 (subagent tool boundaries — the constraint), [ADR-0003](0003-autonomous-pipeline-with-critics.md) (pipeline), [ADR-0008](0008-workflow-autolog-bootstrap-and-naming.md) D7 (no new critic), [ADR-0011](0011-subagent-quality-framework.md) (/audit-subagents framework — D4 extends), [ADR-0017](0017-audit-meta-consolidation.md) (subcommand-consolidation precedent for the glossary merge).
- **Superseded D-IDs:** [ADR-0014](0014-skill-local-vocabulary-and-auto-fold.md) D2 (created `/glossary-fold`), [ADR-0007](0007-vocabulary-glossary-and-grill-me-extension.md) D4 (created `/glossary-add`); [ADR-0012](0012-glossary-consolidation-single-tier.md) D3 (simplified `/glossary-add`, NOT superseded — carries into the `add` subcommand); [ADR-0032](0032-workflow-only-architecture.md) OQ-7 (resolved affirmatively-via-consolidation).
- [ADR-0036](0036-worktree-isolation-all-dispatches.md) D5 (bootstrap shape), [ADR-0004](0004-bypass-prevention.md) D2 (bootstrap-mode).
- 2026-06-01 dogfood: "not sure what should be a skill vs agent; skills spawning agents seems weird."
