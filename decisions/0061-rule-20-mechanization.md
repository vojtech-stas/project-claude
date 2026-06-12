# 0061 — Rule #20 mechanization: the verification budget becomes a table, provenance becomes fields, route mandates stop being self-graded

- **Status:** Accepted
- **Date:** 2026-06-12
- **Extends:** ADR-0037 D2 (qa-tester production-verify auto-routing by change type — the routing judgment becomes a tracked lookup table); ADR-0037 D3 (orchestrator-enforced gate — gains an artifact-existence assertion); ADR-0054 D4 (proof provenance prose statements — become structured, machine-validated fields); ADR-0054 D5 (verification-route downgrade policy — its PROVISIONAL-never-weaker-route rule is unchanged in substance; this ADR mechanizes it: the route mandate now derives from the D1 table instead of the agent's own route declaration, and compliance becomes evaluator-measured — closing the gap #639 exploited, where the rule existed but the route choice it governed was still self-graded judgment)

## Context

Rule #20's residual honor-system clauses are this repo's measured top failure mode (verification theater): #639's silent route downgrade shipped a browser-crash bug behind a green gate; the 2026-05-31 forensics show synthetic evidence printing "ACCEPTANCE CRITERIA CHECK: PASS"; #623/#685 stale environments produced proofs of the wrong code twice in one week; #777 (this wave) showed PASS verdicts whose ARTIFACTS paths no longer exist — nothing stats them; route selection, provenance statements, and freshness claims are all agent judgment graded by the agent itself. Wave 1 built the honest substrate (/api/meta, live capture SLO); this ADR converts rule #20's remaining prose into gates that bind on that substrate.

## Decisions

### D1 — Verification-budget route table

Route selection moves from agent judgment to a tracked lookup table in the qa-tester prompt: changed-path globs → mandatory proof class (e.g. `dashboard/**` → browser: screenshot + inner_text; `.claude/hooks/**`, `.claude/settings.json` → hook-fire: happy-path AND induced-failure beacon pair; `tools/**`, `.claude/skills/**` → command-run: output + exit codes; docs → static: grep counts). A change matching multiple globs takes the union of proof classes. The table is the single routing authority; deviations are themselves findings. Per ADR-0004 D2 (bootstrap-mode), binds forward from the qa-tester prompt-update merge.

### D2 — Structured proof provenance: `PROOF_SOURCE:` and `ENV:` fields

The prose data-source/freshness statements of ADR-0054 D4 become structured trailer fields: `PROOF_SOURCE: <session_id>@<ts>` (machine-validated against `workflow-events.jsonl`: sid exists in window, not fixture-patterned, ts ordering sane) and `ENV: <sha>@<started_at>` (validated against `/api/meta` for browser routes — the wave-1 handshake is the freshness mechanism). Validation failures invalidate the proof. Binds forward per ADR-0004 D2.

### D3 — PROVISIONAL semantics mechanized (extends ADR-0054 D5)

ADR-0054 D5's rule stands unchanged: tooling unavailability on the mandated route yields `PROVISIONAL` → `needs-human-check`, never a PASS via a weaker route. What changes here is its authority and measurement: the "mandated route" is now the D1 table's output (not the agent's own declaration — under D5 alone, an agent could still self-select a weaker route upfront and pass honestly against it, the #639 gap), and route-vs-proof-class compliance becomes evaluator-checked. Binds forward per ADR-0004 D2.

### D4 — Negative-path proof obligations

Escalation rows in the D1 table: PRs touching hooks/settings require a happy-path proof AND an induced-failure proof (the ERROR beacon shown firing, per the wave-1 fail-loud contract); PRs touching `.github/workflows/` or `tools/ci-checks.sh` require a deliberately-failing canary shown to fail before the green run is evidence. Binds forward per ADR-0004 D2.

### D5 — Artifact-existence assertion

The orchestrator's gate handling stats every path in the qa-tester `ARTIFACTS:` field before accepting PASS; a missing artifact invalidates the verdict (re-dispatch or FAIL). Companion contract: production-verify artifacts are written ONLY under the root repo's gitignored proof directories (absolute paths) — never worktree-relative paths that vanish with auto-cleaned worktrees (#777's class). Binds forward per ADR-0004 D2.

## Consequences

- The four ways a green gate could lie (wrong route, fake provenance, stale environment, vanished artifacts) each gain a deterministic check; PROVISIONAL volume may rise — that is honest load surfacing, cleared via the existing `/qa-review` queue (ADR-0040).
- qa-tester prompt grows a table; orchestrator gate handling grows two assertions.

### Enforcement (rule #23)

Deterministic: proof-presence + provenance evaluator on the dashboard (per merged non-trivial PR: route classification from changed paths, route-appropriate proof token greps over the PR/PRD trail, PROOF_SOURCE sid resolution, artifact-existence at evaluation time); class-vs-proof mismatch counts target 0. Parsimony: extends ADR-0037's existing gate and ADR-0054's existing trailer — no new agent. Shadow: verification theater — green gates with unverifiable or vanished evidence.

## Alternatives considered

- **Trust agent route judgment with better prompts:** rejected — #639 happened under exactly that regime; prose decays.
- **Hard-FAIL instead of PROVISIONAL on tooling gaps:** rejected — punishes infra flakiness with false reds; PROVISIONAL + human queue preserves honesty without noise (ADR-0040's residual model).
- **Full CI-side proof validation service:** rejected — sprawl; the dashboard evaluator + orchestrator stat cover the measurable need with zero new infrastructure.

## References

- ADR-0037 (gate + routing being mechanized), ADR-0054 D4/D5 (provenance prose + downgrade policy), ADR-0050 (browser driver mechanics unchanged), ADR-0040 (needs-human-check residual queue), ADR-0004 D2 (bootstrap-mode), issues #639 #623 #685 #777, qa-proof/forensics, workflow-v2 synthesis §B2/§B12 (2026-06-12).
