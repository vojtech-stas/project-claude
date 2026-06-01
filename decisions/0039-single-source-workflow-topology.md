# ADR-0039: Single-source workflow topology (one spec, two renders, one measured overlay)

- **Status:** Accepted
- **Date:** 2026-06-01
- **Extends:** [ADR-0034](0034-build-orchestrator-and-generated-docs.md) D4/D7 (the README-template + `--generate-readme` generator this routes the diagram through), [ADR-0033](0033-tooling-spawn-hook-scope.md) D4 (`dashboard/*` non-runtime). Honors [ADR-0008](0008-workflow-autolog-bootstrap-and-naming.md) D7 (no new critic).
- **Supersedes:** none.

## Context

The project's workflow topology exists in **three hand-maintained representations that drift**:
1. the **pipeline mermaid diagram** — prose in `README.md` (hand-written);
2. the **dashboard topology** — a hardcoded `DISPATCH_MAP` JS constant in `dashboard/index.html`;
3. the **actual runtime** — what `/ship`/`/build` + the agents really dispatch.

A 2026-06-01 dogfood found (1) and (2) disagreeing. Repairing the drift each time is whack-a-mole; the user's ask: a single source so they "always reflect current state." Grill decision (Q1): **one declared spec that both the README mermaid AND the dashboard topology are generated from, PLUS a live "measured" overlay derived from real events so declared-vs-actual drift is visible.**

## Decisions

### D1: A single declared pipeline spec is the canonical source for the topology

One machine-readable spec (a structured object — e.g. a `PIPELINE` dict in `dashboard/server.py`, served at `/api/pipeline`) declares the orchestration topology: `orchestrator → skills → the subagents each dispatches` (the `DISPATCH_MAP` content, promoted to the single source). It is the **one place** the topology is hand-edited. Implementer chooses the exact location/format (server-side dict served via an endpoint is the recommended shape, so both the dashboard and the README generator read the same structure).

### D2: Both the README mermaid and the dashboard topology are GENERATED from the spec

- The **README** pipeline diagram is generated from the spec by `dashboard/server.py --generate-readme` ([ADR-0034](0034-build-orchestrator-and-generated-docs.md) D7) — a `{{GENERATED:pipeline-diagram}}` placeholder rendered to mermaid from the spec, so the README diagram can never disagree with the spec.
- The **dashboard** Architecture topology renders from the same spec (replacing the hardcoded `DISPATCH_MAP` — the dashboard fetches the spec instead of embedding a copy).

One edit to the spec updates **both** renders. The diagram↔dashboard drift (the reported defect) is structurally eliminated: there is only one declared copy.

### D3: A live "measured" overlay surfaces declared-vs-actual drift

The dashboard derives a SECOND, "measured" topology from real `skill_invoke`→`agent_complete` events in the log (the Phase-2 capture), shown alongside the declared topology (e.g. a toggle, or measured edges highlighted on the declared graph). Where the measured flow diverges from the declared spec — a skill that dispatched an agent the spec doesn't list, or vice-versa — the dashboard flags it. This makes "reflects current state" *verifiable*, not just *asserted*: the declared spec is intent; the measured overlay is reality; visible drift between them is the signal to update the spec. When no measured events exist (fresh log), the overlay is empty and only the declared topology shows (graceful).

### D4: Bootstrap-mode (per [ADR-0004](0004-bypass-prevention.md) D2)

Binds forward from merge. The spec becomes canonical at merge; the README diagram + dashboard topology regenerate from it thereafter. No retroactive sweep (there are no other copies to migrate — the two existing renders are replaced, not duplicated).

## Consequences

**Positive:**
- The diagram↔dashboard drift is eliminated by construction (one declared copy, two generated renders).
- The measured overlay makes declared-vs-actual drift *visible* — the deeper "always reflects current state" guarantee, since reality is shown, not assumed.
- No new hand-maintained artifact (it removes one — the duplicate DISPATCH_MAP/diagram pair becomes one spec).

**Negative:**
- The spec is still hand-edited (intent must be kept current) — but in ONE place, and the measured overlay flags when it lags reality.
- The measured overlay depends on `skill_invoke` capture (forward-only; the unverified Skill matcher, #430) — it degrades to empty gracefully (D3).

**Neutral:**
- All changes are `dashboard/*` + the README generator/template ([ADR-0033](0033-tooling-spawn-hook-scope.md) D4 non-runtime; [ADR-0034](0034-build-orchestrator-and-generated-docs.md) generated-docs). No new critic, no new dependency, no runtime-artifact change.

## Alternatives considered

- **Alt-A (chosen): one declared spec → both renders + a measured overlay.** Kills the structural drift immediately and surfaces declared-vs-actual.
- **Alt-B: pure measured (auto-derive everything from events).** Rejected (grill): needs real event data (forward-only/empty on fresh clone); the README is a static doc so it still needs generation from a snapshot; a half-run shows a partial graph.
- **Alt-C: make DISPATCH_MAP the source, generate the README from it (no measured overlay).** Rejected as incomplete: kills diagram↔dashboard drift but never shows reality — the spec can still be aspirational. (It is effectively D1+D2 without D3; D3 is the part that makes "reflects current state" verifiable.)

## References

- 2026-06-01 dogfood (diagram↔topology drift). Grill Q1 (declared spec → both + measured overlay).
- [ADR-0034](0034-build-orchestrator-and-generated-docs.md) D4 (README template), D7 (`--generate-readme` generator), [ADR-0033](0033-tooling-spawn-hook-scope.md) D4 (dashboard non-runtime), [ADR-0008](0008-workflow-autolog-bootstrap-and-naming.md) D7 (no new critic), [ADR-0004](0004-bypass-prevention.md) D2 (bootstrap-mode).
- Phase-2 `skill_invoke` capture (PRD #424) — the event source for the measured overlay; #430 (Skill-matcher verification).
- `dashboard/index.html` (`DISPATCH_MAP`, the topology renderer), `dashboard/server.py` (the generator + a new `/api/pipeline`), `README.template.md` (the diagram placeholder).
