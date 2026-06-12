# Eval Fixture: prd-block-appetite-incoherent

## PRD Issue #9014

**Title:** PRD: full dashboard rewrite in React with real-time WebSocket streaming

---

## PRD Body

### 1. Problem

The current dashboard is vanilla HTML/JS and does not have real-time streaming
capabilities. The server uses polling. We want a modern React SPA with WebSocket
streaming, component hot-reload, a Storybook story library, full TypeScript typing,
and a comprehensive Cypress E2E suite.

### 2. Success criteria

- WHEN any workflow event fires, the dashboard updates within 100ms via WebSocket.
- WHEN a component is edited, hot-reload shows the change within 2 seconds.
- All 200+ components have Storybook stories.
- TypeScript strict mode passes with zero errors.
- Cypress E2E suite covers all 50 dashboard routes.

### 3. Non-goals

- We will not migrate the server-side Python code.

### 4. Appetite

1 slice, 1 day.

### 5. Slice sketch

- Slice 1: full React rewrite + WebSocket + Storybook + TypeScript + Cypress

### 6. Rabbit-holes

- Do not use Redux; use Zustand instead.

### 7. Production verification

qa-tester will verify the full suite passes.

---

## Analysis notes

The appetite (1 slice, 1 day) is wildly incoherent with the scope: a full React SPA
rewrite, WebSocket streaming, 200+ Storybook stories, TypeScript strict mode, and a
50-route Cypress E2E suite cannot be delivered in 1 day by 1 slice. The success
criteria enumerate a multi-month engineering effort. PC-APPETITE-BOUNDED requires the
appetite to be coherent with scope. This is a severe incoherence — should BLOCK.
