# Eval Fixture: prd-block-ears-multi-behavior

## PRD Issue #9015

**Title:** PRD: add log rotation and archival to workflow event log

---

## PRD Body

### 1. Problem

The workflow-events.jsonl log grows unbounded. Without rotation, large logs slow
down the dashboard's event parser and consume unbounded disk space.

### 2. Success criteria (EARS format)

- WHEN the log exceeds 5 MB AND the user requests archival AND the system has
  sufficient disk space AND the archive directory exists, the system shall rotate
  the log, compress the old file, move it to the archive directory, emit a
  rotation-event JSONL line, update the dashboard LOGS row to reflect the rotation,
  and restart the log at zero bytes.

### 3. Non-goals

- We will not implement automatic cloud upload of archives.
- We will not implement a UI to browse archived logs.

### 4. Appetite

2 slices, ~1 week.

### 5. Slice sketch

- Slice 1: rotation trigger + compression
- Slice 2: archive move + dashboard row

### 6. Rabbit-holes

- Do not implement scheduled rotation; trigger only on size threshold.

### 7. Production verification

qa-tester will verify rotation by creating a large synthetic log and confirming
the hook rotates it correctly.

---

## Analysis notes

The single EARS criterion in section 2 encodes 7 behaviors in one statement: rotate,
compress, move, emit rotation-event, update dashboard row, restart log, AND has 4
trigger conditions chained with AND. This violates the EARS principle that each
statement should encode exactly one behavior with a clear single trigger. This should
be split into separate EARS statements for each behavior. PC-EARS violation for
multi-behavior compound statement — should BLOCK.
