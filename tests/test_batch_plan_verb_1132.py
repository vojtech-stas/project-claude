"""
tests/test_batch_plan_verb_1132.py

Regression / new-feature tests for slice #1132 (PRD #1127 §2 criterion 6a) —
the emit-only `tools/pipe/batch-plan` verb.

Covers:
  (a) a real invocation emits exactly one `batch_planned` span with prd/
      pending/ready/blocked/session_id attrs, arrays shaped as lists
  (b) comma-separated lists are split, whitespace-stripped, empty tokens
      dropped; an empty string arg produces an empty list (a legal empty
      set — e.g. `--blocked ""`)
  (c) session_id defaults to "orchestrator" absent CLAUDE_SESSION_ID, and is
      threaded through when the env var is set (mirrors tools/pipe/dispatch)
  (d) repeated invocations append (never overwrite) — one line per call

All spans are written ONLY to a TRACE_LOG_OVERRIDE-pointed tmp file, never
the real ledger (CLAUDE.md rule #21 / R-FIXTURE fixture discipline).

Runner: stdlib unittest + pytest compatible.
  python -m pytest tests/test_batch_plan_verb_1132.py -v
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
BATCH_PLAN = REPO_ROOT / "tools" / "pipe" / "batch-plan"


def _read_jsonl(path):
    p = Path(path)
    if not p.exists():
        return []
    lines = [l.strip() for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
    return [json.loads(l) for l in lines]


class BatchPlanTestBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="batch_plan_test_")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _run(self, args, env_updates=None):
        env = os.environ.copy()
        env.update(env_updates or {})
        cmd = [sys.executable, str(BATCH_PLAN)] + args
        return subprocess.run(
            cmd, capture_output=True, text=True, cwd=str(REPO_ROOT), env=env, timeout=30,
        )


class TestBatchPlanEmitsSpan(BatchPlanTestBase):
    def test_real_invocation_emits_one_batch_planned_span_with_arrays(self):
        log_path = os.path.join(self.tmp, "trace-v3.jsonl")
        result = self._run(
            ["1127", "--pending", "1134,1135", "--ready", "1130,1131", "--blocked", ""],
            {"TRACE_LOG_OVERRIDE": log_path, "CLAUDE_SESSION_ID": "test-session-42"},
        )
        self.assertEqual(result.returncode, 0, f"stdout={result.stdout!r} stderr={result.stderr!r}")
        lines = _read_jsonl(log_path)
        self.assertEqual(len(lines), 1)
        span = lines[0]
        self.assertEqual(span["kind"], "batch_planned")
        self.assertEqual(span["v"], 3)
        attrs = span["attrs"]
        self.assertEqual(attrs["prd"], "1127")
        self.assertEqual(attrs["pending"], ["1134", "1135"])
        self.assertEqual(attrs["ready"], ["1130", "1131"])
        self.assertEqual(attrs["blocked"], [])
        self.assertEqual(attrs["session_id"], "test-session-42")

    def test_whitespace_and_empty_tokens_stripped(self):
        log_path = os.path.join(self.tmp, "trace-v3.jsonl")
        result = self._run(
            ["1127", "--pending", " 1134 , 1135 ,,", "--ready", "", "--blocked", "1200"],
            {"TRACE_LOG_OVERRIDE": log_path},
        )
        self.assertEqual(result.returncode, 0, f"stdout={result.stdout!r} stderr={result.stderr!r}")
        lines = _read_jsonl(log_path)
        attrs = lines[0]["attrs"]
        self.assertEqual(attrs["pending"], ["1134", "1135"])
        self.assertEqual(attrs["ready"], [])
        self.assertEqual(attrs["blocked"], ["1200"])

    def test_session_id_defaults_to_orchestrator(self):
        log_path = os.path.join(self.tmp, "trace-v3.jsonl")
        env = os.environ.copy()
        env.pop("CLAUDE_SESSION_ID", None)
        env["TRACE_LOG_OVERRIDE"] = log_path
        result = subprocess.run(
            [sys.executable, str(BATCH_PLAN), "1127"],
            capture_output=True, text=True, cwd=str(REPO_ROOT), env=env, timeout=30,
        )
        self.assertEqual(result.returncode, 0, f"stdout={result.stdout!r} stderr={result.stderr!r}")
        lines = _read_jsonl(log_path)
        self.assertEqual(lines[0]["attrs"]["session_id"], "orchestrator")

    def test_all_sets_default_empty_when_omitted(self):
        log_path = os.path.join(self.tmp, "trace-v3.jsonl")
        result = self._run(["1127"], {"TRACE_LOG_OVERRIDE": log_path})
        self.assertEqual(result.returncode, 0, f"stdout={result.stdout!r} stderr={result.stderr!r}")
        attrs = _read_jsonl(log_path)[0]["attrs"]
        self.assertEqual(attrs["pending"], [])
        self.assertEqual(attrs["ready"], [])
        self.assertEqual(attrs["blocked"], [])

    def test_repeated_invocations_append_not_overwrite(self):
        log_path = os.path.join(self.tmp, "trace-v3.jsonl")
        env_updates = {"TRACE_LOG_OVERRIDE": log_path}
        r1 = self._run(["1127", "--pending", "1134"], env_updates)
        r2 = self._run(["1127", "--pending", "1135"], env_updates)
        self.assertEqual(r1.returncode, 0)
        self.assertEqual(r2.returncode, 0)
        lines = _read_jsonl(log_path)
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[0]["attrs"]["pending"], ["1134"])
        self.assertEqual(lines[1]["attrs"]["pending"], ["1135"])
        # Same trace_id groups the whole PRD's planning history together.
        self.assertEqual(lines[0]["trace_id"], lines[1]["trace_id"])


if __name__ == "__main__":
    unittest.main()
