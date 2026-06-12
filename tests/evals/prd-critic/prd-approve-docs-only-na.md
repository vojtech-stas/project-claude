# Eval Fixture: prd-approve-docs-only-na (HOLDOUT)

## PRD Issue #9018

**Title:** PRD: document the hook lifecycle and event schema in decisions/

---

## PRD Body

### 1. Problem

New contributors to the project cannot easily understand the hook lifecycle — when
hooks fire, what they receive on stdin, what exit codes mean, and how events are
structured in the JSONL schema. This information is scattered across multiple files
and ADRs.

### 2. Success criteria

- WHEN a contributor reads the hook-lifecycle ADR (to be created), they find a
  complete description of the hook firing sequence, stdin contract, and exit-code
  semantics.
- WHEN a contributor reads the event-schema-reference ADR (to be created), they find
  the canonical v2 event schema with all required fields documented and example JSONL.
- Both documents are cross-linked from decisions/README.md.

### 3. Non-goals

- We will not change the hook implementation in this PRD.
- We will not change the event schema; this is documentation only.
- We will not add UI elements to surface these docs.

### 4. Appetite

2 slices, ~2 days.

### 5. Slice sketch

- Slice 1: hook-lifecycle ADR (new file under decisions/)
- Slice 2: event-schema-reference ADR (new file) + README index update

### 6. Rabbit-holes

- Do not include implementation details of hook scripts in the lifecycle doc;
  link to the hook files instead.

### 7. Production verification

Production verification: N/A — docs-only PRD; no runtime behavior changes.
Static verification: grep for both new ADR slugs in decisions/README.md confirming
they are indexed.

---

## Analysis notes

HOLDOUT case. Docs-only PRD — explicitly states "no runtime behavior changes" and
gives an appropriate N/A with a static-verification proxy in section 7. The prd-critic
should accept "N/A" for production-verification when the PRD explicitly documents why
(docs-only) and provides a static-verification alternative. All other sections are
well-formed. Should APPROVE.
