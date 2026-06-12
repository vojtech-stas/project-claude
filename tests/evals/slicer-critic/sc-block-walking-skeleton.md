# Eval Fixture: sc-block-walking-skeleton

## PRD Issue #9020

**Title:** PRD: add multi-panel layout to dashboard

---

## PRD Success Criteria

- WHEN the user visits the dashboard, it shows four panels: Events, Health, Sessions, Settings.
- WHEN the user clicks a panel header, it collapses/expands.
- WHEN the user resizes the browser, the layout reflows responsively.

---

## Proposed Slice Decomposition

### Slice 1: feat(dashboard): events panel UI component

**What ships:**
- `dashboard/static/events-panel.js` — fully polished events panel with expand/collapse
- `dashboard/static/events-panel.css` — complete responsive styles

**Covers:** Success criterion 1 (partial — events panel only)

**LoC estimate:** R-LOC ~180

---

### Slice 2: feat(dashboard): health panel UI component

**What ships:**
- `dashboard/static/health-panel.js` — health panel component
- `dashboard/static/health-panel.css`

**Covers:** Success criterion 1 (partial — health panel)

**LoC estimate:** R-LOC ~150

---

### Slice 3: feat(dashboard): sessions panel UI component

**What ships:**
- `dashboard/static/sessions-panel.js`
- `dashboard/static/sessions-panel.css`

**Covers:** Success criterion 1 (partial — sessions panel)

**LoC estimate:** R-LOC ~160

---

### Slice 4: feat(dashboard): settings panel + multi-panel layout integration

**What ships:**
- `dashboard/static/settings-panel.js`
- `dashboard/static/layout.js` — integrates all four panels into the page

**Covers:** Success criteria 1, 2, 3

**LoC estimate:** R-LOC ~200

---

## Analysis notes

Slice 1 builds a fully polished events panel in isolation. There is no end-to-end
working product until Slice 4. Slices 1–3 build individual layers (horizontal slices)
rather than cutting through the full feature stack. SC-WALKING-SKELETON requires that
Slice 1 demonstrate the smallest end-to-end version of the feature — here Slice 1
should show one panel + the multi-panel shell working end-to-end, then Slices 2–3
add the remaining panels. This is a horizontal layer decomposition, not a
walking-skeleton. Should BLOCK.
