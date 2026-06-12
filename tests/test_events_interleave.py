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

Pytest is the runner on this box (pytest 9.0.3 available). stdlib unittest is
also available as a fallback (run with: python -m unittest tests/test_events_interleave.py).
"""
import json
import tempfile
from pathlib import Path

import pytest

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


def _write_log(lines: list[str], path: Path) -> None:
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Regression test — interleaved session truncation (issue #730)
# ---------------------------------------------------------------------------

class TestInterleaveRegression:
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

    def _build_interleaved_log(self) -> list[str]:
        """Build a log where A and B lines are strictly interleaved: A B A B A."""
        return [
            _make_v2_event(self.TARGET_SID, "session_start",  "2026-06-12T10:00:00Z"),
            _make_v2_event(self.OTHER_SID,  "session_start",  "2026-06-12T10:00:01Z"),
            _make_v2_event(self.TARGET_SID, "tool_use",       "2026-06-12T10:00:02Z"),
            _make_v2_event(self.OTHER_SID,  "tool_use",       "2026-06-12T10:00:03Z"),
            _make_v2_event(self.TARGET_SID, "session_stop",   "2026-06-12T10:00:04Z"),
        ]

    def test_interleaved_session_returns_all_events(self, tmp_path: Path):
        """With interleaved A/B events, fetching session A must return all 3 A events.

        The buggy implementation would return only the first A event (session_start)
        before encountering the first B line and breaking. This test would FAIL on
        that implementation and PASS on the fixed one.
        """
        import sys
        # Ensure the dashboard package is importable from the repo root.
        repo_root = Path(__file__).resolve().parent.parent
        dashboard_dir = str(repo_root / "dashboard")
        if dashboard_dir not in sys.path:
            sys.path.insert(0, dashboard_dir)

        from events import serve_runs  # noqa: PLC0415

        log_path = tmp_path / "workflow-events.jsonl"
        _write_log(self._build_interleaved_log(), log_path)

        result = serve_runs({"session": [self.TARGET_SID]}, log_path)

        assert result.get("run") is not None, (
            "Expected a run dict for TARGET_SID but got None. "
            "This means serve_runs found no events for the target session."
        )
        events = result["run"]["events"]

        # The target session has exactly 3 events: session_start, tool_use, session_stop.
        assert len(events) == 3, (
            f"Expected 3 events for session {self.TARGET_SID!r} but got {len(events)}. "
            f"Events returned: {[e.get('event') for e in events]}. "
            "The interleave defect (break-on-non-matching-line) truncates the list "
            "whenever a different session's line appears between two target-session lines."
        )

        event_types = [e["event"] for e in events]
        assert event_types == ["session_start", "tool_use", "session_stop"], (
            f"Unexpected event order: {event_types}"
        )

    def test_non_interleaved_baseline(self, tmp_path: Path):
        """Baseline: contiguous A events (no interleaving) still return all events.

        This passes even under the buggy implementation — it is the baseline that
        demonstrates the buggy version would appear to work in the simple case.
        """
        import sys
        repo_root = Path(__file__).resolve().parent.parent
        dashboard_dir = str(repo_root / "dashboard")
        if dashboard_dir not in sys.path:
            sys.path.insert(0, dashboard_dir)

        from events import serve_runs  # noqa: PLC0415

        log_path = tmp_path / "workflow-events.jsonl"
        lines = [
            _make_v2_event(self.TARGET_SID, "session_start", "2026-06-12T10:00:00Z"),
            _make_v2_event(self.TARGET_SID, "tool_use",      "2026-06-12T10:00:01Z"),
            _make_v2_event(self.TARGET_SID, "session_stop",  "2026-06-12T10:00:02Z"),
        ]
        _write_log(lines, log_path)

        result = serve_runs({"session": [self.TARGET_SID]}, log_path)
        assert result.get("run") is not None
        assert len(result["run"]["events"]) == 3

    def test_metadata_mode_interleave(self, tmp_path: Path):
        """Metadata mode (?n=2): both sessions appear even with strict interleaving."""
        import sys
        repo_root = Path(__file__).resolve().parent.parent
        dashboard_dir = str(repo_root / "dashboard")
        if dashboard_dir not in sys.path:
            sys.path.insert(0, dashboard_dir)

        from events import serve_runs  # noqa: PLC0415

        log_path = tmp_path / "workflow-events.jsonl"
        _write_log(self._build_interleaved_log(), log_path)

        result = serve_runs({"n": ["2"]}, log_path)
        runs = result.get("runs", [])
        session_ids = {r["session_id"] for r in runs}

        assert self.TARGET_SID in session_ids, (
            f"TARGET_SID {self.TARGET_SID!r} missing from metadata runs: {session_ids}"
        )
        assert self.OTHER_SID in session_ids, (
            f"OTHER_SID {self.OTHER_SID!r} missing from metadata runs: {session_ids}"
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
                assert run["event_count"] == expected, (
                    f"Session {sid!r} has event_count={run['event_count']}, "
                    f"expected {expected}."
                )
