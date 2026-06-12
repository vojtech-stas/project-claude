# Eval Fixture: prd-block-non-goals-tbd

## PRD Issue #9013

**Title:** PRD: add session replay to dashboard

---

## PRD Body

### 1. Problem

Engineers want to replay a past session's events in sequence to debug state
transitions. The dashboard currently shows only the final state; temporal ordering
is invisible.

### 2. Success criteria

- WHEN a user clicks "Replay" on a session row, the dashboard steps through events
  in chronological order at 1x speed.
- WHEN playback reaches the end, the dashboard returns to the final-state view.
- Playback can be paused and resumed at any event boundary.

### 3. Non-goals

- TBD

### 4. Appetite

4 slices, ~3 weeks.

### 5. Slice sketch

- Slice 1: replay API endpoint
- Slice 2: playback UI controls
- Slice 3: event-step rendering
- Slice 4: pause/resume + keyboard shortcuts

### 6. Rabbit-holes

- Do not implement variable-speed playback in this PRD.

### 7. Production verification

qa-tester will verify replay with a real session captured in the production log.

---

## Analysis notes

The PRD is otherwise well-formed, but the Non-goals section (section 3) says only
"TBD". This is a PC-NON-GOALS-EXPLICIT violation — non-goals must be explicitly
stated, not deferred. An explicit non-goals list prevents scope creep and helps
the slicer draw boundaries. "TBD" means the author has not thought through what is
out of scope, which is a gate-level problem. Should BLOCK.
