"""
Tests for slice #1054 — /api/status last_activity picks the newest of
hook-beacons vs workflow-events, honestly labeled by source.

Problem: the header pill + event panels read only workflow-events.jsonl
(SessionStart events don't fire on resumed sessions, so that log can go
stale for days) while hook-fires.jsonl beacons keep flowing.  The board
falsely reads "no events" / "event 150h ago" while the system is ACTIVE.

Fix under test: _build_status() gains a `last_activity` field = the newer
of {newest hook-beacon ts, newest workflow-event ts}, with a `source` key
identifying which log won ("hook-beacon" | "workflow-event").  The existing
`last_event` field's semantics are preserved unchanged (other consumers may
still rely on it) — last_activity is additive, not a replacement.

Test-first per ADR-0067 D3: this file is committed BEFORE the fix.  Both
tests below FAIL on main (no `last_activity` key exists yet) and PASS after
the fix lands.

Runner: stdlib unittest + pytest compatible.
  python -m pytest tests/test_header_freshness_1054.py -v
"""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
DASHBOARD_DIR = REPO_ROOT / "dashboard"


def _run_dashboard_script(script: str) -> tuple[int, str, str]:
    """Run a Python snippet with dashboard/ on sys.path; return (rc, stdout, stderr)."""
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        cwd=str(DASHBOARD_DIR),
        timeout=30,
    )
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def _call_build_status_with_logs(tmpdir: Path, beacon_lines, event_lines) -> dict:
    """Write fixture hook-fires.jsonl / workflow-events.jsonl under tmpdir/.claude/logs/,
    monkeypatch server._telemetry_log_root() to point there, then call
    server._build_status() and return the parsed JSON result.

    Isolated in a temp dir per rule #21 (fixture discipline) — never touches
    the real .claude/logs/* telemetry store.
    """
    logs_dir = tmpdir / ".claude" / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    (logs_dir / "hook-fires.jsonl").write_text(
        "\n".join(json.dumps(x) for x in beacon_lines) + ("\n" if beacon_lines else ""),
        encoding="utf-8",
    )
    (logs_dir / "workflow-events.jsonl").write_text(
        "\n".join(json.dumps(x) for x in event_lines) + ("\n" if event_lines else ""),
        encoding="utf-8",
    )

    script = f"""
import sys
sys.path.insert(0, r'{DASHBOARD_DIR}')
import server
from pathlib import Path
server._telemetry_log_root = lambda: Path(r'{tmpdir}')
import json
result = server._build_status()
print(json.dumps(result))
"""
    rc, stdout, stderr = _run_dashboard_script(script)
    if rc != 0:
        raise AssertionError(
            f"_build_status() subprocess failed (rc={rc}):\n"
            f"STDOUT: {stdout[:800]}\nSTDERR: {stderr[:800]}"
        )
    try:
        return json.loads(stdout)
    except json.JSONDecodeError as e:
        raise AssertionError(f"_build_status() returned non-JSON: {stdout[:400]}\n{e}")


class TestLastActivityPicksNewest(unittest.TestCase):
    """last_activity = max(newest hook-beacon ts, newest workflow-event ts),
    with source correctly attributing which log won."""

    def test_beacon_newer_picks_hook_beacon(self):
        """Beacon log has a timestamp newer than the events log ->
        last_activity.ts == beacon ts, last_activity.source == 'hook-beacon'."""
        with tempfile.TemporaryDirectory() as td:
            tmpdir = Path(td)
            beacon_lines = [
                {"ts": "2026-07-02T10:00:00Z", "hook": "PostToolUse"},
                {"ts": "2026-07-02T10:05:00Z", "hook": "PreToolUse"},  # newest
            ]
            event_lines = [
                {"ts": "2026-06-28T08:00:00Z", "event": "session_start"},
            ]
            data = _call_build_status_with_logs(tmpdir, beacon_lines, event_lines)

            self.assertIn(
                "last_activity", data,
                msg=f"_build_status() missing 'last_activity' key. Got keys: {sorted(data.keys())}",
            )
            la = data["last_activity"]
            self.assertEqual(
                la.get("ts"), "2026-07-02T10:05:00Z",
                msg=f"last_activity.ts should be the newest beacon ts, got {la!r}",
            )
            self.assertEqual(
                la.get("source"), "hook-beacon",
                msg=f"last_activity.source should be 'hook-beacon' when beacon is newest, got {la!r}",
            )
            self.assertIsInstance(
                la.get("age_minutes"), (int, float),
                msg=f"last_activity.age_minutes must be numeric, got {la!r}",
            )

    def test_event_newer_picks_workflow_event(self):
        """Events log has a timestamp newer than the beacon log ->
        last_activity.ts == event ts, last_activity.source == 'workflow-event'."""
        with tempfile.TemporaryDirectory() as td:
            tmpdir = Path(td)
            beacon_lines = [
                {"ts": "2026-06-20T10:00:00Z", "hook": "PostToolUse"},
            ]
            event_lines = [
                {"ts": "2026-06-28T08:00:00Z", "event": "session_start"},
                {"ts": "2026-07-01T09:30:00Z", "event": "pr_merged"},  # newest
            ]
            data = _call_build_status_with_logs(tmpdir, beacon_lines, event_lines)

            self.assertIn("last_activity", data)
            la = data["last_activity"]
            self.assertEqual(
                la.get("ts"), "2026-07-01T09:30:00Z",
                msg=f"last_activity.ts should be the newest event ts, got {la!r}",
            )
            self.assertEqual(
                la.get("source"), "workflow-event",
                msg=f"last_activity.source should be 'workflow-event' when event is newest, got {la!r}",
            )

    def test_last_event_field_unchanged_alongside_last_activity(self):
        """Existing last_event semantics must survive untouched — last_activity
        is additive, not a replacement (per slice #1054 instructions: 'keep the
        raw last_event semantics ... add last_activity alongside')."""
        with tempfile.TemporaryDirectory() as td:
            tmpdir = Path(td)
            beacon_lines = [{"ts": "2026-07-02T10:05:00Z", "hook": "PreToolUse"}]
            event_lines = [{"ts": "2026-06-28T08:00:00Z", "event": "session_start"}]
            data = _call_build_status_with_logs(tmpdir, beacon_lines, event_lines)

            self.assertIn("last_event", data)
            self.assertEqual(
                data["last_event"].get("ts"), "2026-06-28T08:00:00Z",
                msg="last_event.ts must still reflect only workflow-events.jsonl (unchanged shape)",
            )

    def test_no_logs_at_all_yields_honest_nulls(self):
        """Neither log has any parseable entry -> last_activity.ts is None,
        source is None (no fake data per rule #21)."""
        with tempfile.TemporaryDirectory() as td:
            tmpdir = Path(td)
            data = _call_build_status_with_logs(tmpdir, [], [])

            self.assertIn("last_activity", data)
            la = data["last_activity"]
            self.assertIsNone(la.get("ts"))
            self.assertIsNone(la.get("source"))


if __name__ == "__main__":
    unittest.main()
