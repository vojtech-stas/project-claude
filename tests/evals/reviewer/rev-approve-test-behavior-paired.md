# Eval Fixture: rev-approve-test-behavior-paired (HOLDOUT)

## Slice issue #9008

**Title:** feat(events): add metadata-mode event count to serve_runs

**What ships:**
- `dashboard/events.py` — add event_count field to metadata-mode response
- `tests/test_events_metadata.py` — regression test for metadata mode

---

## PR body

```
feat(events): add metadata-mode event count to serve_runs

## Scope
Adds event_count field to each run in the ?n= metadata-mode response.
Pairs with a regression test in tests/.

## Out-of-scope
No changes to health.py or server.py.

## Verification
python -m pytest tests/test_events_metadata.py -v exits 0

Closes #9008
```

---

## Diff summary

Files changed:
- `dashboard/events.py` (+18 -4): add event_count computation in metadata mode
- `tests/test_events_metadata.py` (+65 -0): new regression test

---

## Commit log

```
feat(events): add metadata-mode event count to serve_runs

Consumers of ?n= mode need event counts to render sparklines without
fetching full event lists. Paired with regression test.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
```

---

## Analysis notes

HOLDOUT case. Clean slice: new behavior (event_count) is paired with a matching
regression test. PR body has all three required sections. Commit subject is 56 chars
(under 72 cap), lowercase, Co-Authored-By present. Closes #9008 in body. No scope
drift. Should APPROVE — R-TEST-BEHAVIOR satisfied.
