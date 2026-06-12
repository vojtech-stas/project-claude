# tests/ — regression suite

This directory holds the project-claude regression test suite, seeded per ADR-0067 D1.

## Runner choice

**pytest** is the primary runner (pytest 9.0.3 was verified present on this machine
at suite creation time). The stdlib `unittest` module is also available as a fallback.

Run the suite:
```bash
# From the repo root:
pytest tests/ -v

# Fallback (no pytest installed):
python -m unittest discover -s tests -p "test_*.py"
```

## CI integration

`tools/ci-checks.sh` runs the suite automatically as CHECK 12 when `tests/`
exists. A failure in any test fails the CI check. The collected count is
reported in the pass line.

## Founding test

`test_events_interleave.py` — regression for the events.py interleave defect
(issue #730, ADR-0067 D1). This bug shipped twice; the test ensures it cannot
ship a third time.

**What the bug was:** `serve_runs(?session=<id>)` broke early when it
encountered a line from a different session, truncating the target session's
events whenever two concurrent sessions' lines interleaved in the JSONL file.

**Why it shipped twice:** the second author rationalised the break with a
docstring comment saying "if we see a different session, the target session
is done" — a false assumption for concurrent sessions. The forensic post-mortem
lives in `qa-proof/forensics/event-pipeline-autopsy.md`.

## Quarantine

Flaky or known-broken tests may be quarantined in `tests/quarantine.txt` per
ADR-0067 D4. Every quarantine entry must carry a `captured`-labeled issue
reference. Entries older than 30 days are SLA breaches.
