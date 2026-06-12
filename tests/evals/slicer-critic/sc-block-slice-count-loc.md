# Eval Fixture: sc-block-slice-count-loc

## PRD Issue #9024

**Title:** PRD: add comprehensive analytics to dashboard

---

## PRD Success Criteria

- WHEN the user views the Analytics tab, they see: session duration histogram,
  tool-use frequency bar chart, error-rate trend line, agent-type breakdown pie chart,
  and a heatmap of activity by hour-of-day.
- All charts update within 30s of new events.

---

## Proposed Slice Decomposition

### Slice 1: feat(dashboard): add analytics tab with all five chart types

**What ships:**
- `dashboard/server.py` — /api/analytics endpoint with all five data computations
- `dashboard/static/analytics.js` — all five chart components (histogram, bar, line,
  pie, heatmap) with D3.js rendering
- `dashboard/static/analytics.css` — styling for all five charts
- `dashboard/templates/analytics.html` — new Analytics tab template
- `dashboard/health.py` — ANALYTICS health check
- `tests/test_analytics.py` — test suite for analytics computation

**Covers:** PRD success criteria 1, 2

**LoC estimate:** R-LOC ~650

**Out-of-scope:** Nothing deferred.

**Branch + commit conventions:**
- Branch: `feat/9024-analytics-tab`
- Commit: `feat(dashboard): add analytics tab with all five chart types`

---

## Analysis notes

The single slice claims R-LOC ~650, which is more than double the 300 LoC cap
defined in rule I4 / R-LOC. A 650-LoC slice is a clear SC-SLICE-COUNT-LOC violation.
The slicer should have split this into at least 3 slices: (1) /api/analytics endpoint
+ data computations, (2) basic chart rendering (1-2 charts as walking skeleton),
(3) remaining charts + polish. The "Nothing deferred" out-of-scope is also a red flag
confirming the slicer attempted to stuff everything into one slice.
Should BLOCK for over-cap LoC estimate.
