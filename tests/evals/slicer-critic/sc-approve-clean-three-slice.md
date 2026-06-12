# Eval Fixture: sc-approve-clean-three-slice

## PRD Issue #9026

**Title:** PRD: add session-search to dashboard Events tab

---

## PRD Success Criteria

- WHEN the user types in the search box on the Events tab, the session list filters
  to sessions whose IDs match the search string (case-insensitive substring).
- WHEN the user clears the search box, all sessions are shown.
- WHEN the user presses Enter in the search box, the first matching session is
  expanded automatically.

---

## Proposed Slice Decomposition

### Slice 1: feat(server): add ?search= param to /api/events endpoint

**What ships:**
- `dashboard/server.py` — /api/events?search= query-param filtering
- `tests/test_events_search.py` — regression test for search filtering

**Covers:** PRD success criterion 1 (backend filter)

**Out-of-scope:** Frontend search box UI; auto-expand behavior.

**LoC estimate:** R-LOC ~70

**Depends on:** none

**Branch + commit conventions:**
- Branch: `feat/9026-events-search-api`
- Commit: `feat(server): add search filter to /api/events`

---

### Slice 2: feat(dashboard): add search box UI to Events tab

**What ships:**
- `dashboard/static/events.js` — search input + filter wiring to ?search= param
- `dashboard/static/events.css` — search box styles

**Covers:** PRD success criteria 1 (frontend), 2

**Out-of-scope:** Auto-expand on Enter; server-side changes.

**LoC estimate:** R-LOC ~85

**Depends on:** Slice 1

**Branch + commit conventions:**
- Branch: `feat/9026-events-search-ui`
- Commit: `feat(dashboard): add search box to events tab`

---

### Slice 3: feat(dashboard): auto-expand first match on Enter

**What ships:**
- `dashboard/static/events.js` — keydown Enter handler to auto-expand first result

**Covers:** PRD success criterion 3

**Out-of-scope:** Keyboard navigation beyond Enter; search history.

**LoC estimate:** R-LOC ~25

**Depends on:** Slice 2

**Branch + commit conventions:**
- Branch: `feat/9026-events-search-enter`
- Commit: `feat(dashboard): auto-expand first search match on enter`

---

## Analysis notes

Clean 3-slice decomposition. Slice 1 is the walking-skeleton: it cuts end-to-end
(backend filter + test) and delivers value immediately. Slices 2–3 build on Slice 1
incrementally. All slices have Covers:, Out-of-scope, LoC estimate, and branch/commit
conventions. Dependency ordering is a linear chain with no cycles. All three PRD
criteria are covered across the slices. Should APPROVE.
