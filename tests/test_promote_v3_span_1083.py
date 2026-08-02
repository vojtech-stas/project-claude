"""
tests/test_promote_v3_span_1083.py

Regression/feature test for slice #1083 (PRD #1075 criterion 1 rider):
promote.sh must append a v3 trace span (kind=promotion) to the canonical
trace log IN THE SAME SUCCESS PATH as its existing v2 workflow-event append —
alongside, not gated behind an extra opt-in. On any refusal path (missing
human-ack sentinel, RELEASE-READY gate not open), NO v3 span may be written.

Per ADR-0067 D3 / rule #13 regression rider: this test commit precedes the
implementation commit in branch history. These tests FAIL against the
un-fixed promote.sh (no v3 span ever written) and PASS after the fix.

Isolation (mirrors test_promote_gate_parse_1036.py / test_promote_ack_880.py):
  - A synthetic git repo (bare origin + working clone) serves as REPO_ROOT so
    promote.sh's git-common-dir resolution never touches the real repo.
  - TRACE_LOG_OVERRIDE points tools/trace.py's canonical log resolution at a
    temp file for this test run only — the real
    <git-common-dir-parent>/.claude/logs/trace-v3.jsonl is never touched
    (rule #21 fixture discipline: fixture data never enters a real log).
  - _PROMOTE_SH_SKIP_PUSH=1 — no real push, ever.

Runner: stdlib unittest + pytest compatible.
  python -m pytest tests/test_promote_v3_span_1083.py -v
"""

import json
import os
import platform
import re
import stat
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
PROMOTE_SH = REPO_ROOT / "tools" / "promote.sh"
TRACE_PY = REPO_ROOT / "tools" / "trace.py"


def _to_bash_path(win_path: str) -> str:
    """Convert a Windows path to a bash-compatible POSIX path for Git Bash."""
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


def _git(*args, cwd=None, check=True):
    return subprocess.run(
        ["git"] + list(args),
        cwd=cwd,
        check=check,
        capture_output=True,
        text=True,
    )


def _make_isolated_repo(parent_tmp: str) -> str:
    """Create a self-contained git repo (bare origin + main + develop) in
    parent_tmp. git-common-dir == this repo's own .git — never the real repo.

    Copies the real tools/trace.py into work/tools/trace.py so promote.sh's
    `$REPO_ROOT/tools/trace.py` invocation (REPO_ROOT == this isolated repo's
    show-toplevel) resolves to a real, working emitter — mirrors how the
    RELEASE-READY gate is stubbed via PROMOTE_HEALTH_CMD in the sibling
    promote.sh tests (test_promote_gate_parse_1036.py), except trace.py has
    no external side effects to stub around, so the real module is copied in.
    """
    bare = os.path.join(parent_tmp, "bare.git")
    os.makedirs(bare)
    _git("init", "--bare", "-b", "main", bare)

    work = os.path.join(parent_tmp, "work")
    _git("clone", bare, work)
    _git("-C", work, "config", "user.email", "test@example.com")
    _git("-C", work, "config", "user.name", "Test")

    import shutil as _shutil
    os.makedirs(os.path.join(work, "tools"), exist_ok=True)
    _shutil.copy(str(TRACE_PY), os.path.join(work, "tools", "trace.py"))

    current = subprocess.run(
        ["git", "-C", work, "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True, text=True,
    ).stdout.strip()
    if current != "main":
        _git("-C", work, "checkout", "-b", "main")

    readme = os.path.join(work, "README.md")
    with open(readme, "w") as f:
        f.write("hello")
    _git("-C", work, "add", "README.md")
    _git("-C", work, "commit", "-m", "init")
    _git("-C", work, "push", "-u", "origin", "HEAD:main")

    _git("-C", work, "checkout", "-b", "develop")
    changes = os.path.join(work, "CHANGES.md")
    with open(changes, "w") as f:
        f.write("dev change")
    _git("-C", work, "add", "CHANGES.md")
    _git("-C", work, "commit", "-m", "dev commit")
    _git("-C", work, "push", "-u", "origin", "develop")

    develop_sha = subprocess.run(
        ["git", "-C", work, "rev-parse", "develop"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()

    return work, develop_sha


def _make_stub_health(tmpdir: str, output_line: str) -> str:
    """Stub script printing `output_line` and exiting 0. Returns bash path."""
    stub_path = os.path.join(tmpdir, "stub_health.sh")
    safe_line = output_line.replace('"', '\\"')
    with open(stub_path, "w", newline="\n") as f:
        f.write("#!/bin/bash\n")
        f.write(f'printf "%s\\n" "{safe_line}"\n')
        f.write("exit 0\n")
    mode = os.stat(stub_path).st_mode
    os.chmod(stub_path, mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return _to_bash_path(stub_path)


class _PromoteV3SpanTestBase(unittest.TestCase):
    def setUp(self):
        if not PROMOTE_SH.exists():
            self.fail(f"promote.sh not found at {PROMOTE_SH}")
        self.tmp = tempfile.mkdtemp(prefix="promote_v3_span_1083_")
        self.work, self.develop_sha = _make_isolated_repo(self.tmp)
        self.trace_log = os.path.join(self.tmp, "trace-v3.jsonl")

        self.env = os.environ.copy()
        self.env["MSYS_NO_PATHCONV"] = "1"
        self.env["_PROMOTE_SH_SKIP_PUSH"] = "1"
        self.env["TRACE_LOG_OVERRIDE"] = self.trace_log

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _create_sentinel(self):
        sentinel = os.path.join(self.work, ".claude", "PROMOTE_OK")
        os.makedirs(os.path.dirname(sentinel), exist_ok=True)
        with open(sentinel, "w") as f:
            f.write("")
        return sentinel

    def _stub_gate(self, output_line):
        health_bash_path = _make_stub_health(self.tmp, output_line)
        self.env["PROMOTE_HEALTH_CMD"] = f"bash {health_bash_path}"

    def _run_promote(self):
        return subprocess.run(
            ["bash", str(PROMOTE_SH)],
            cwd=self.work,
            env=self.env,
            capture_output=True,
            text=True,
            timeout=30,
        )

    def _read_trace_spans(self):
        if not os.path.exists(self.trace_log):
            return []
        spans = []
        with open(self.trace_log, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                spans.append(json.loads(line))
        return spans


class TestV3SpanAppendedOnSuccess(_PromoteV3SpanTestBase):
    """KEY regression: v3 promotion span appended on the success path,
    alongside the existing v2 workflow event, using the same DEVELOP_SHA."""

    def test_span_appended_with_expected_attrs(self):
        self._create_sentinel()
        self._stub_gate(
            "PASS: RELEASE-READY - gate open: stub for test_promote_v3_span_1083"
        )

        result = self._run_promote()

        self.assertEqual(
            result.returncode, 0,
            msg=(
                "promote.sh must exit 0 on the success path.\n"
                f"stdout={result.stdout!r}\nstderr={result.stderr!r}"
            ),
        )

        spans = self._read_trace_spans()
        promotion_spans = [s for s in spans if s.get("kind") == "promotion"]
        self.assertEqual(
            len(promotion_spans), 1,
            msg=(
                "promote.sh must append exactly one v3 span with "
                f"kind=promotion on success. Found: {spans!r}\n"
                f"stdout={result.stdout!r}\nstderr={result.stderr!r}"
            ),
        )
        span = promotion_spans[0]
        self.assertEqual(span.get("v"), 3)
        attrs = span.get("attrs", {})
        self.assertEqual(attrs.get("from"), "develop")
        self.assertEqual(attrs.get("to"), "main")
        self.assertEqual(attrs.get("sha"), self.develop_sha)

    def test_v2_event_and_v3_span_both_present_same_sha(self):
        """Both the pre-existing v2 workflow event AND the new v3 span are
        written on the same success run, sharing the same develop sha —
        proves the 'alongside, same success path' atomic intent."""
        self._create_sentinel()
        self._stub_gate(
            "PASS: RELEASE-READY - gate open: stub for test_promote_v3_span_1083"
        )

        result = self._run_promote()
        self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)

        events_log = os.path.join(self.work, ".claude", "logs", "workflow-events.jsonl")
        self.assertTrue(
            os.path.exists(events_log),
            msg="v2 workflow-events.jsonl must still be written on success",
        )
        with open(events_log, "r", encoding="utf-8") as f:
            v2_lines = [json.loads(line) for line in f if line.strip()]
        v2_promotions = [e for e in v2_lines if e.get("event") == "promotion"]
        self.assertEqual(len(v2_promotions), 1)
        self.assertEqual(v2_promotions[0]["sha"], self.develop_sha)

        spans = self._read_trace_spans()
        promotion_spans = [s for s in spans if s.get("kind") == "promotion"]
        self.assertEqual(len(promotion_spans), 1)
        self.assertEqual(promotion_spans[0]["attrs"]["sha"], self.develop_sha)


class TestV3SpanNotAppendedOnSentinelRefusal(_PromoteV3SpanTestBase):
    """No sentinel -> promote.sh refuses -> no v3 span written at all."""

    def test_no_span_when_sentinel_missing(self):
        # Sentinel deliberately NOT created.
        self._stub_gate(
            "PASS: RELEASE-READY - gate open: stub for test_promote_v3_span_1083"
        )

        result = self._run_promote()

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("PROMOTION REFUSED", result.stdout + result.stderr)
        self.assertFalse(
            os.path.exists(self.trace_log),
            msg=(
                "No v3 span file should be created at all when promote.sh "
                "refuses due to missing sentinel (no span on refusal)."
            ),
        )


class TestV3SpanNotAppendedOnGateRefusal(_PromoteV3SpanTestBase):
    """Sentinel present but RELEASE-READY gate not open -> refuses -> no span."""

    def test_no_span_when_gate_not_open(self):
        self._create_sentinel()
        self._stub_gate(
            "WARN: RELEASE-READY - gate held: condition (a) CI not green"
        )

        result = self._run_promote()

        self.assertNotEqual(result.returncode, 0)
        combined = result.stdout + result.stderr
        self.assertIn("gate not open", combined.lower())
        self.assertFalse(
            os.path.exists(self.trace_log),
            msg=(
                "No v3 span file should be created when the RELEASE-READY "
                "gate is not open (no span on refusal)."
            ),
        )
        # Sentinel must remain untouched (one-shot removal only happens
        # after both gates pass — refusal must be non-destructive).
        sentinel = os.path.join(self.work, ".claude", "PROMOTE_OK")
        self.assertTrue(os.path.exists(sentinel))


if __name__ == "__main__":
    unittest.main()
