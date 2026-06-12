# Eval Fixture: prd-block-vague-problem

## PRD Issue #9012

**Title:** PRD: improve the dashboard

---

## PRD Body

### 1. Problem

The dashboard is not great. Users have complained that it is hard to use and does
not show the right information. We should make it better.

### 2. Success criteria

- The dashboard is improved.
- Users can find what they need more easily.
- Performance is acceptable.

### 3. Non-goals

- We will not redesign the color scheme.

### 4. Appetite

Several slices, a few weeks.

### 5. Slice sketch

- TBD based on what we decide to improve.

### 6. Rabbit-holes

- Do not over-engineer.

### 7. Production verification

qa-tester will verify.

---

## Analysis notes

This PRD has catastrophically vague content throughout:
- Problem statement: "not great", "hard to use", "make it better" — no specific pain
  point, no measurable symptom.
- Success criteria: "is improved", "more easily", "acceptable" — none are verifiable
  or testable.
- Appetite: "several slices, a few weeks" — no numeric bounds.
- Slice sketch: "TBD based on what we decide to improve" — no decomposition.
- PRD title: "improve the dashboard" — not specific enough.
PC-PRD-COMPLETENESS and PC-EARS are violated throughout. Should BLOCK hard.
