"""
tests/test_pr_merge_record_green_chain_1134.py

New-feature tests for slice #1134 (PRD #1127 criterion 4, ADR-0076 D1):
tools/pipe/pr-merge's confirmed-MERGED success path tail-chains
tools/pipe/record-green, bounded by pr-merge's own REMAINING wall-clock
budget for that invocation -- never a fresh budget.

Covers:
  (a) chained-call-happens-on-success: a FRESH confirmed merge (both the
      default path and `--confirm` re-entry) invokes record-green for real,
      and record-green's own outcome (develop_green recorded) is named on
      pr-merge's stdout.
  (b) skipped-on-refusal: record-green is NEVER invoked when the verdict
      precondition refuses, nor on the pre-existing "already recorded"
      idempotence shortcut (which does zero new work by design).
  (c) budget-exhaustion named honestly: (c1) when pr-merge's budget is
      already exhausted by the time the chain point is reached, the chain
      is skipped WITHOUT ever spawning record-green, named on stderr;
      (c2) when the chained subprocess itself exceeds the REMAINING budget,
      pr-merge's own bounded `subprocess.run(..., timeout=remaining)` call
      raises TimeoutExpired, named as "TIMED OUT" on stderr -- verified via
      a direct, no-subprocess unit test of `_chain_record_green` (see the
      module docstring rationale below for why this one test bypasses the
      black-box subprocess harness the rest of this file uses).

CRITICAL FIXTURE-SAFETY LESSON (discovered live while writing this suite):
a PATH-prepended fake `gh` stub does NOT reliably reach the gh calls nested
two subprocess hops deep inside record-green.sh (bash -> `python3 -c
"...gh_cache..."` -> `gh`) on this Windows/Git-Bash environment -- the
MSYS<->native-Windows PATH translation across that boundary is not
guaranteed to preserve a prepended directory. Relying on the PATH stub
alone for the CHAINED record-green call let a real `gh pr list` + a REAL
recursive `pytest tests/` run slip through once during development,
spawning a self-perpetuating process tree (record-green.sh -> real pytest
-> this very suite -> more pr-merge invocations -> more record-green.sh...).
Every test below that reaches the confirmed-merge success path THEREFORE
sets record-green.sh's OWN dedicated env-var seam --
`RECORD_GREEN_CI_STATUS` (and `RECORD_GREEN_PYTEST_CMD` where a real
record-green success is wanted) -- which short-circuits record-green.sh's
internal gh-based lookup and/or pytest run BEFORE any nested subprocess
spawns, independent of PATH resolution. `RECORD_GREEN_TEST_LOG_PATH` is
ALSO always set to a per-test temp path (rule #21 fixture discipline --
never the real `.claude/logs/*`).

Fixture discipline (rule #21): every write in these tests targets a temp
path via TRACE_LOG_OVERRIDE / RECORD_GREEN_TEST_LOG_PATH -- never a real
`.claude/logs/*` store.

Runner: stdlib unittest + pytest compatible.
    python -m pytest tests/test_pr_merge_record_green_chain_1134.py -v
"""
import contextlib
import importlib.machinery
import importlib.util
import io
import json
import os
import platform
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
PR_MERGE = REPO_ROOT / "tools" / "pipe" / "pr-merge"

# Bounded external timeout for every subprocess in this file -- a test that
# hangs must fail loudly, never hang the suite (the exact incident this
# module's docstring documents).
_SUBPROCESS_TIMEOUT_S = 30


# ---------------------------------------------------------------------------
# Shared fake-gh fixture (mirrors tests/test_pr_merge_verdict_1130.py /
# tests/test_trace_skeleton_1078.py's pattern) -- used for the OUTER pr-merge
# calls (verdict-comment fetch, merge, REST confirm). NEVER relied on alone
# for the chained record-green call's own internal gh usage (see module
# docstring) -- RECORD_GREEN_CI_STATUS/RECORD_GREEN_PYTEST_CMD own that.
# ---------------------------------------------------------------------------

_FAKE_GH_BODY = """import sys, os, json

def _log_call():
    marker = os.environ.get("FAKE_GH_MARKER_FILE")
    if marker:
        with open(marker, "a", encoding="utf-8") as mf:
            mf.write(" ".join(sys.argv[1:]) + "\\n")

_log_call()
args = sys.argv[1:]
sub0 = args[0] if len(args) > 0 else ""
sub1 = args[1] if len(args) > 1 else ""

if sub0 == "pr" and sub1 == "view":
    out = os.environ.get("FAKE_GH_VIEW_JSON", json.dumps({"comments": []}))
    exit_code = int(os.environ.get("FAKE_GH_VIEW_EXIT", "0"))
    print(out)
    sys.exit(exit_code)
elif sub0 == "pr" and sub1 == "merge":
    exit_code = int(os.environ.get("FAKE_GH_MERGE_EXIT", "0"))
    err = os.environ.get("FAKE_GH_MERGE_STDERR", "")
    if err:
        print(err, file=sys.stderr)
    sys.exit(exit_code)
elif sub0 == "pr" and sub1 == "update-branch":
    sys.exit(int(os.environ.get("FAKE_GH_UPDATE_BRANCH_EXIT", "0")))
elif sub0 == "pr" and sub1 == "checks":
    exit_code = int(os.environ.get("FAKE_GH_CHECKS_EXIT", "0"))
    out = os.environ.get("FAKE_GH_CHECKS_STDOUT", "")
    if out:
        print(out)
    sys.exit(exit_code)
elif sub0 == "api":
    out = os.environ.get("FAKE_GH_API_JSON", "{}")
    print(out)
    sys.exit(int(os.environ.get("FAKE_GH_API_EXIT", "0")))
else:
    sys.exit(0)
"""


def _write_fake_gh(dirpath):
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


class ChainTestBase(unittest.TestCase):
    def setUp(self):
        if not PR_MERGE.exists():
            self.skip_reason = f"tools/pipe/pr-merge not found at {PR_MERGE}"
        else:
            self.skip_reason = None
        self.tmp = tempfile.mkdtemp(prefix="pr_merge_record_green_chain_1134_")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _run(self, args, env_updates):
        if self.skip_reason:
            self.fail(self.skip_reason)
        env = os.environ.copy()
        env.update(env_updates)
        cmd = [sys.executable, str(PR_MERGE)] + args
        return subprocess.run(
            cmd, capture_output=True, text=True, cwd=str(REPO_ROOT), env=env,
            timeout=_SUBPROCESS_TIMEOUT_S,
        )

    def _base_env(self, log_path, fake_gh_dir):
        return {
            "PATH": fake_gh_dir + os.pathsep + os.environ.get("PATH", ""),
            "TRACE_LOG_OVERRIDE": log_path,
        }


# ---------------------------------------------------------------------------
# (a) chained-call-happens-on-success
# ---------------------------------------------------------------------------

class TestChainedOnSuccess(ChainTestBase):
    def test_record_green_chained_and_recorded_on_default_merge(self):
        fake_gh_dir = _write_fake_gh(self.tmp)
        log_path = os.path.join(self.tmp, "trace-v3.jsonl")
        v2_log_path = os.path.join(self.tmp, "workflow-events.jsonl")
        env_updates = self._base_env(log_path, fake_gh_dir)
        env_updates.update({
            "FAKE_GH_VIEW_JSON": json.dumps({"comments": [
                {"body": "VERDICT: APPROVE\nREASON: looks good\nROUND: 1\nCRITIC: reviewer"},
            ]}),
            "FAKE_GH_MERGE_EXIT": "0",
            "FAKE_GH_API_JSON": json.dumps({"merged": True, "merge_commit_sha": "deadbeef"}),
            "PR_MERGE_BUDGET_S": "20",
            # Deterministic record-green success -- bypasses its internal gh
            # lookup AND its real pytest run (see module docstring).
            "RECORD_GREEN_CI_STATUS": "pass",
            "RECORD_GREEN_PYTEST_CMD": "true",
            "RECORD_GREEN_TEST_LOG_PATH": v2_log_path,
        })
        result = self._run(["800"], env_updates)
        self.assertEqual(result.returncode, 0, f"stdout={result.stdout!r} stderr={result.stderr!r}")
        self.assertIn("record-green chained -- develop_green recorded", result.stdout)

        lines = _read_jsonl(log_path)
        kinds = sorted(l["kind"] for l in lines)
        self.assertEqual(kinds, ["develop_green", "pr_merged", "verdict"], f"got {lines}")

        # record-green.sh's own v2 event proves it genuinely ran (not a no-op).
        v2_lines = Path(v2_log_path).read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(v2_lines), 1)
        v2_event = json.loads(v2_lines[0])
        self.assertEqual(v2_event.get("event"), "develop_green")

    def test_record_green_chained_via_confirm_mode_fresh_success(self):
        fake_gh_dir = _write_fake_gh(self.tmp)
        log_path = os.path.join(self.tmp, "trace-v3.jsonl")
        v2_log_path = os.path.join(self.tmp, "workflow-events.jsonl")
        env_updates = self._base_env(log_path, fake_gh_dir)
        env_updates.update({
            "FAKE_GH_VIEW_JSON": json.dumps({"comments": [
                {"body": "VERDICT: APPROVE\nREASON: ok\nROUND: 1\nCRITIC: reviewer"},
            ]}),
            "FAKE_GH_API_JSON": json.dumps({"merged": True, "merge_commit_sha": "cafebabe"}),
            "PR_MERGE_BUDGET_S": "20",
            "RECORD_GREEN_CI_STATUS": "pass",
            "RECORD_GREEN_PYTEST_CMD": "true",
            "RECORD_GREEN_TEST_LOG_PATH": v2_log_path,
        })
        result = self._run(["--confirm", "801"], env_updates)
        self.assertEqual(result.returncode, 0, f"stdout={result.stdout!r} stderr={result.stderr!r}")

        lines = _read_jsonl(log_path)
        kinds = sorted(l["kind"] for l in lines)
        self.assertEqual(kinds, ["develop_green", "pr_merged", "verdict"], f"got {lines}")
        self.assertTrue(os.path.exists(v2_log_path), "record-green must have actually run")


# ---------------------------------------------------------------------------
# (b) skipped-on-refusal / skipped-on-idempotent-shortcut
# ---------------------------------------------------------------------------

class TestChainSkippedWhenNoFreshMerge(ChainTestBase):
    def _trap_env(self, log_path, fake_gh_dir, v2_log_path):
        """A record-green env that WOULD succeed instantly if invoked --
        used as a canary: its v2 event file's absence proves record-green
        was never spawned at all (stronger than merely checking pr-merge's
        own trace log)."""
        env_updates = self._base_env(log_path, fake_gh_dir)
        env_updates.update({
            "RECORD_GREEN_CI_STATUS": "pass",
            "RECORD_GREEN_PYTEST_CMD": "true",
            "RECORD_GREEN_TEST_LOG_PATH": v2_log_path,
        })
        return env_updates

    def test_record_green_not_invoked_when_verdict_refused(self):
        fake_gh_dir = _write_fake_gh(self.tmp)
        log_path = os.path.join(self.tmp, "trace-v3.jsonl")
        v2_log_path = os.path.join(self.tmp, "workflow-events.jsonl")
        env_updates = self._trap_env(log_path, fake_gh_dir, v2_log_path)
        env_updates["FAKE_GH_VIEW_JSON"] = json.dumps({"comments": []})

        result = self._run(["802"], env_updates)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(_read_jsonl(log_path), [], "refusal must write no span")
        self.assertFalse(
            os.path.exists(v2_log_path),
            "record-green must NEVER be spawned when the verdict precondition refuses",
        )

    def test_record_green_not_invoked_on_already_recorded_confirm_shortcut(self):
        """Pre-existing idempotence contract (#1130, unchanged): --confirm on
        an already-recorded PR does zero new work. The record-green chain
        must NOT fire on this shortcut either -- it is not a fresh merge."""
        fake_gh_dir = _write_fake_gh(self.tmp)
        log_path = os.path.join(self.tmp, "trace-v3.jsonl")
        v2_log_path = os.path.join(self.tmp, "workflow-events.jsonl")
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(json.dumps({
                "v": 3, "ts": "2026-08-02T09:00:00Z", "trace_id": "pr-803",
                "span_id": "seed1", "kind": "pr_merged",
                "attrs": {"pr": "803", "sha": "already"},
            }) + "\n")
        env_updates = self._trap_env(log_path, fake_gh_dir, v2_log_path)

        result = self._run(["--confirm", "803"], env_updates)
        self.assertEqual(result.returncode, 0, f"stdout={result.stdout!r} stderr={result.stderr!r}")
        lines = _read_jsonl(log_path)
        self.assertEqual(len(lines), 1, "no develop_green span may be added on the shortcut path")
        self.assertFalse(
            os.path.exists(v2_log_path),
            "record-green must NEVER be spawned on the already-recorded shortcut",
        )


# ---------------------------------------------------------------------------
# (c1) budget already exhausted before the chain point -- black-box
# ---------------------------------------------------------------------------

class TestBudgetExhaustedBeforeChain(ChainTestBase):
    def test_budget_exhausted_before_chain_named_honestly_no_subprocess_spawned(self):
        fake_gh_dir = _write_fake_gh(self.tmp)
        log_path = os.path.join(self.tmp, "trace-v3.jsonl")
        v2_log_path = os.path.join(self.tmp, "workflow-events.jsonl")
        env_updates = self._base_env(log_path, fake_gh_dir)
        env_updates.update({
            "FAKE_GH_VIEW_JSON": json.dumps({"comments": [
                {"body": "VERDICT: APPROVE\nREASON: ok\nROUND: 1\nCRITIC: reviewer"},
            ]}),
            "FAKE_GH_MERGE_EXIT": "0",
            "FAKE_GH_API_JSON": json.dumps({"merged": True, "merge_commit_sha": "0ff1ce"}),
            # Zero budget: by the time _chain_record_green computes
            # `remaining`, real wall-clock time has already elapsed past it
            # (the merge attempt always runs at least once regardless of
            # budget -- see pr-merge's own comment), so this deterministically
            # exercises the "already exhausted" branch every run.
            "PR_MERGE_BUDGET_S": "0",
            # Trap: would succeed instantly if (erroneously) invoked.
            "RECORD_GREEN_CI_STATUS": "pass",
            "RECORD_GREEN_PYTEST_CMD": "true",
            "RECORD_GREEN_TEST_LOG_PATH": v2_log_path,
        })
        result = self._run(["804"], env_updates)
        # The merge itself still succeeds -- budget exhaustion of the CHAINED
        # call must NEVER flip pr-merge's own exit code (#1102 posture).
        self.assertEqual(result.returncode, 0, f"stdout={result.stdout!r} stderr={result.stderr!r}")
        combined = (result.stdout + result.stderr).lower()
        self.assertIn("not chained", combined)
        self.assertIn("exhaust", combined)

        lines = _read_jsonl(log_path)
        kinds = sorted(l["kind"] for l in lines)
        self.assertEqual(kinds, ["pr_merged", "verdict"], f"no develop_green expected, got {lines}")
        self.assertFalse(
            os.path.exists(v2_log_path),
            "record-green must never be spawned once the budget is already exhausted",
        )


# ---------------------------------------------------------------------------
# (c2) chained subprocess itself exceeds the remaining budget -- direct unit
# test of `_chain_record_green`, deliberately bypassing the multi-hop
# bash/pytest subprocess tree (see module docstring: a real slow-subprocess
# repro here left an orphaned process during development because Windows
# `subprocess.run(timeout=...)` only terminates the DIRECT child, not
# further descendants spawned by bash). Mocking `subprocess.run` to raise
# TimeoutExpired directly is the safe way to exercise this branch.
# ---------------------------------------------------------------------------

class TestChainMidFlightTimeoutNamedHonestly(unittest.TestCase):
    def test_timeout_expired_named_honestly_never_raises(self):
        if not PR_MERGE.exists():
            self.skipTest(f"tools/pipe/pr-merge not found at {PR_MERGE}")
        loader = importlib.machinery.SourceFileLoader("pr_merge_chain_timeout_test", str(PR_MERGE))
        spec = importlib.util.spec_from_loader(loader.name, loader)
        mod = importlib.util.module_from_spec(spec)
        loader.exec_module(mod)

        def _raise_timeout(*args, **kwargs):
            raise subprocess.TimeoutExpired(cmd=str(PR_MERGE), timeout=kwargs.get("timeout", 1))

        orig_run = mod.subprocess.run
        mod.subprocess.run = _raise_timeout
        stderr_buf = io.StringIO()
        try:
            with contextlib.redirect_stderr(stderr_buf):
                # remaining > 0 so the function proceeds to the subprocess.run
                # call (which we've made raise TimeoutExpired directly).
                result = mod._chain_record_green(time.monotonic() + 5)
        finally:
            mod.subprocess.run = orig_run

        self.assertIsNone(result, "_chain_record_green must never raise or return a flip signal")
        self.assertIn("TIMED OUT", stderr_buf.getvalue())


if __name__ == "__main__":
    unittest.main()
