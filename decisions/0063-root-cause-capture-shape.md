---
id: "ADR-0063"
status: "accepted"
supersedes: []
superseded_by: []
scope: "capture"
rule_ids:
  - "CAP-007"
  - "CAP-008"
---
# 0063 — Root-cause capture shape contract: labeled, regex-checkable, evidence-first

- **Status:** Accepted
- **Date:** 2026-06-12
- **Extends:** ADR-0024 D3 (root-cause capture body MUST contain 3 named sections); this ADR adds a query label, mechanical detectability, an evidence-first ordering rider, and a standing measurement on top of that shape

## Context

ADR-0024 D3 named the three mandatory sections of a rule-#13 root-cause capture (Symptom / Root cause / Proposed), and the discipline is a user-standing preference — but nothing measures compliance, so the shape is subject to the same prose-decay this repo has quantified elsewhere (~0–17% compliance for unmeasured prose obligations vs ~97.5% for checked contracts). Two specific gaps: (a) root-cause captures are indistinguishable from ordinary `captured` issues at query time — no label exists, so neither a human nor an evaluator can list them mechanically; (b) under failure pressure agents fix first and reconstruct evidence from memory afterwards — the original error output is gone by capture time, degrading the root-cause analysis the discipline exists to preserve (observed repeatedly in this repo's forensics).

## Decisions

### D1 — The `root-cause` label

Rule-#13 captures carry a second label, `root-cause`, alongside `captured`. This makes the class mechanically queryable (`gh issue list --label root-cause`) for humans, evaluators, and the backlog autopilot. Per ADR-0004 D2 (bootstrap-mode), binds forward from the merge of the rule-#13 amendment slice; existing captures are grandfathered (the evaluator's heuristic sweep may suggest retro-labels, never auto-apply them).

### D2 — Mechanically detectable section shape

The three ADR-0024 D3 sections are written as regex-detectable headings — `**Symptom:**` / `**Root cause:**` / `**Proposed:**` — so shape compliance is computable from the issue body alone. Per ADR-0004 D2, binds forward from the same merge; the shape matches what well-formed captures in this repo already use, so conforming agents change nothing.

### D3 — Evidence-first ordering rider

On an unexpected failure, the FIRST action is preserving verbatim evidence (error output, log excerpts, environment facts) into the capture body — STOP → PRESERVE → DIAGNOSE → FIX → GUARD → RESUME. Memory-reconstructed captures are the named anti-pattern. Per ADR-0004 D2, binds forward from the rule-#13 amendment merge.

## Consequences

- Root-cause discipline becomes a measured rate with named non-conformers instead of an honor-system hope; the capture class becomes queryable.
- One more label to create in `bootstrap.sh`'s label step (rides the implementing slice).

### Enforcement (rule #23)

Deterministic, per decision: D1+D2 — a CAPTURE-SHAPE dashboard health row computing the shape-conforming fraction of `root-cause`-labeled issue bodies (3-heading regex) and naming non-conformers, plus a heuristic counter for 3-section-shaped bodies missing the label (surfaced, never auto-relabeled); D3 — the evidence-presence sub-metric of the same row (fraction of conforming captures whose Symptom section contains a fenced/quoted verbatim evidence block). Parsimony — existing mechanisms considered and why each falls short: `backlog-critic` evaluates capture quality but fires exactly once per item at promotion time (ADR-0008 D2 autopilot semantics), so BLOCKed items legitimately remain in the captured tier unmeasured and post-promotion decay is invisible to it; CI greps (`tools/ci-checks.sh`) run on code pushes, not on issue creation, so they never see issue bodies; no health check today reads issue-body text. A standing dashboard evaluator over the live issue list is the only surface that continuously measures issue-body shape, and it reuses the existing health-row pattern — no new agent, no new artifact type. (ADR-0024 D4 separately deferred an `/audit-meta` scan of workflow-events.jsonl for bypass language — a different mechanism over a different data source; this ADR neither fulfills nor disturbs that deferral.) Shadow: symptom-only and memory-reconstructed captures wearing the root-cause name.

## Alternatives considered

- **backlog-critic enforces shape at promotion time:** rejected as the sole mechanism — the autopilot fires once per item and BLOCKed items legitimately stay captured; a standing measured rate catches decay the single-fire gate misses (the critic MAY still cite shape in verdicts).
- **Auto-relabeling shape-matching issues:** rejected — labels are intent declarations; the evaluator surfaces candidates, a human decides.
- **CI grep over issue bodies:** rejected — CI runs on code pushes, not issue creation; the dashboard evaluator polls the live issue list, which is the natural surface.

## References

- ADR-0024 (rule #13 origin; D3 the shape being extended; D4's separate /audit-meta deferral untouched), ADR-0004 D2 (bootstrap-mode), ADR-0008 D2/D3/D4 (captured→backlog autopilot the label rides), user-standing root-cause preference, workflow-v2 synthesis §B14 (2026-06-12).
