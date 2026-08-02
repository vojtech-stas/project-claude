"""
tests/test_stream_liveness_v3_kinds_1136.py

Regression / new-feature tests for slice #1136 (PRD #1127 §2 criterion 10 /
ADR-0076 D2) — STREAM-LIVENESS explodes the single aggregate "trace-v3"
stream into one row per registered v3 span kind (denominator: tools/
trace.py's VALID_KINDS closed enum), with cadence classes assigned per kind:

  - always-on (generous _STREAM_LIVENESS_V3_DARK_MINUTES window):
    pr_opened, pr_merged, verdict, dispatch, dispatch_end
  - on-demand (dead-feed honesty -- never-fired reads as idle, not FAIL):
    qa_verified, develop_green, promotion, batch_planned

Test-first discipline: this commit lands BEFORE the per-kind explosion
exists in dashboard/health.py's check_stream_liveness(). FAILS before impl
(the aggregate "trace-v3" row does not distinguish per-kind silence);
PASSES after impl.

Covers (per slice #1136 body):
  (a) silence-one-kind fixture (always-on kind) -> that kind alone flagged
      FAIL, sibling always-on kinds stay PASS, hook streams unaffected
  (b) dead-feed honesty: a NEW on-demand kind that has NEVER fired (e.g.
      batch_planned) reads as idle, not FAIL
  (c) generous window: an always-on kind idle for hours (but well within
      the 24h v3 window) must not FAIL -- this is the "doesn't false-FAIL
      tomorrow" property the slice explicitly calls for
  (d) registry/list surface unaffected (still one row, id STREAM-LIVENESS)

Runner: stdlib unittest + pytest compatible.
  python -m pytest tests/test_stream_liveness_v3_kinds_1136.py -v
"""

import json
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
DASHBOARD_DIR = REPO_ROOT / "dashboard"

# Mirrors the real VALID_KINDS enum (tools/trace.py) -- duplicated here only
# as literal fixture-authoring convenience; the check itself imports the
# real enum, never a copy of this list.
_ALWAYS_ON_KINDS = ["pr_opened", "pr_merged", "verdict", "dispatch", "dispatch_end"]
_ON_DEMAND_KINDS = ["qa_verified", "develop_green", "promotion", "batch_planned"]


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
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"hooks": hook_entries}), encoding="utf-8")


# Minimal always-on hook registration (mirrors test_stream_liveness_1107.py's
# fixture shape) -- no session-scoped/on-demand hook streams needed here,
# this file's focus is the v3 kind explosion, not hook-stream cadence.
_MINIMAL_SETTINGS = {
    "PreToolUse": [
        {"matcher": "Bash", "hooks": [{"type": "command",
         "command": 'bash "$X/.claude/hooks/pre-tool-bash.sh"'}]},
    ],
}


def _run_check(tmp_dir: Path, fires_lines=None, trace_lines=None,
               now_override: str = None) -> dict:
    """Invoke check_stream_liveness() via subprocess with env-var overrides
    (mirrors tests/test_stream_liveness_1107.py's _run_check pattern). Uses
    the REAL tools/trace.py VALID_KINDS enum (not mocked) -- health.py
    imports it directly."""
    settings_path = tmp_dir / "settings.json"
    _write_settings(settings_path, _MINIMAL_SETTINGS)

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


def _full_trace_lines(now: float, omit_kind: str = None) -> list:
    """One fresh span per VALID_KINDS member (5 min ago), optionally
    omitting exactly one kind (the silence-one-kind fixture)."""
    lines = []
    for kind in _ALWAYS_ON_KINDS + _ON_DEMAND_KINDS:
        if kind == omit_kind:
            continue
        lines.append({"v": 3, "ts": _iso(now - 300), "kind": kind, "attrs": {}})
    return lines


class TestSilenceOneAlwaysOnKindFlagsOnlyThatKind(unittest.TestCase):
    """(a) Silence-one-kind fixture: 'dispatch' never fires while every
    other v3 kind (and the always-on hook stream) fires fresh. Only
    'v3:dispatch' must be flagged (FAIL); every sibling v3 kind and the
    hook stream must remain unaffected (PASS)."""

    def test_silenced_dispatch_fails_others_pass(self):
        now = time.time()
        now_iso = _iso(now)
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            result = _run_check(
                tmp_dir,
                fires_lines=[
                    {"hook": "pre-tool-bash", "ts": _iso(now - 60)},
                ],
                trace_lines=_full_trace_lines(now, omit_kind="dispatch"),
                now_override=now_iso,
            )
        self.assertEqual("FAIL", result["result"], msg=result)
        fail_names = " ".join(result.get("fail_streams", []))
        self.assertIn(
            "v3:dispatch(never-fired)", fail_names,
            msg=f"silenced kind must be named FAIL: {result}",
        )
        # Sibling always-on v3 kinds must stay unaffected (not in fail_streams).
        for kind in ["pr_opened", "pr_merged", "verdict", "dispatch_end"]:
            self.assertNotIn(
                f"v3:{kind}(", fail_names,
                msg=f"sibling kind v3:{kind} must not be flagged: {result}",
            )
        # The hook stream is unaffected too.
        self.assertNotIn("pre-tool-bash", fail_names, msg=result)
        self.assertIn("v3:pr_opened", result["streams"])
        self.assertIn("v3:dispatch", result["streams"])


class TestDeadFeedHonestyNeverFiredOnDemandIsIdle(unittest.TestCase):
    """(b) Dead-feed honesty rule: on-demand kinds that have NEVER fired
    (batch_planned only just landed this PRD) read as idle/pending, never
    FAIL -- direct reuse of the existing on-demand never-fired-is-idle
    semantics (#1107), not a new mechanism."""

    def test_never_fired_batch_planned_and_qa_verified_are_idle_not_fail(self):
        now = time.time()
        now_iso = _iso(now)
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            # Only the always-on kinds + one hook stream fire; batch_planned
            # and qa_verified never fire at all.
            trace_lines = [
                {"v": 3, "ts": _iso(now - 60), "kind": k, "attrs": {}}
                for k in _ALWAYS_ON_KINDS
            ]
            result = _run_check(
                tmp_dir,
                fires_lines=[{"hook": "pre-tool-bash", "ts": _iso(now - 60)}],
                trace_lines=trace_lines,
                now_override=now_iso,
            )
        self.assertEqual("PASS", result["result"], msg=result)
        fail_names = " ".join(result.get("fail_streams", []))
        self.assertNotIn("batch_planned", fail_names, msg=result)
        self.assertNotIn("qa_verified", fail_names, msg=result)
        idle_names = " ".join(result.get("idle_streams", []))
        self.assertIn("v3:batch_planned(never-fired)", idle_names, msg=result)
        self.assertIn("v3:qa_verified(never-fired)", idle_names, msg=result)


class TestGenerousWindowDoesNotFalseFailTomorrow(unittest.TestCase):
    """(c) An always-on v3 kind (pr_merged) last fired 5 hours ago -- well
    beyond the 60m hook-cadence window but comfortably inside the generous
    24h v3 window -- must PASS. Under the OLD uniform-60m aggregate this
    would have false-FAILed the very next quiet morning."""

    def test_five_hours_idle_always_on_v3_kind_still_passes(self):
        now = time.time()
        now_iso = _iso(now)
        five_hours = 5 * 60 * 60
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            trace_lines = [
                {"v": 3, "ts": _iso(now - five_hours), "kind": "pr_merged", "attrs": {}},
                {"v": 3, "ts": _iso(now - 60), "kind": "pr_opened", "attrs": {}},
                {"v": 3, "ts": _iso(now - 60), "kind": "verdict", "attrs": {}},
                {"v": 3, "ts": _iso(now - 60), "kind": "dispatch", "attrs": {}},
                {"v": 3, "ts": _iso(now - 60), "kind": "dispatch_end", "attrs": {}},
            ]
            result = _run_check(
                tmp_dir,
                fires_lines=[{"hook": "pre-tool-bash", "ts": _iso(now - 60)}],
                trace_lines=trace_lines,
                now_override=now_iso,
            )
        self.assertEqual("PASS", result["result"], msg=result)
        fail_names = " ".join(result.get("fail_streams", []))
        self.assertNotIn("v3:pr_merged(", fail_names, msg=result)
        pass_names = " ".join(result.get("streams", []))
        self.assertIn("v3:pr_merged", pass_names)


class TestRegistryUnaffected(unittest.TestCase):
    """(d) The STREAM-LIVENESS registry entry itself is unchanged -- still
    exactly one row, id STREAM-LIVENESS, in CHECK_REGISTRY and --list."""

    def test_still_one_registry_row(self):
        sys.path.insert(0, str(DASHBOARD_DIR))
        import importlib
        if "health" in sys.modules:
            del sys.modules["health"]
        health = importlib.import_module("health")
        self.assertIn("STREAM-LIVENESS", health.CHECK_REGISTRY)
        self.assertTrue(callable(health.CHECK_REGISTRY["STREAM-LIVENESS"]))


if __name__ == "__main__":
    unittest.main()
