"""
tests/test_promote_trace_emit_nonfatal_1102.py

Regression test for captured issue #1102(a) (root-cause), folded into slice
#1086 (PRD #1075 closing pass):

Under `set -euo pipefail`, promote.sh's v3 promotion-span emission
(`python3 tools/trace.py emit --kind promotion ...`) ran AFTER main was
ff-pushed and the one-shot `.claude/PROMOTE_OK` sentinel was consumed. If
that emit call ever failed (non-zero exit), `set -e` propagated the failure
and promote.sh exited non-zero — even though the promotion itself (the ff
push + sentinel consumption + v2 workflow event) had ALREADY succeeded. A
telemetry failure must never mislabel a successful promotion.

Per rule #13 / ADR-0067 D3: this test commit precedes the fix commit in
branch history. These tests FAIL against the un-fixed promote.sh (a failing
trace.py emit exits promote.sh non-zero post-push/post-sentinel-consumption)
and PASS after the fix (the emit failure is caught, warned, and promote.sh
still exits 0 since the real side effect already succeeded).

Isolation (mirrors test_promote_v3_span_1083.py / test_promote_sentinel_order_1038.py):
  - A synthetic git repo (bare origin + working clone) serves as REPO_ROOT so
    promote.sh's git-common-dir resolution never touches the real repo.
  - A deliberately-broken stub tools/trace.py (always exits 1 on `emit`) is
    copied into the synthetic repo in place of the real trace.py — this is
    the "failing trace.py emit" env seam (never a real trace.py failure
    triggered against production data).
  - _PROMOTE_SH_SKIP_PUSH=1 — no real push, ever.

Runner: stdlib unittest + pytest compatible.
    python -m pytest tests/test_promote_trace_emit_nonfatal_1102.py -v
"""

import json
import os
import platform
import re
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
PROMOTE_SH = REPO_ROOT / "tools" / "promote.sh"


def _to_bash_path(win_path: str) -> str:
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
        ["git"] + list(args), cwd=cwd, check=check, capture_output=True, text=True,
    )


def _make_isolated_repo(parent_tmp: str) -> str:
    """Self-contained git repo (bare origin + main + develop). git-common-dir
    == this repo's own .git — never the real repo. A deliberately-BROKEN
    tools/trace.py (exits 1 on `emit`) is copied in as the failure seam."""
    bare = os.path.join(parent_tmp, "bare.git")
    os.makedirs(bare)
    _git("init", "--bare", "-b", "main", bare)

    work = os.path.join(parent_tmp, "work")
    _git("clone", bare, work)
    _git("-C", work, "config", "user.email", "test@example.com")
    _git("-C", work, "config", "user.name", "Test")

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

    # Broken tools/trace.py: `emit` subcommand always exits 1 — simulates a
    # failing trace-emit WITHOUT touching the real emitter or any real log.
    tools_dir = os.path.join(work, "tools")
    os.makedirs(tools_dir, exist_ok=True)
    with open(os.path.join(tools_dir, "trace.py"), "w", newline="\n") as f:
        f.write(
            "#!/usr/bin/env python3\n"
            "import sys\n"
            "if __name__ == '__main__':\n"
            "    sys.exit(1)\n"
        )

    develop_sha = subprocess.run(
        ["git", "-C", work, "rev-parse", "develop"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()

    return work, develop_sha


def _make_stub_health(tmpdir: str, output_line: str) -> str:
    stub_path = os.path.join(tmpdir, "stub_health.sh")
    safe_line = output_line.replace('"', '\\"')
    with open(stub_path, "w", newline="\n") as f:
        f.write("#!/bin/bash\n")
        f.write(f'printf "%s\\n" "{safe_line}"\n')
        f.write("exit 0\n")
    mode = os.stat(stub_path).st_mode
    os.chmod(stub_path, mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return _to_bash_path(stub_path)


class TestFailingTraceEmitDoesNotMislabelSuccessfulPromotion(unittest.TestCase):
    def setUp(self):
        if not PROMOTE_SH.exists():
            self.fail(f"promote.sh not found at {PROMOTE_SH}")
        self.tmp = tempfile.mkdtemp(prefix="promote_trace_emit_nonfatal_1102_")
        self.work, self.develop_sha = _make_isolated_repo(self.tmp)

        self.env = os.environ.copy()
        self.env["MSYS_NO_PATHCONV"] = "1"
        self.env["_PROMOTE_SH_SKIP_PUSH"] = "1"

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _create_sentinel(self):
        sentinel = os.path.join(self.work, ".claude", "PROMOTE_OK")
        os.makedirs(os.path.dirname(sentinel), exist_ok=True)
        with open(sentinel, "w") as f:
            f.write("")
        return sentinel

    def _run_promote(self):
        return subprocess.run(
            ["bash", str(PROMOTE_SH)],
            cwd=self.work, env=self.env, capture_output=True, text=True, timeout=30,
        )

    def test_promote_exits_zero_despite_failing_trace_emit(self):
        """KEY regression: the ff-push + sentinel-consumption + v2 event ALL
        succeed; the v3 span emit then fails (broken stub trace.py) — this
        must NOT flip the overall exit code to non-zero."""
        sentinel = self._create_sentinel()
        self._stub_gate = _make_stub_health(
            self.tmp, "PASS: RELEASE-READY - gate open: stub for test_promote_trace_emit_nonfatal_1102"
        )
        self.env["PROMOTE_HEALTH_CMD"] = f"bash {self._stub_gate}"

        result = self._run_promote()

        self.assertEqual(
            result.returncode, 0,
            msg=(
                "promote.sh must exit 0 when the promotion itself succeeded "
                "(push + sentinel consumption + v2 event) even though the v3 "
                f"trace-span emit failed.\nstdout={result.stdout!r}\nstderr={result.stderr!r}"
            ),
        )
        # Sentinel must have been consumed (one-shot) — proves the real
        # promotion side effect ran to completion, not aborted early.
        self.assertFalse(
            os.path.exists(sentinel),
            msg="sentinel must be consumed on a successful promotion even if the span emit fails",
        )
        # The v2 workflow event must still be present (real side effect proof).
        events_log = os.path.join(self.work, ".claude", "logs", "workflow-events.jsonl")
        self.assertTrue(os.path.exists(events_log), msg="v2 promotion event must still be written")
        with open(events_log, encoding="utf-8") as f:
            events = [json.loads(line) for line in f if line.strip()]
        promotions = [e for e in events if e.get("event") == "promotion"]
        self.assertEqual(len(promotions), 1)
        self.assertEqual(promotions[0]["sha"], self.develop_sha)
        # The emit failure must be visible (loud, not silent) even though
        # non-fatal — surfaced via a WARNING line.
        combined = result.stdout + result.stderr
        self.assertIn("WARNING", combined, msg="a failing trace-span emit must still be reported loudly")


if __name__ == "__main__":
    unittest.main()
