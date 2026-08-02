"""
Regression tests for PRD #1075 criterion 8 / slice #1085 — STREAM-LIVENESS.

STREAM-LIVENESS closes the gap between:
  - HOOK-LIVENESS (compares the SINGLE newest beacon across the WHOLE hook
    layer against activity — a live stream masks every dead sibling), and
  - HOOK-INTEGRITY (skips beacon-less streams entirely, deferring "dark"
    detection to HOOK-LIVENESS — which never looks per-stream either).

by tracking every REGISTERED stream against its OWN denominator: a dead
stream is a NAMED FAIL for that stream alone; live siblings still PASS.

Core fixture (silence-one-stream): with a settings.json registering N
streams, and hook-fires.jsonl carrying fresh beacons for N-1 of them but
NONE for one — that one stream must FAIL while the others PASS.

This test file FAILS on develop before slice #1085 (dashboard.health has no
check_stream_liveness / STREAM-LIVENESS registry entry) and PASSES after.

Runner: stdlib unittest + pytest compatible.
  python -m pytest tests/test_stream_liveness_1085.py -v
"""

import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
DASHBOARD_DIR = REPO_ROOT / "dashboard"

# Mirror the module constant so this test doesn't need to import health.py
# directly (subprocess isolation keeps env-var overrides reliable across runs).
_STREAM_LIVENESS_DARK_MINUTES = 60


def _iso(ts: float) -> str:
    import datetime
    return (
        datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc)
        .strftime("%Y-%m-%dT%H:%M:%SZ")
    )


def _write_jsonl(path: Path, lines: list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for obj in lines:
            fh.write(json.dumps(obj) + "\n")


def _write_settings(path: Path, hook_entries: dict) -> None:
    """hook_entries: {event_name: [{"matcher": ..., "hooks": [{"command": ...}]}]}"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"hooks": hook_entries}), encoding="utf-8")


# Two simple direct-beacon hook entries (mirrors session-start.sh / pre-tool-bash.sh
# style — no log-tool-event.sh, telemetry key = filename stem) — a minimal but
# realistic settings.json fixture that STREAM-LIVENESS's discovery must parse.
_TWO_STREAM_SETTINGS = {
    "SessionStart": [
        {"matcher": "", "hooks": [{"type": "command",
         "command": 'bash "$X/.claude/hooks/stream-a.sh"'}]},
    ],
    "PreToolUse": [
        {"matcher": "Bash", "hooks": [{"type": "command",
         "command": 'bash "$X/.claude/hooks/stream-b.sh"'}]},
    ],
}


def _run_check(tmp_dir: Path, settings: dict, fires_lines=None, trace_lines=None,
               now_override: str = None) -> dict:
    """Invoke check_stream_liveness() via subprocess with env-var overrides
    (mirrors tests/test_hook_liveness_849.py's _run_check pattern)."""
    settings_path = tmp_dir / "settings.json"
    _write_settings(settings_path, settings)

    fires_path = tmp_dir / "hook-fires.jsonl"
    if fires_lines is not None:
        _write_jsonl(fires_path, fires_lines)

    trace_path = tmp_dir / "trace-v3.jsonl"
    if trace_lines is not None:
        _write_jsonl(trace_path, trace_lines)

    script = f"""
import sys
sys.path.insert(0, r'{DASHBOARD_DIR}')
import os
os.environ['_STREAM_LIVENESS_SETTINGS_OVERRIDE'] = r'{settings_path}'
os.environ['_STREAM_LIVENESS_FIRES_OVERRIDE'] = r'{fires_path}'
os.environ['_STREAM_LIVENESS_TRACE_OVERRIDE'] = r'{trace_path}'
{"os.environ['_STREAM_LIVENESS_NOW_OVERRIDE'] = " + repr(now_override) if now_override else ""}
from health import check_stream_liveness
import json
print(json.dumps(check_stream_liveness()))
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True, text=True, cwd=str(DASHBOARD_DIR),
    )
    if result.returncode != 0:
        raise AssertionError(
            f"check_stream_liveness() subprocess failed:\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}"
        )
    return json.loads(result.stdout.strip())


class TestStreamLivenessSilenceOneStream(unittest.TestCase):
    """Core acceptance fixture: silence ONE registered stream -> that stream
    FAILs while its sibling PASSes (no aggregate-newest-beacon blindness)."""

    def test_silenced_stream_fails_others_pass(self):
        now = time.time()
        now_iso = _iso(now)
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            result = _run_check(
                tmp_dir,
                _TWO_STREAM_SETTINGS,
                fires_lines=[
                    # stream-b fired 2 minutes ago (fresh) — stream-a NEVER fires.
                    {"hook": "stream-b", "ts": _iso(now - 120)},
                ],
                trace_lines=[
                    {"v": 3, "ts": _iso(now - 60), "kind": "pr_opened"},
                ],
                now_override=now_iso,
            )
        self.assertEqual(
            "FAIL", result["result"],
            msg=f"expected FAIL (stream-a silenced); got {result}",
        )
        fail_names = " ".join(result.get("fail_streams", []))
        self.assertIn(
            "stream-a", fail_names,
            msg=f"stream-a (never fired) must be named in fail_streams: {result}",
        )
        self.assertNotIn(
            "stream-b(", fail_names,
            msg=f"stream-b (fresh beacon) must NOT appear in fail_streams: {result}",
        )
        self.assertIn(
            "stream-b", result["detail"],
            msg=f"stream-b must be reported as live in detail: {result['detail']}",
        )

    def test_all_streams_fresh_is_pass(self):
        now = time.time()
        now_iso = _iso(now)
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            result = _run_check(
                tmp_dir,
                _TWO_STREAM_SETTINGS,
                fires_lines=[
                    {"hook": "stream-a", "ts": _iso(now - 60)},
                    {"hook": "stream-b", "ts": _iso(now - 120)},
                ],
                trace_lines=[
                    {"v": 3, "ts": _iso(now - 30), "kind": "pr_opened"},
                ],
                now_override=now_iso,
            )
        self.assertEqual("PASS", result["result"], msg=f"expected PASS; got {result}")
        self.assertEqual([], result.get("fail_streams", []))

    def test_stale_beacon_beyond_window_fails_that_stream_only(self):
        """A beacon that exists but is OLDER than the dark-minutes window must
        still FAIL that stream (not just 'never fired')."""
        now = time.time()
        now_iso = _iso(now)
        dark_seconds = (_STREAM_LIVENESS_DARK_MINUTES + 10) * 60
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            result = _run_check(
                tmp_dir,
                _TWO_STREAM_SETTINGS,
                fires_lines=[
                    {"hook": "stream-a", "ts": _iso(now - dark_seconds)},  # stale
                    {"hook": "stream-b", "ts": _iso(now - 60)},            # fresh
                ],
                trace_lines=[
                    {"v": 3, "ts": _iso(now - 30), "kind": "pr_opened"},
                ],
                now_override=now_iso,
            )
        self.assertEqual("FAIL", result["result"], msg=result)
        fail_names = " ".join(result.get("fail_streams", []))
        self.assertIn("stream-a", fail_names)
        self.assertNotIn("stream-b(", fail_names)

    def test_trace_v3_stream_tracked_and_can_fail_independently(self):
        """trace-v3 is always a registered stream; silencing it alone must FAIL
        only trace-v3, not the (fresh) hook streams."""
        now = time.time()
        now_iso = _iso(now)
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            result = _run_check(
                tmp_dir,
                _TWO_STREAM_SETTINGS,
                fires_lines=[
                    {"hook": "stream-a", "ts": _iso(now - 60)},
                    {"hook": "stream-b", "ts": _iso(now - 60)},
                ],
                trace_lines=[],  # trace-v3.jsonl exists but is empty — never fired
                now_override=now_iso,
            )
        self.assertEqual("FAIL", result["result"], msg=result)
        fail_names = " ".join(result.get("fail_streams", []))
        self.assertIn("trace-v3", fail_names)


class TestStreamLivenessDegradeCases(unittest.TestCase):
    """Honest WARN degrade — never fabricate PASS/FAIL without data."""

    def test_no_data_anywhere_warns(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            result = _run_check(
                tmp_dir, _TWO_STREAM_SETTINGS,
                fires_lines=None, trace_lines=None,
            )
        self.assertIn(
            result["result"], ("WARN",),
            msg=f"no beacon data anywhere should WARN, not fabricate PASS/FAIL: {result}",
        )

    def test_missing_settings_warns(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            # No settings.json written at all.
            script = f"""
import sys
sys.path.insert(0, r'{DASHBOARD_DIR}')
import os
os.environ['_STREAM_LIVENESS_SETTINGS_OVERRIDE'] = r'{tmp_dir / "missing-settings.json"}'
os.environ['_STREAM_LIVENESS_FIRES_OVERRIDE'] = r'{tmp_dir / "hook-fires.jsonl"}'
os.environ['_STREAM_LIVENESS_TRACE_OVERRIDE'] = r'{tmp_dir / "trace-v3.jsonl"}'
from health import check_stream_liveness
import json
print(json.dumps(check_stream_liveness()))
"""
            result = subprocess.run(
                [sys.executable, "-c", script],
                capture_output=True, text=True, cwd=str(DASHBOARD_DIR),
            )
        self.assertEqual(0, result.returncode, msg=result.stderr)
        parsed = json.loads(result.stdout.strip())
        self.assertEqual("WARN", parsed["result"], msg=parsed)


if __name__ == "__main__":
    unittest.main()
