---
id: "ADR-0007"
status: "accepted"
supersedes: []
superseded_by: []
scope: "glossary"
rule_ids:
  - "GLO-001"
  - "GLO-002"
---
# ADR-0007: Universal vocabulary mechanism — two-tier glossary + /grill-me extension

- **Status:** Accepted
- **Date:** 2026-05-15
- **Extends:** [ADR-0001](0001-foundational-design.md) D8 (orientation artifacts); [ADR-0005](0005-output-shape-and-slicing-methodology.md) D2 (authority-citation pattern); [ADR-0006](0006-backlog-and-session-continuity.md) D4 (write convention pattern)
- **Supersedes:** none

## Context

AI agents in this project (main Claude; subagents `reviewer`, `prd-critic`, `adr-critic`, `slicer`, `slicer-critic`) and the human user lack a shared, anchored vocabulary. Terms like "slice", "critic", "trivial", "session" carry narrowed project-specific meanings; without anchoring, agents drift toward common meanings. The user explicitly named this during the PRD-vocabulary grill: *"I would like to create some universal language for ai, domain expert and for me that we agree upon."*

The naive solution — a single `GLOSSARY.md` file at repo root, read on session start — was initially considered (grill Q2=2A) but revised mid-grill (Q6=6B) when the user spotted a load-mechanism flaw: *"I am afraid that the ai will not read it everytime."* Investigation confirmed that only `CLAUDE.md` is genuinely auto-loaded by the Claude Code runtime; any "auto-load `GLOSSARY.md`" pattern reduces to either (a) a `CLAUDE.md` instruction the agent must follow (still agent-discipline-dependent) or (b) on-demand reads (worse).

The work this ADR enables is the **first** themed PRD in a two-PRD sequence (grill Q1=1B). The second themed PRD (PRD-workflow — bootstrap.sh, auto-log-to-backlog) is queued separately and out of scope here.

## Decisions

### D1: Two-tier glossary location

The glossary lives in two tiers:
- **Key-zone (auto-loaded):** a `## Glossary (key terms)` section INSIDE `CLAUDE.md`. Capped at ~25 entries. Guaranteed loaded by the runtime on every session.
- **Long-tail (on-demand):** `GLOSSARY.md` at repo root. Read by agents when an unfamiliar term comes up.

Rationale: only `CLAUDE.md` is genuinely auto-loaded by the runtime. Putting the load-bearing vocabulary IN `CLAUDE.md` eliminates the agent-discipline-reliance failure mode the user identified. The cap prevents `CLAUDE.md` bloat; the long-tail in a separate file scales without paying the always-loaded context tax.

### D2: Entry shape

Each glossary entry follows the shape: term + one-sentence definition + authority + see-also.

- **Authority** cites either `ADR-NNNN D-X` (project decision), an external URL (named external source), or the literal string `external` (industry-standard term with no project-specific authority).
- **See-also** lists related glossary terms (zero or more).

Rationale: the authority field anchors every term to its source-of-truth. The glossary becomes a TOC into the decision record, not a competing source. Without authority, the glossary would inevitably drift from the ADRs.

### D3: Scope rule — three inclusion categories

A term qualifies for the glossary if and only if it falls into one of:
- **(a) Project jargon coined here** — examples: PRD, slice, walking-skeleton, R-LOC, cascade-doc check, joint-APPROVE gate.
- **(b) External standards adopted** — examples: INVEST, SPIDR, hamburger method, ADR, Conventional Commits.
- **(c) Common words with narrowed meaning here** — examples: slice (vs general "piece"), critic (vs general "reviewer"), trivial (vs casual meaning), session (vs general "meeting").

Category (c) is the highest-leverage — disambiguation of words an agent *thinks* it already knows. Pure industry background ("TypeScript", "CI" if used with its standard meaning) is NOT glossary-worthy unless it falls under (c).

### D4: Write path — skill + discretionary agent surfacing

Two paths land terms in the glossary:
- **Explicit:** `/glossary-add` skill — user-driven; interactive single-term flow. Prompts for term, definition, scope category (a/b/c per D3), authority, zone (default long-tail; `--key` for key-zone). Opens a `hotfix/glossary-<term>` PR with the `trivial` label.
- **Discretionary surfacing:** subagents and skills get a 1-line prompt clause encouraging them to inline a one-line suggestion (*"Heads up: 'X' looks glossary-worthy — run `/glossary-add` to capture"*) when they encounter glossary-worthy terms in their work.

Mirrors [ADR-0006](0006-backlog-and-session-continuity.md) D4 backlog convention exactly: explicit channel for batch/deliberate capture; discretionary nudge for what the user would otherwise miss. Surfacing is non-mandatory — agents that don't surface are not non-compliant.

### D5: `glossary-critic` subagent — 5th critic

A new subagent `glossary-critic` provides adversarial scope check on glossary edits. Invoked by `/glossary-add` directly, and by `reviewer` when a PR's diff includes `GLOSSARY.md` or the `## Glossary (key terms)` section of `CLAUDE.md`. Outputs the canonical 5-section verdict + CRITIC trailer per [ADR-0005](0005-output-shape-and-slicing-methodology.md) D1.

Rubric:
1. Scope category (a/b/c per D3) — PASS if entry fits exactly one category; BLOCK if entry is "industry background" or fits no category.
2. No duplicate — PASS if grep against `CLAUDE.md` key-zone + `GLOSSARY.md` returns no existing entry for this term.
3. Definition quality — PASS if one declarative sentence; BLOCK if multi-sentence, vague, or tutorial-shaped.
4. Authority field present — PASS if cites `ADR-NNNN D-X`, external URL, or literal `external`; BLOCK if empty or malformed.

≤3-round APPROVE/BLOCK loop with I5 escalation on round-3 BLOCK (mirrors `prd-critic`/`adr-critic`/`slicer-critic` contract per [ADR-0004](0004-bypass-prevention.md) D1).

Rationale: the agent that wants to add a term cannot validate it adversarially (the failure mode behind grill Q10's rejection of in-skill self-check). The pattern of "dedicated critic per generation stage" ([ADR-0003](0003-autonomous-pipeline-with-critics.md) D2) extends naturally. Glossary edits are routine enough to deserve a fast, specialized critic rather than absorbing scope-judgment into `reviewer`'s heterogeneous rubric.

### D6: `/grill-me` gains optional doc-path argument

`/grill-me <path>` reads `<path>` before asking Q1 (matt-pocock-style external doc loading for grill sessions about an existing spec). No-arg behavior is unchanged (full backward compatibility). Single optional path; not multi-doc, not config-file, not URL.

If the path doesn't exist or isn't a readable file, `/grill-me` reports the error and proceeds in no-arg mode rather than aborting.

Rationale: named in the user's opening ask. Minimal extension. Multi-doc and config-file approaches are speculative beyond the single-path use case; both can be added later via additive extension if demand emerges.

### D7: Bootstrap-mode acknowledgment (per ADR-0004 D2)

D4 surfacing convention and D5 critic enforcement bind FORWARD from the slice that ships them. Earlier slices/PRDs are grandfathered — neither retroactive prompt-edit sweeps nor retroactive `glossary-critic` verdicts apply.

Bootstrap-mode applicable for D4 surfacing convention: `/grill-me`, `slicer`, `slicer-critic`, `prd-critic`, `adr-critic`, `reviewer`, `qa-plan`, `glossary-critic` itself, and main Claude. Each gets the 1-line convention clause via the slice that touches its prompt; no retroactive sweep across pre-existing prompts. (Some of these prompts are touched in the same slice that adds D5; others come in subsequent slices or future PRDs.)

Bootstrap-mode applicable for D5 critic enforcement: `glossary-critic` validates glossary edits from PRD-vocabulary slice 1 forward. Pre-existing scattered "glossary-like" content in `CLAUDE.md` (the Map table, the rule definitions, the I1–I5 list) is NOT subject to `glossary-critic` review — those are different artifacts with their own rubrics (`reviewer`'s R-META etc.).

The `CLAUDE.md` ~25-entry cap (D1) is `reviewer`-enforced from the slice that ships the cap onward; existing `CLAUDE.md` content is not retroactively assessed against the cap.

## Consequences

**Positive:**
- Shared vocabulary anchored in `CLAUDE.md` (auto-loaded) eliminates the *"AI might not read it"* failure mode for load-bearing terms.
- Authority field (D2) forces every entry to cite a source-of-truth — no glossary/ADR drift.
- Scope rule (D3) gives `/glossary-add` and `glossary-critic` a defensible inclusion test; mechanically grep-able for the ≥2-citation criterion used in the backfill slice.
- `/glossary-add` + `glossary-critic` mirror the existing skill/critic pattern; new contributors recognize the shape.
- `/grill-me` doc-path extension (D6) solves the matt-pocock use case named by the user without architectural disruption.

**Negative:**
- The critic count grows to 5 (`reviewer`, `prd-critic`, `adr-critic`, `slicer-critic`, `glossary-critic`). Each new critic dilutes the focus of the pattern; a 6th would warrant explicit pushback.
- `CLAUDE.md` grows by ~30-50 lines (Glossary section header + ~25 entries); the already-large file becomes larger.
- Promotion/demotion between zones requires deliberate slice-ceremony (no auto-shuffle); the ~25-entry cap may force demotion decisions that feel arbitrary at the boundary.
- The ≥2-citation backfill criterion is a heuristic; some genuinely-load-bearing terms cited only once will be missed and need separate addition.

**Neutral:**
- Backward compatibility on `/grill-me` is preserved (D6 is purely additive).
- No external dependencies introduced.
- No CI / branch-protection / git-hook changes (those are deferred to PRD-workflow).

## Alternatives considered

- **Alt-A: Single `GLOSSARY.md` at root, no `CLAUDE.md` zone.** Rejected per the user's stated concern (*"AI might not read it every time"*); separate-file approaches reduce to agent-discipline reliance.
- **Alt-B: All vocabulary inlined in `CLAUDE.md`, no separate file.** Rejected on bloat grounds; doesn't scale past ~50 terms.
- **Alt-C: `CLAUDE.md` containing a "READ `GLOSSARY.md` BEFORE RESPONDING" instruction.** Rejected as fake auto-load; still on-demand with louder nagging.
- **Alt-D: `reviewer` extension (`R-GLOSSARY` rule) instead of dedicated `glossary-critic`.** Rejected per grill Q10=10C on adversarial-pressure grounds — `reviewer`'s rubric is mixed; the glossary scope check deserves a dedicated specialized critic with separate context.
- **Alt-E: Multi-doc or config-file approach for `/grill-me`.** Rejected as speculative beyond the single-path use case; YAGNI.
- **Alt-F: Auto-promote/demote terms between zones based on usage statistics.** Rejected as machinery for a non-problem; deliberate slice-ceremony promotion is fine.
- **Alt-G: Bidirectional cross-references (ADRs link to glossary terms).** Rejected on maintenance-burden grounds; forward-only via D2 authority field is sufficient.
- **Alt-H: Dedicated `/glossary-add` skill with NO `glossary-critic` (just in-skill validation).** Rejected per grill Q10=10C — same agent that wants to add cannot validate adversarially.

## Open questions deferred

- Whether the `CLAUDE.md` key-zone cap should ultimately be hard-coded at 25, parametric, or float with the project. Bootstrap-mode policy permits future revision via a superseding ADR.
- Whether `glossary-critic` should ALSO validate entries on every `reviewer` pass that touches `CLAUDE.md` (catches accidental edits to the glossary section). Currently it triggers only when a PR's diff includes `GLOSSARY.md` or the `## Glossary (key terms)` section; the trigger condition may need refinement once edit patterns emerge.
- Whether multi-doc args for `/grill-me` will eventually be demanded; tracked via D6 + the user's opening ask. Not blocked here.

## Future direction

- If glossary churn turns out to be high (>20 entries added per quarter), promote `glossary-critic`'s heuristic checks (duplicate detection, format check) into the `/glossary-add` skill itself to reduce critic round-trips. Bootstrap-mode policy supports such a refinement via a superseding ADR.
- If `/grill-me <path>` proves useful, extend to multi-doc args via an additive change (no breaking).
- If the ≥2-citation backfill criterion proves too narrow, supersede the rule with a new ADR — do not retrofit ADR-0007.

## References

- [ADR-0001](0001-foundational-design.md) D8 — orientation artifacts (this ADR adds a new orientation artifact)
- [ADR-0003](0003-autonomous-pipeline-with-critics.md) D2 (critic per generation stage — pattern this D5 extends); D8 (ADR placement at grill→PRD boundary — why this ADR is drafted alongside PRD-vocabulary)
- [ADR-0004](0004-bypass-prevention.md) D1 (joint critic gate — pattern this D5 follows); D2 (bootstrap-mode policy — D7 mirrors this)
- [ADR-0005](0005-output-shape-and-slicing-methodology.md) D1 (canonical critic verdict template + CRITIC trailer — D5 conforms); D2 (canonical home of methodology depth — authority-citation pattern in D2 mirrors this); D3 (cascade-doc check — slicer-relevant)
- [ADR-0006](0006-backlog-and-session-continuity.md) D4 (write convention pattern — D4 mirrors this)
- Grill session: PRD-vocabulary Q1–Q12 (2026-05-15)
