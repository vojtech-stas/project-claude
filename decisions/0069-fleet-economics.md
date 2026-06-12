# 0069 — Fleet economics: effort budgets, reassurance-rerun detection, evidence-gated model tiering, DORA instability panel

- **Status:** Accepted
- **Date:** 2026-06-12
- **Extends:** ADR-0016 D6 (the future-event-additions provision — agent events gain a `model` field and dispatch events gain an `effort_class` field as within-PRD additive extensions under that provision); ADR-0027 D2 (the two-tier model-assignment policy — tier CHANGES gain an evidence gate: no downgrade without a recorded before/after golden-eval delta)

## Context

The fleet spends tokens with no economic instrumentation. Dispatches carry no effort expectation, so a context-burn death spiral (an agent grinding 150+ tool calls on a 20-call task) is indistinguishable from legitimate depth until the transcript is read; the JSONL already records tool events per session but nothing aggregates them per dispatch. Reassurance reruns — re-running an identical command with no intervening change, purely to re-observe the same output — are a named, observable waste pattern in this fleet's transcripts. Model assignment policy exists (ADR-0027 D1–D3: mandatory explicit `model:` frontmatter, two tiers, per-agent assignment) but has no change-control or runtime verification: a tier change today needs no evidence, and nothing checks that the dispatched model matches the declared one — downgrading without evidence is how silent quality regression ships, which is why the change gate is sequenced strictly after the golden-eval baselines (co-submitted regression-memory ADR). At the delivery level, the measured 24–34% fix churn has no standing trend instrument: throughput and instability can diverge for weeks before anyone notices (DORA 2025's core warning, locally confirmed).

## Decisions

### D1 — Effort classes in dispatch templates

Every /ship dispatch template states an effort class with an advisory tool-call budget: `trivial` ≈ 10–20, `standard` ≈ 30–80, `closing` ≈ ≤150. The template instructs: on clearly exceeding budget, STOP and return BLOCKED-with-learnings rather than grinding (advisory-with-measurement, never a hard kill — an agent mid-fix is not guillotined). The dispatch's `agent_start` event carries `effort_class`. Measurement (registry row): tool-calls-per-dispatch by class from the event log; flag dispatches >2× budget; PASS while ≥90% of dispatches land within budget. Per ADR-0004 D2 (bootstrap-mode), binds forward from the template merge; historical dispatches report in an unclassified bucket.

### D2 — Reassurance-rerun detector

implementer and qa-tester prompts gain one line: never re-run an identical command with no intervening file change or new hypothesis — state what new information the rerun is expected to produce. Measurement (registry row): identical-consecutive-command pairs with no intervening Edit/Write per session, from the event log (trend target: zero). Per ADR-0004 D2, binds forward from the prompt merge.

### D3 — Evidence-gated model tiering

Explicit `model:` frontmatter on every subagent is already mandatory (ADR-0027 D1) and a two-tier assignment already stands (ADR-0027 D2/D3) — what is missing is a change-control discipline. The gate this decision adds: any tier CHANGE to a critic (re-assignment of its declared `model:` value) is permitted only after that critic's golden-eval baseline exists (co-submitted regression-memory ADR), and the tier-change PR MUST record before/after eval pass rates — a tier change without a recorded eval delta is a reviewer BLOCK on that PR. The canonical logger gains a `model` field on agent events so declared-vs-observed parity is checkable (the ADR-0027 D1 invariant becomes runtime-verified instead of file-asserted). Measurement (registry rows): frontmatter coverage (the ADR-0027 D1 invariant, now standing); declared==observed parity. Per ADR-0004 D2, binds forward from the reviewer-rule merge; tier changes predating it are grandfathered.

### D4 — DORA-style instability panel

The dashboard gains a delivery-instability panel computed from real PR/issue/event ids: merges/day; slice-open→merge lead time; change-failure rate (reverts + hotfix-branch PRs + production-verify FAILs, over merged PRs); MTTR (capture-opened→fix-merged); weekly trends. Headline pair: CFR + re-dispatch rate — the "fleet outrunning its verification" canary. Keys are repo-local redefinitions (merge = deploy); every cell names its data source per rule #20's data-source discipline. Implemented in the dashboard's discovery layer with a registry row for gate-ability. Per ADR-0004 D2, binds forward; windows with no data render honestly empty.

## Consequences

- Token spend gets a per-dispatch instrument and a stop-honestly escape valve; the rerun waste pattern becomes a counted defect; model tier changes become evidence-gated experiments instead of vibes; delivery instability gets a standing trend line tied to real ids.
- Dispatch templates grow slightly; the logger schema gains two fields (additive, v2-compatible); the eval dependency means tier changes wait for baselines — deliberately.

### Enforcement (rule #23)

Deterministic, per decision: D1 — the effort-class field in dispatch events + the per-class budget registry row; D2 — the identical-pair registry row; D3 — the reviewer BLOCK condition (tier-change PR without recorded eval delta) + the frontmatter-coverage and declared==observed parity rows; D4 — the panel's registry row (renders-with-real-ids check). Parsimony — mechanisms considered: the wave-2 critic-health row measures verdict quality, not cost (verified); CAPTURE-SLO/GREEN-MAIN measure pipeline liveness, not spend; ADR-0027's assignment policy declares tiers but ships no change gate and no runtime parity check (verified against its D1–D3 — the truth-doc it relied on was retired with the KB layer per ADR-0032); no existing mechanism reads tool-call volume per dispatch though the JSONL already records it (aggregation, not new collection); all four land in existing surfaces (ship templates, two prompt lines, logger fields, registry/dashboard) — no new agent. Shadow: context-burn spirals, reassurance-rerun waste, vibes-based downgrades, throughput/instability divergence.

## Alternatives considered

- **Hard budget kills (terminate over-budget agents):** rejected — an agent mid-legitimate-fix should finish or stop honestly; advisory budgets + measurement catch the pattern without guillotining work.
- **Tiering all critics immediately by intuition:** rejected — the eval-baseline gate exists precisely because silent judgment regression is this repo's measured failure mode; evidence precedes downgrade.
- **Full DORA (deployment frequency to environments, MTTR from incidents):** rejected — no deploy target or incident system exists; repo-local proxies (merge=deploy, capture=incident) keep the metrics honest to what this repo actually does.
- **Per-dispatch token accounting via API metering:** rejected — tool-call counts from the existing JSONL are a sufficient proxy and require zero new collection machinery.

## References

- ADR-0016 D6 (future event additions), ADR-0027 D1/D2/D3 (mandatory explicit `model:` frontmatter + the two-tier assignment this ADR adds change control to), ADR-0064 D3 (registry hosts the rows), ADR-0042 D1 (CI consumes registry checks), ADR-0004 D2 (bootstrap-mode), workflow-v2 synthesis §C5/§C6/§C11 (2026-06-12); fix-churn measurement: senior-audit report (2026-06-11).
- Numbering note: co-submitted with the regression-memory ADR and the hygiene/session-start ADR (the two numbers below it) in this wave's joint gate; all three ship together in slice 1 per ADR-0003 D8, keeping the sequence contiguous at merge. The tiering gate's eval-baseline dependency refers to the co-submitted regression-memory draft by content, not number, until both are Accepted.
