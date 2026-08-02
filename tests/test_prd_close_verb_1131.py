"""
tests/test_prd_close_verb_1131.py

New-feature tests for slice #1131 (PRD #1127 §2 criterion 5 / ADR-0076 D1):
`tools/pipe/prd-close` — the precondition-checked verb wrapping the PRD
issue-closure transition.

Covers PRD #1127 §2 criterion 5: `prd-close <prd>` refuses (non-zero exit,
named reason, NO gh side effect) unless the canonical v3 trace ledger holds
a `qa_verified` span with `attrs.prd == <prd>` and `attrs.verdict == "PASS"`;
on that precondition it runs `gh issue close <prd> --reason completed`
(optionally with `--comment <text>`) as its sole side effect.

Fixture discipline (rule #21): every test targets a temp trace log via
TRACE_LOG_OVERRIDE and a fake `gh` binary shadowing PATH — never a real
`.claude/logs/*` store, and never a real GitHub issue is closed.

prd-close is deliberately a zero-`emit_span` wrapper (GitHub issue-state is
the cross-checked ground truth; the CLOSED-PRD-VS-QA reconciler, slice
#1136, cross-checks it) — these tests therefore assert the trace log is
NEVER appended to by this verb, on either the refusal or the success path.

Runner: stdlib unittest + pytest compatible.
  python -m pytest tests/test_prd_close_verb_1131.py -v
"""

import json
import os
import platform
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
PRD_CLOSE = REPO_ROOT / "tools" / "pipe" / "prd-close"


_FAKE_GH_BODY = """import sys, os

def _log_call():
    marker = os.environ.get("FAKE_GH_MARKER_FILE")
    if marker:
        with open(marker, "a", encoding="utf-8") as mf:
            mf.write(" ".join(sys.argv[1:]) + "\\n")

_log_call()
sys.exit(int(os.environ.get("FAKE_GH_CLOSE_EXIT", "0")))
"""


def _write_fake_gh(dirpath):
    """Write a fake `gh` binary into dirpath; prepend dirpath to PATH to
    shadow the real `gh`. Records every invocation to FAKE_GH_MARKER_FILE
    (if set) so tests can assert whether/how `gh issue close` was called —
    never touching a real GitHub issue."""
    if platform.system() == "Windows":
        impl_path = os.path.join(dirpath, "_fake_gh_impl.py")
        with open(impl_path, "w", encoding="utf-8") as f:
            f.write(_FAKE_GH_BODY)
        bat_path = os.path.join(dirpath, "gh.bat")
        with open(bat_path, "w", encoding="utf-8", newline="\r\n") as f:
            f.write(f'@echo off\r\n"{sys.executable}" "{impl_path}" %*\r\n')
    else:
        sh_path = os.path.join(dirpath, "gh")
        with open(sh_path, "w", encoding="utf-8") as f:
            f.write("#!/usr/bin/env python3\n")
            f.write(_FAKE_GH_BODY)
        os.chmod(sh_path, 0o755)
    return dirpath


def _read_jsonl(path):
    p = Path(path)
    if not p.exists():
        return []
    lines = [l.strip() for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
    return [json.loads(l) for l in lines]


def _qa_verified_span(prd, verdict, ts="2026-08-02T09:00:00Z", span_id="qa1"):
    return {
        "v": 3, "ts": ts, "trace_id": f"qa-{prd}", "span_id": span_id,
        "kind": "qa_verified", "attrs": {"prd": str(prd), "verdict": verdict, "route": "static"},
    }


class PrdCloseTestBase(unittest.TestCase):
    def setUp(self):
        self.assertTrue(PRD_CLOSE.exists(), f"tools/pipe/prd-close not found at {PRD_CLOSE}")
        self.tmp = tempfile.mkdtemp(prefix="prd_close_test_")
        self.log_path = os.path.join(self.tmp, "trace-v3.jsonl")
        self.marker_path = os.path.join(self.tmp, "gh-calls.log")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _run(self, args, env_updates=None):
        env = os.environ.copy()
        fake_gh_dir = _write_fake_gh(self.tmp)
        env["PATH"] = fake_gh_dir + os.pathsep + env.get("PATH", "")
        env["TRACE_LOG_OVERRIDE"] = self.log_path
        env["FAKE_GH_MARKER_FILE"] = self.marker_path
        if env_updates:
            env.update(env_updates)
        cmd = [sys.executable, str(PRD_CLOSE)] + args
        return subprocess.run(cmd, capture_output=True, text=True, cwd=str(REPO_ROOT), env=env, timeout=30)

    def _gh_calls(self):
        p = Path(self.marker_path)
        if not p.exists():
            return []
        return [l for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


# ---------------------------------------------------------------------------
# Refusal: no qa_verified PASS span for this PRD
# ---------------------------------------------------------------------------

class TestRefusalWithoutQaVerifiedPass(PrdCloseTestBase):
    def test_empty_ledger_refused_no_gh_call(self):
        result = self._run(["1127"])
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self._gh_calls(), [], "no gh side effect may run on refusal")
        self.assertEqual(_read_jsonl(self.log_path), [], "prd-close must never write a span")

    def test_pass_span_for_different_prd_refused(self):
        with open(self.log_path, "w", encoding="utf-8") as f:
            f.write(json.dumps(_qa_verified_span(9999, "PASS")) + "\n")
        result = self._run(["1127"])
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self._gh_calls(), [])

    def test_fail_verdict_for_this_prd_refused(self):
        with open(self.log_path, "w", encoding="utf-8") as f:
            f.write(json.dumps(_qa_verified_span(1127, "FAIL")) + "\n")
        result = self._run(["1127"])
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self._gh_calls(), [])

    def test_provisional_verdict_for_this_prd_refused(self):
        with open(self.log_path, "w", encoding="utf-8") as f:
            f.write(json.dumps(_qa_verified_span(1127, "PROVISIONAL")) + "\n")
        result = self._run(["1127"])
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self._gh_calls(), [])


# ---------------------------------------------------------------------------
# Success: qa_verified PASS span present for this PRD
# ---------------------------------------------------------------------------

class TestSuccessAfterQaVerifiedPass(PrdCloseTestBase):
    def test_pass_span_present_closes_issue_no_span_written(self):
        with open(self.log_path, "w", encoding="utf-8") as f:
            f.write(json.dumps(_qa_verified_span(1127, "PASS")) + "\n")
        result = self._run(["1127"])
        self.assertEqual(result.returncode, 0, f"stdout={result.stdout!r} stderr={result.stderr!r}")

        calls = self._gh_calls()
        self.assertEqual(len(calls), 1)
        self.assertIn("issue close 1127", calls[0])
        self.assertIn("--reason completed", calls[0])

        # prd-close is a zero-emit_span wrapper — the pre-seeded span must
        # be the ONLY line in the log; no new span appended.
        lines = _read_jsonl(self.log_path)
        self.assertEqual(len(lines), 1)

    def test_comment_flag_passed_through_to_gh(self):
        with open(self.log_path, "w", encoding="utf-8") as f:
            f.write(json.dumps(_qa_verified_span(1127, "PASS")) + "\n")
        result = self._run(["1127", "--comment", "13 PASS, 0 residuals"])
        self.assertEqual(result.returncode, 0, f"stdout={result.stdout!r} stderr={result.stderr!r}")
        calls = self._gh_calls()
        self.assertEqual(len(calls), 1)
        self.assertIn("--comment 13 PASS, 0 residuals", calls[0])

    def test_gh_close_failure_propagates_nonzero(self):
        with open(self.log_path, "w", encoding="utf-8") as f:
            f.write(json.dumps(_qa_verified_span(1127, "PASS")) + "\n")
        result = self._run(["1127"], env_updates={"FAKE_GH_CLOSE_EXIT": "7"})
        self.assertEqual(result.returncode, 7)


# ---------------------------------------------------------------------------
# Usage / arg parsing
# ---------------------------------------------------------------------------

class TestUsage(PrdCloseTestBase):
    def test_no_args_refused_usage(self):
        result = self._run([])
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self._gh_calls(), [])

    def test_dangling_comment_flag_refused_usage(self):
        with open(self.log_path, "w", encoding="utf-8") as f:
            f.write(json.dumps(_qa_verified_span(1127, "PASS")) + "\n")
        result = self._run(["1127", "--comment"])
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self._gh_calls(), [])


if __name__ == "__main__":
    unittest.main()
