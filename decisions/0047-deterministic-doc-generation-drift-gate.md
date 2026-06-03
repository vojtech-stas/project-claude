# ADR-0047: Deterministic doc generation + a CI drift gate (generate the derivable, check the prose)

- **Status:** Accepted
- **Date:** 2026-06-03
- **Extends / completes:** [ADR-0039](0039-single-source-workflow-topology.md) D1 (the `PIPELINE` spec as canonical topology source — generalized here to *all* derivable representations) + D2 (README + dashboard generated from the spec — **fulfilled**: the implementation left `render_pipeline_mermaid` ignoring the spec, which this ADR fixes) + D3 (the measured-overlay drift-*visibility* mechanism — **complemented** with a mechanical drift *gate*), [ADR-0034](0034-build-orchestrator-and-generated-docs.md) D4 (README template) + D7 (`--generate-readme` generator — extended to the critic-list + spec-rendered mermaid), [ADR-0042](0042-github-actions-ci-gate-r4.md) D1 (the `tools/ci-checks.sh` CI gate — gains CHECK 7), [ADR-0033](0033-tooling-spawn-hook-scope.md) D4 (`dashboard/*` non-runtime). Honors [ADR-0046](0046-codebase-critic-and-parsimony-reframe.md) D1 (critic parsimony — no new critic; the in-force rule that reframed ADR-0008 D7) + [ADR-0004](0004-bypass-prevention.md) D2 (bootstrap-mode).
- **Supersedes:** none (additive — it completes ADR-0039's intent and extends the generated-docs system; no prior decision is reversed).

## Context

The owner observed (2026-06-03) that the dashboard's architecture graph disagrees with the README — despite the README generator, the CI gate, audit-meta, and the just-shipped codebase-critic. Investigation found the workflow topology is asserted in **~7 places across 5 files**, three of them **independent hand-maintained copies**: the README pipeline mermaid (rendered by `dashboard/server.py render_pipeline_mermaid`), a hardcoded mermaid in `dashboard/index.html`, and the `PIPELINE` dict ([ADR-0039](0039-single-source-workflow-topology.md)'s intended single source). The smoking gun: **`render_pipeline_mermaid()` ignores the `PIPELINE` argument it is handed** — its body is ~70 hardcoded `lines.append(...)` literals — so ADR-0039 D2's "the README diagram can never disagree with the spec" was *decided but never implemented*; the spec only ever fed the dashboard's secondary node-link graph + the counts. Likewise the `index.html` mermaid is a hand-maintained copy D2 never addressed.

Nothing caught the drift because the sole guard, `ci-checks.sh` CHECK 2, only verifies *README == its own regenerator's output* — it certifies **self-consistency**, never **correctness-against-reality** or **agreement-with-the-dashboard**. So when the last two PRDs added `codebase-critic` and retired `R-BOY-SCOUT`, every hand-maintained copy went stale silently (the dashboard + README still show `R-BOY-SCOUT` and omit `codebase-critic`; the README prose still says "6 critics" while CLAUDE.md says "7").

The root cause is a DRY violation (rule #9): N hand-maintained copies of facts that have a single canonical home, with no generation-from-source and no cross-representation check. Grill (2026-06-03) resolved the fix and corrected one tempting-but-unworkable intuition: you **cannot** deterministically generate CLAUDE.md/README *prose* from ADRs (prose isn't machine-renderable; an LLM is non-deterministic and untrustworthy in CI). The repo holds **three kinds of fact** with **three canonical homes**: *"what exists"* → the **filesystem**; *"how it connects"* → the **`PIPELINE` spec**; *"why / what rule"* → **ADRs + CLAUDE.md** (prose). The first two are *generated*; the third is *checked*.

## Decisions

### D1: Generalize the single-source principle to every derivable representation (extends [ADR-0039](0039-single-source-workflow-topology.md) D1)

The canonical-source rule is generalized beyond the topology: **every mechanically-derivable representation — diagrams, component lists, counts — is GENERATED from its canonical home and is never hand-maintained.** The two canonical homes are the **filesystem** (the ground truth for *what exists*: the `.claude/agents/*.md`, `.claude/skills/*/`, `decisions/*.md` sets and their counts) and the **`PIPELINE` spec** (the ground truth for *how the pipeline connects*). Hand-authored prose (ADRs, CLAUDE.md rules, README narrative) is the only non-generated layer (see D4).

### D2: Both mermaids generate from the spec; the critic-list/count generates from the filesystem (fulfills + extends [ADR-0039](0039-single-source-workflow-topology.md) D2)

- Fix `dashboard/server.py render_pipeline_mermaid()` to **actually render the README mermaid from the `PIPELINE` spec** (currently it ignores the argument — honoring the ADR-0039 D2 decision the implementation skipped).
- Render the dashboard's "Pipeline diagram" mermaid from the **same** spec (served via `/api/pipeline`), **removing the hardcoded `index.html` copy** (the implementer may render it client-side from the spec or drop it in favor of the already-data-driven node-link graph).
- **Extend the `PIPELINE` spec** to model the full graph — stages, nodes (skills/agents/critics), edges, side-workflows (glossary, promote-to-backlog, the codebase-critic cadence) — so the rendered mermaids are complete.
- **Generate the README critic-list and count** from the discovered critic set (the `*-critic.md` files), removing the hand-typed "6 critics" prose from `README.template.md`.

One edit to the spec (or one file added to the filesystem) updates every render; the hand-maintained copies cease to exist.

### D3: CHECK 7 — a mechanical drift gate in CI (the enforcement [ADR-0039](0039-single-source-workflow-topology.md) lacked)

`tools/ci-checks.sh` ([ADR-0042](0042-github-actions-ci-gate-r4.md) D1's gate) gains **CHECK 7**, which fails the run (exit non-zero) on any of:
- **(a) source ↔ reality** — the critic/agent/skill set declared in the `PIPELINE` spec does not match the set discovered on the filesystem (a node added without a file, or a file like `codebase-critic` missing from the spec, or a retired node like `R-BOY-SCOUT` still declared);
- **(b) artifact ↔ source** — the generated README mermaid and dashboard mermaid do not equal a fresh render-from-spec (regenerate-and-diff, extending CHECK 2's mechanic to the dashboard render);
- **(c) prose-facts ↔ reality** — load-bearing factual claims in hand-authored prose disagree with the canonical facts (e.g. the critic *count/names* stated in CLAUDE.md and README do not match `ls .claude/agents/*-critic.md`).

CHECK 7 soft-degrades (skips cleanly) if git/grep/python tooling is unavailable, like the other checks. It **complements** ADR-0039 D3's measured overlay (which visualizes declared-vs-*runtime* drift from event logs) with a declared-vs-*filesystem* + artifact-vs-spec **gate that blocks merge**.

### D4: Prose stays hand-authored and *checked*, not generated (the boundary)

This is recorded explicitly so no future work attempts the unworkable: **ADRs (immutable) and CLAUDE.md (governance prose) are NOT machine-generated.** Deterministic rendering of prose from a structured model is not achievable; LLM generation is non-deterministic and cannot be trusted in a CI gate. The prose layer's consistency is guarded by CHECK 7's prose-facts sub-check (specific high-value claims) plus the *judgment* layer — `adr-critic` (AC-CROSS-ADR-CONSISTENCY) and `codebase-critic` (semantic reference currency) — for the semantics a grep cannot see.

### D5: Bootstrap-mode (per [ADR-0004](0004-bypass-prevention.md) D2)

Binds forward from merge. The walking-skeleton slice regenerates the currently-stale artifacts (adds `codebase-critic`, drops `R-BOY-SCOUT`, corrects the critic count) so the baseline is honest and CHECK 7 is green on a clean tree before the gate binds. No retroactive sweep beyond making the baseline correct.

## Consequences

**Positive:**
- Drift becomes **structurally impossible** for every derivable representation (there is nothing left to hand-edit) and **mechanically caught** for the prose layer (CI red on any stale claim).
- The repo self-heals on `--generate-readme` + regen; "is the data current?" stops being a worry and becomes a green/red CI signal.
- Completes ADR-0039's intent (the spec finally drives both mermaids) and removes two hand-maintained copies.

**Negative:**
- The `PIPELINE` spec is still hand-edited — but in **one** place, and CHECK 7 (a) fails the moment it lags the filesystem.
- A one-time effort to model the full graph in the spec and write CHECK 7 carefully (false-positive-averse).

**Neutral:**
- No new critic ([ADR-0046](0046-codebase-critic-and-parsimony-reframe.md) D1 critic-parsimony honored), no new dependency. Touch: `dashboard/server.py`, `dashboard/index.html`, `README.template.md`, `tools/ci-checks.sh` (all non-runtime per [ADR-0033](0033-tooling-spawn-hook-scope.md) D4 + the tooling/doc set) + `decisions/0047-*.md` + `decisions/README.md` + README regen.

## Alternatives considered

- **Alt-A (chosen): generate the derivable (filesystem + spec) + check the prose (CHECK 7), both in CI.** Eliminates the duplication and gates the rest.
- **Alt-B: generate-only (no CHECK 7).** Rejected (grill): the prose-facts class (CLAUDE.md/README count claims) would stay caught only by per-PRD judgment — which already missed this exact drift.
- **Alt-C: generate CLAUDE.md / drive prose from a structured ADR model.** Rejected (grill): prose isn't deterministically renderable; it fights ADR immutability and needs an LLM no CI gate can trust. The same "stop worrying" outcome is reached by *checking* prose instead of generating it (D4).
- **Alt-D: check-only (keep the hand-maintained copies, just add a consistency check).** Rejected (grill): leaves the root-cause duplication intact → perpetual reactive whack-a-mole; never fulfills ADR-0039 D2.
- **Alt-E: rely on the codebase-critic (judgment).** Rejected (grill): per-PRD, forward-only, non-deterministic; it already missed this drift and the owner explicitly wants a mechanical gate.

## References

- Grill 2026-06-03 (dashboard↔README drift). The drift dogfood: dashboard `index.html` + README mermaid still show retired `R-BOY-SCOUT` `-.periodic.- reviewer` and omit `codebase-critic`; README prose says "6 critics" vs CLAUDE.md "7".
- [ADR-0039](0039-single-source-workflow-topology.md) D1+D2+D3 (completed + extended). [ADR-0034](0034-build-orchestrator-and-generated-docs.md) D4 (README template) + D7 (generator). [ADR-0042](0042-github-actions-ci-gate-r4.md) D1 (CI gate / CHECK 7). [ADR-0033](0033-tooling-spawn-hook-scope.md) D4 (dashboard non-runtime). [ADR-0046](0046-codebase-critic-and-parsimony-reframe.md) D1 (critic parsimony — no new critic). [ADR-0004](0004-bypass-prevention.md) D2 (bootstrap-mode).
- `dashboard/server.py` (`render_pipeline_mermaid`, `_build_component_map`, `_build_counts`, the `PIPELINE` dict, `/api/pipeline`), `dashboard/index.html` (hardcoded mermaid to remove), `README.template.md` (the "6 critics" prose + diagram placeholder), `tools/ci-checks.sh` (CHECK 7).
