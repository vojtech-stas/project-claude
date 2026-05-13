# Architecture Decision Records (ADRs)

This directory holds the project's design decisions — the *why* behind structural choices that aren't obvious from the code.

## What an ADR is

An ADR captures **one architectural decision** along with the context that drove it, the alternatives that were considered and rejected, and the consequences accepted. Originated in Michael Nygard's *"Documenting Architecture Decisions"* (2011); now standard practice at Spotify, AWS, ThoughtWorks, HashiCorp, Kubernetes, and many open-source projects.

An ADR is a **historical record**, not a living spec. Once accepted, it's frozen at the moment of decision. If the decision is later reversed or refined, a *new* ADR supersedes the old one — the old one is never edited (only its `Status` may flip to `Superseded`).

## Why one file per decision

- **Immutability.** Each ADR is the snapshot of a decision in its moment. Editing it retroactively destroys the audit trail of "what was true *when*."
- **Granular supersession.** A new ADR can supersede *one specific decision* from an older one without invalidating the rest.
- **Git history per decision.** `git log decisions/0042-*.md` tells you exactly when that decision changed and why.
- **Stable links.** PRs, code comments, and CLAUDE.md can link to one specific ADR — the link doesn't rot when an unrelated decision changes.
- **Discoverability.** `ls decisions/` is your changelog — chronological order, decision titles visible.

The unit isn't quite "one tiny decision per file" — it's **one architectural pattern or coherent design move per file**. If a pattern has 5 inter-dependent rules (e.g., "autonomous pipeline with critics" has rules about stages, critics, options, gates, orchestrator), those go in one ADR. If a decision is independent ("use library X over Y for date parsing"), it gets its own ADR.

This project's [ADR-0001](0001-foundational-design.md) (13 decisions in one file) is intentionally a mega-ADR because the decisions were the *foundational set* — they're a coherent pattern, not 13 separate moves. ADR-0002 and ADR-0003 follow the same one-pattern-per-file rule.

## Conventions

- **Filename:** `NNNN-<kebab-case-slug>.md`, sequentially numbered.
- **Status values:** `Proposed`, `Accepted`, `Superseded by ADR-NNNN`, `Deprecated`.
- **Required sections:** Status / Date / Context / Decisions / Consequences / Alternatives considered.
- **Optional sections:** Open questions deferred, Future direction, References.

## When to write an ADR

Heuristic — write one when at least one of these is true:

- The decision was **hard to make** (real trade-offs surfaced; multiple valid paths existed).
- The decision **constrains future work** (other decisions depend on this one).
- A future maintainer would ask **"why did they do it this way?"** without explanation.

Don't write one for trivial choices (naming a variable, picking a CSS color). Those belong in the code or commit message.

## When in the pipeline ADRs are written

Per [ADR-0003](0003-autonomous-pipeline-with-critics.md) D8:

- **Macro-ADRs** — at the `grill-me → to-prd` boundary. The grill session surfaces architectural decisions; `to-prd` drafts both the PRD and any warranted ADRs. They ship together in slice 1 of the implementation.
- **Micro-ADRs** — during implementation. If an implementer hits an unexpected design decision mid-build, it writes an ADR inline with that slice. The `reviewer` subagent enforces.

## Index

| ADR | Title | Status |
|---|---|---|
| [0001](0001-foundational-design.md) | Foundational design | Accepted (D3 and D6 partially superseded by 0003; D9 superseded by 0002) |
| [0002](0002-autonomous-merge-policy.md) | Autonomous merge policy with QA-level human checkpoint | Accepted |
| [0003](0003-autonomous-pipeline-with-critics.md) | Autonomous multi-stage pipeline with adversarial critics | Accepted |
