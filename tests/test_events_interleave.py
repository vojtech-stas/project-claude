"""
Regression test for the events.py interleave defect (issue #730 / ADR-0067 D1).

Bug history: the ?session=<id> branch in serve_runs() was re-implemented twice
with a break-on-non-matching-line optimisation. Both authors believed "if we see
a line from a different session, the target session is done" — a false assumption
when two concurrent sessions interleave lines throughout the file. The second
re-introduction was accompanied by a docstring rationalising it as an
"optimisation". This regression test ensures the defect stays fixed.

Failing behaviour (the bug): serve_runs({session:[TARGET_SID]}, log_path)
returns a truncated event list whenever another session's line appears between
two TARGET_SID events in the log file.

Passing behaviour (the fix): every TARGET_SID line is collected regardless of
interleaving, producing a complete event list.

The test constructs a synthetic JSONL log with two interleaved sessions
(A and B) and asserts that fetching session A returns ALL of A's events,
not just the head before the first B line.

Runner: stdlib unittest (pytest optional — run with either):
  python -m unittest discover -s tests
  pytest tests/  (if pytest is installed)
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_v2_event(session_id: str, event: str, ts: str) -> str:
    """Return a JSON-encoded schema-v2 event line."""
    return json.dumps({
        "v": 2,
        "ts": ts,
        "session_id": session_id,
        "event": event,
    })


def _write_log(lines: list, path: Path) -> None:
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _get_dashboard_dir() -> str:
    """Return the dashboard/ directory path and ensure it is on sys.path."""
    repo_root = Path(__file__).resolve().parent.parent
    dashboard_dir = str(repo_root / "dashboard")
    if dashboard_dir not in sys.path:
        sys.path.insert(0, dashboard_dir)
    return dashboard_dir


# ---------------------------------------------------------------------------
# Regression test — interleaved session truncation (issue #730)
# ---------------------------------------------------------------------------

class TestInterleaveRegression(unittest.TestCase):
    """serve_runs(?session=A) must return ALL of session A's events even when
    session B lines appear between A's events in the JSONL file.

    This is the founding regression test for the tests/ suite per ADR-0067 D1.
    The defect shipped twice; the test ensures it cannot ship a third time.
    """

    # Note: session IDs must NOT match FIXTURE_SID_RE in events.py
    # (^(demo|test|verify|fixture|manual|sess-|sample-session-id$)) — those
    # are filtered out by the is_valid_v2_event guard.
    TARGET_SID = "live-session-alpha-001"
    OTHER_SID  = "live-session-beta-002"

    def _build_interleaved_log(self) -> list:
        """Build a log where A and B lines are strictly interleaved: A B A B A."""
        return [
            _make_v2_event(self.TARGET_SID, "session_start",  "2026-06-12T10:00:00Z"),
            _make_v2_event(self.OTHER_SID,  "session_start",  "2026-06-12T10:00:01Z"),
            _make_v2_event(self.TARGET_SID, "tool_use",       "2026-06-12T10:00:02Z"),
            _make_v2_event(self.OTHER_SID,  "tool_use",       "2026-06-12T10:00:03Z"),
            _make_v2_event(self.TARGET_SID, "session_stop",   "2026-06-12T10:00:04Z"),
        ]

    def test_interleaved_session_returns_all_events(self):
        """With interleaved A/B events, fetching session A must return all 3 A events.

        The buggy implementation would return only the first A event (session_start)
        before encountering the first B line and breaking. This test would FAIL on
        that implementation and PASS on the fixed one.
        """
        _get_dashboard_dir()
        from events import serve_runs  # noqa: PLC0415

        with tempfile.TemporaryDirectory() as tmp_dir:
            log_path = Path(tmp_dir) / "workflow-events.jsonl"
            _write_log(self._build_interleaved_log(), log_path)

            result = serve_runs({"session": [self.TARGET_SID]}, log_path)

        self.assertIsNotNone(
            result.get("run"),
            "Expected a run dict for TARGET_SID but got None. "
            "This means serve_runs found no events for the target session.",
        )
        events = result["run"]["events"]

        # The target session has exactly 3 events: session_start, tool_use, session_stop.
        self.assertEqual(
            len(events), 3,
            f"Expected 3 events for session {self.TARGET_SID!r} but got {len(events)}. "
            f"Events returned: {[e.get('event') for e in events]}. "
            "The interleave defect (break-on-non-matching-line) truncates the list "
            "whenever a different session's line appears between two target-session lines.",
        )

        event_types = [e["event"] for e in events]
        self.assertEqual(
            event_types, ["session_start", "tool_use", "session_stop"],
            f"Unexpected event order: {event_types}",
        )

    def test_non_interleaved_baseline(self):
        """Baseline: contiguous A events (no interleaving) still return all events.

        This passes even under the buggy implementation — it is the baseline that
        demonstrates the buggy version would appear to work in the simple case.
        """
        _get_dashboard_dir()
        from events import serve_runs  # noqa: PLC0415

        with tempfile.TemporaryDirectory() as tmp_dir:
            log_path = Path(tmp_dir) / "workflow-events.jsonl"
            lines = [
                _make_v2_event(self.TARGET_SID, "session_start", "2026-06-12T10:00:00Z"),
                _make_v2_event(self.TARGET_SID, "tool_use",      "2026-06-12T10:00:01Z"),
                _make_v2_event(self.TARGET_SID, "session_stop",  "2026-06-12T10:00:02Z"),
            ]
            _write_log(lines, log_path)

            result = serve_runs({"session": [self.TARGET_SID]}, log_path)

        self.assertIsNotNone(result.get("run"))
        self.assertEqual(len(result["run"]["events"]), 3)

    def test_metadata_mode_interleave(self):
        """Metadata mode (?n=2): both sessions appear even with strict interleaving."""
        _get_dashboard_dir()
        from events import serve_runs  # noqa: PLC0415

        with tempfile.TemporaryDirectory() as tmp_dir:
            log_path = Path(tmp_dir) / "workflow-events.jsonl"
            _write_log(self._build_interleaved_log(), log_path)

            result = serve_runs({"n": ["2"]}, log_path)

        runs = result.get("runs", [])
        session_ids = {r["session_id"] for r in runs}

        self.assertIn(
            self.TARGET_SID, session_ids,
            f"TARGET_SID {self.TARGET_SID!r} missing from metadata runs: {session_ids}",
        )
        self.assertIn(
            self.OTHER_SID, session_ids,
            f"OTHER_SID {self.OTHER_SID!r} missing from metadata runs: {session_ids}",
        )

        # The log is A B A B A — target has 3 events, other has 2.
        expected_counts = {
            self.TARGET_SID: 3,
            self.OTHER_SID: 2,
        }
        for run in runs:
            sid = run["session_id"]
            expected = expected_counts.get(sid)
            if expected is not None:
                self.assertEqual(
                    run["event_count"], expected,
                    f"Session {sid!r} has event_count={run['event_count']}, "
                    f"expected {expected}.",
                )


if __name__ == "__main__":
    unittest.main()
