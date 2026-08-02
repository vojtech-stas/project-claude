"""
tests/test_pipe_wrappers_1086.py

New-feature tests for slice #1086 (PRD #1075 closing pass, criterion 1
rider): tools/pipe/qa-verify + tools/pipe/record-green.

qa-verify records a qa-tester production-verify verdict as a v2 workflow
event + a v3 trace span (kind=qa_verified), atomically.

record-green ABSORBS the existing tools/record-green.sh (CI-conclusion +
pytest verification, v2 develop_green event) as the one canonical
event-writing path, then additionally appends a v3 span (kind=develop_green)
on the same success run.

Fixture discipline (rule #21): every write in these tests targets a temp
path via the QA_VERIFY_EVENTS_LOG_OVERRIDE / TRACE_LOG_OVERRIDE /
RECORD_GREEN_TEST_LOG_PATH env seams — never a real `.claude/logs/*` store.

Runner: stdlib unittest + pytest compatible.
    python -m pytest tests/test_pipe_wrappers_1086.py -v
"""
import json
import os
import platform
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
QA_VERIFY = REPO_ROOT / "tools" / "pipe" / "qa-verify"
RECORD_GREEN = REPO_ROOT / "tools" / "pipe" / "record-green"


def _to_bash_path(win_path: str) -> str:
    """Convert a Windows path to a bash-compatible POSIX path for Git Bash
    (mirrors tests/test_promote_v3_span_1083.py's helper) — record-green's
    RECORD_GREEN_TEST_LOG_PATH is consumed inside a nested bash script, where
    a bare backslash-separated Windows path breaks `dirname`/`mkdir -p`."""
    if platform.system() != "Windows":
        return win_path
    try:
        result = subprocess.run(
            ["cygpath", "-u", win_path],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    p = win_path.replace("\\", "/")
    p = re.sub(r"^([A-Za-z]):/", lambda m: f"/{m.group(1).lower()}/", p)
    return p


def _read_jsonl(path):
    p = Path(path)
    if not p.exists():
        return []
    lines = [l.strip() for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
    return [json.loads(l) for l in lines]


class TestQaVerify(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="qa_verify_1086_")
        self.events_log = os.path.join(self.tmp, "workflow-events.jsonl")
        self.trace_log = os.path.join(self.tmp, "trace-v3.jsonl")
        self.env = os.environ.copy()
        self.env["QA_VERIFY_EVENTS_LOG_OVERRIDE"] = self.events_log
        self.env["TRACE_LOG_OVERRIDE"] = self.trace_log

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _run(self, args):
        return subprocess.run(
            [sys.executable, str(QA_VERIFY)] + args,
            cwd=str(REPO_ROOT), env=self.env, capture_output=True, text=True, timeout=30,
        )

    def test_pass_verdict_writes_v2_event_and_v3_span(self):
        result = self._run([
            "--verdict", "PASS", "--route", "browser", "--pr", "999", "--prd", "1075",
        ])
        self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)

        events = _read_jsonl(self.events_log)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["event"], "production_verify")
        self.assertEqual(events[0]["verdict"], "PASS")
        self.assertEqual(events[0]["route"], "browser")
        self.assertEqual(events[0]["pr"], "999")
        self.assertEqual(events[0]["prd"], "1075")

        spans = _read_jsonl(self.trace_log)
        qa_spans = [s for s in spans if s.get("kind") == "qa_verified"]
        self.assertEqual(len(qa_spans), 1)
        self.assertEqual(qa_spans[0]["attrs"]["verdict"], "PASS")
        self.assertEqual(qa_spans[0]["attrs"]["route"], "browser")
        self.assertEqual(qa_spans[0]["attrs"]["pr"], "999")
        self.assertEqual(qa_spans[0]["v"], 3)

    def test_fail_and_provisional_verdicts_accepted(self):
        for verdict in ("FAIL", "PROVISIONAL"):
            with self.subTest(verdict=verdict):
                result = self._run(["--verdict", verdict, "--route", "hook-fire"])
                self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)

    def test_invalid_verdict_rejected_no_writes(self):
        result = self._run(["--verdict", "NOPE", "--route", "browser"])
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(os.path.exists(self.events_log))
        self.assertFalse(os.path.exists(self.trace_log))

    def test_unwritable_events_log_exits_nonzero_no_span(self):
        # Point the events-log override at a path whose parent is a FILE
        # (not a directory) — os.makedirs(..., exist_ok=True) will raise.
        blocker = os.path.join(self.tmp, "not_a_dir")
        with open(blocker, "w") as f:
            f.write("x")
        self.env["QA_VERIFY_EVENTS_LOG_OVERRIDE"] = os.path.join(blocker, "sub", "workflow-events.jsonl")

        result = self._run(["--verdict", "PASS", "--route", "static-check"])
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(os.path.exists(self.trace_log), msg="no span may be written when the v2 event write fails")


class TestRecordGreen(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="record_green_pipe_1086_")
        self.events_log = os.path.join(self.tmp, "workflow-events.jsonl")
        self.trace_log = os.path.join(self.tmp, "trace-v3.jsonl")
        self.env = os.environ.copy()
        self.env["RECORD_GREEN_CI_STATUS"] = "pass"
        self.env["RECORD_GREEN_PYTEST_CMD"] = "true"
        self.env["RECORD_GREEN_TEST_LOG_PATH"] = _to_bash_path(self.events_log)
        self.env["TRACE_LOG_OVERRIDE"] = self.trace_log

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _run(self, args=None):
        return subprocess.run(
            [sys.executable, str(RECORD_GREEN)] + (args or []),
            cwd=str(REPO_ROOT), env=self.env, capture_output=True, text=True, timeout=30,
        )

    def test_green_appends_v2_event_and_v3_span_same_sha(self):
        result = self._run()
        self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)

        events = _read_jsonl(self.events_log)
        green_events = [e for e in events if e.get("event") == "develop_green"]
        self.assertEqual(len(green_events), 1)

        spans = _read_jsonl(self.trace_log)
        green_spans = [s for s in spans if s.get("kind") == "develop_green"]
        self.assertEqual(len(green_spans), 1)
        self.assertEqual(green_spans[0]["attrs"]["sha"], green_events[0]["sha"])

    def test_ci_not_green_no_span_nonzero_exit(self):
        self.env["RECORD_GREEN_CI_STATUS"] = "fail"
        result = self._run()
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(os.path.exists(self.trace_log))
        self.assertFalse(os.path.exists(self.events_log))

    def test_dry_run_writes_neither_event_nor_span(self):
        result = self._run(["--dry-run"])
        self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
        self.assertFalse(os.path.exists(self.events_log), msg="--dry-run must write no v2 event")
        self.assertFalse(os.path.exists(self.trace_log), msg="--dry-run must write no v3 span")


if __name__ == "__main__":
    unittest.main()
