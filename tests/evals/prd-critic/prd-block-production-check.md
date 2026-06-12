# Eval Fixture: prd-block-production-check

## PRD Issue #9010

**Title:** PRD: add real-time latency histogram to dashboard

---

## PRD Body

### 1. Problem

The dashboard shows aggregate event counts but gives no visibility into how long
individual operations take. Engineers debugging slow hooks have no in-product tool
to visualize latency distribution.

### 2. Success criteria

- A /api/latency endpoint returns a histogram (P50/P90/P99) computed from recent
  workflow events.
- The dashboard Health tab displays a latency sparkline.
- Values update within 30 seconds of new events arriving.

### 3. Non-goals

- We will not implement alerting based on latency thresholds.
- We will not persist historical histogram data beyond the rolling window.

### 4. Appetite

2 slices, ~1 week engineering time.

### 5. Slice sketch

- Slice 1: /api/latency endpoint + computation
- Slice 2: sparkline UI component

### 6. Rabbit-holes

- Do not attempt to correlate latency with specific tool types in slice 1.

---

## Analysis notes

The PRD has all required structural sections and the success criteria are measurable.
However there is NO section 7 / production-verification plan — no mention of how the
feature will be verified in production, no QA plan reference, no qa-tester mention.
PC-PRODUCTION-CHECK requires every PRD that ships runtime behavior to include a
production-verification plan. This PRD should BLOCK.
