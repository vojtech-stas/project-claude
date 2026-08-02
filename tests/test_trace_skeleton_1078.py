"""
tests/test_trace_skeleton_1078.py

Regression / new-feature tests for slice #1078 (PRD #1075 walking skeleton) —
the v3 pipeline trace-span emitter, the pr-open/pr-merge wrapper CLIs, and the
crude linear-scan acid-test causal-path query.

Test-first discipline (rule #13 rider / ADR-0067 D3 shape, applied here to a
new-feature slice per the slice's own instruction): this commit lands BEFORE
`tools/trace.py` / `tools/pipe/pr-open` / `tools/pipe/pr-merge` exist.

FAILS before impl: every test below errors (ImportError / FileNotFoundError)
because the modules under test do not exist yet.
PASSES after impl: tools/trace.py + tools/pipe/pr-open + tools/pipe/pr-merge
land in the next commit and satisfy every assertion here.

Covers PRD #1075 criteria 1 / 2a / 2b (walking-skeleton slice):
  (a) emit_span writes a valid v3 line to a temp-pointed log
      (TRACE_LOG_OVERRIDE env seam, mirrors telemetry_root's override pattern)
  (b) pr-open: atomic gh-call + span-append; STUBBED gh (fake bin on PATH):
        - gh succeeds -> span appended, PR number/branch/slice attrs correct
        - gh fails -> exits non-zero, NO span written
        - log path unwritable -> exits non-zero, gh NEVER executed (writability
          is validated BEFORE the gh side effect — no half-success)
  (c) pr-merge: sanctioned protocol wrapper
        - merged -> pr_merged span appended (pr, sha, dur)
        - not-merged after bounded retries -> exits non-zero, NO span written
  (d) acid query (`python tools/trace.py path --pr <n>`):
        - fixture spans -> ordered causal-path output (ts-ordered, includes
          same-trace_id "parent" spans lacking attrs.pr)
        - unknown PR -> non-zero exit + explicit "no recorded trace" error

Runner: stdlib unittest + pytest compatible.
  python -m pytest tests/test_trace_skeleton_1078.py -v
"""

import importlib.util
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
TOOLS_DIR = REPO_ROOT / "tools"
TRACE_PY = TOOLS_DIR / "trace.py"
PR_OPEN = TOOLS_DIR / "pipe" / "pr-open"
PR_MERGE = TOOLS_DIR / "pipe" / "pr-merge"


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _load_trace_module():
    """Import tools/trace.py under a distinct module name (never "trace" —
    that shadows/collides with the stdlib `trace` coverage module)."""
    if not TRACE_PY.exists():
        raise FileNotFoundError(f"tools/trace.py not found at {TRACE_PY}")
    spec = importlib.util.spec_from_file_location("trace_v3_test", TRACE_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


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

if sub0 == "pr" and sub1 == "create":
    exit_code = int(os.environ.get("FAKE_GH_CREATE_EXIT", "0"))
    out = os.environ.get("FAKE_GH_CREATE_STDOUT", "https://github.com/o/r/pull/1")
    err = os.environ.get("FAKE_GH_CREATE_STDERR", "")
    if out:
        print(out)
    if err:
        print(err, file=sys.stderr)
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
elif sub0 == "pr" and sub1 == "view":
    # slice #1130: pr-merge's verdict-assertion precondition calls this same
    # gh form (mirrors .claude/hooks/stop-reviewer-gate.sh). Default fixture
    # carries a matching reviewer APPROVE comment so pre-#1130 pr-merge tests
    # keep passing unmodified; override via FAKE_GH_VIEW_JSON to exercise the
    # refusal path.
    default_view = json.dumps({"comments": [{"body": "VERDICT: APPROVE\\nROUND: 1\\nCRITIC: reviewer"}]})
    out = os.environ.get("FAKE_GH_VIEW_JSON", default_view)
    exit_code = int(os.environ.get("FAKE_GH_VIEW_EXIT", "0"))
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
    """Write a fake `gh` binary into dirpath; prepend dirpath to PATH to
    shadow the real `gh`. One fixture script serves every scenario below —
    behavior is selected entirely via env vars at call time (FAKE_GH_*).
    Returns dirpath (the directory to prepend to PATH).
    """
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


# ---------------------------------------------------------------------------
# (a) emit_span writes a valid v3 line to a temp-pointed log
# ---------------------------------------------------------------------------

class TestEmitSpan(unittest.TestCase):
    def setUp(self):
        self._orig_override = os.environ.get("TRACE_LOG_OVERRIDE")

    def tearDown(self):
        if self._orig_override is None:
            os.environ.pop("TRACE_LOG_OVERRIDE", None)
        else:
            os.environ["TRACE_LOG_OVERRIDE"] = self._orig_override

    def test_emit_span_writes_valid_v3_line(self):
        mod = _load_trace_module()
        with tempfile.TemporaryDirectory() as tmp:
            log_path = os.path.join(tmp, "trace-v3.jsonl")
            os.environ["TRACE_LOG_OVERRIDE"] = log_path

            record = mod.emit_span(
                trace_id="pr-1",
                kind="pr_opened",
                attrs={"pr": "1", "branch": "feat/x"},
            )

            self.assertTrue(os.path.exists(log_path), "emit_span must create the log file")
            lines = _read_jsonl(log_path)
            self.assertEqual(len(lines), 1, f"expected exactly 1 line, got {lines}")
            line = lines[0]

            self.assertEqual(line["v"], 3)
            self.assertIn("ts", line)
            self.assertTrue(line["ts"].endswith("Z"), f"ts must be UTC ISO ending in Z: {line['ts']!r}")
            self.assertEqual(line["trace_id"], "pr-1")
            self.assertEqual(line["kind"], "pr_opened")
            self.assertEqual(line["attrs"], {"pr": "1", "branch": "feat/x"})
            # span_id auto-generated when omitted
            self.assertIn("span_id", line)
            self.assertTrue(len(line["span_id"]) > 0)
            self.assertEqual(record["span_id"], line["span_id"])

    def test_emit_span_respects_explicit_span_and_parent(self):
        mod = _load_trace_module()
        with tempfile.TemporaryDirectory() as tmp:
            log_path = os.path.join(tmp, "trace-v3.jsonl")
            os.environ["TRACE_LOG_OVERRIDE"] = log_path

            mod.emit_span(
                trace_id="pr-2",
                kind="pr_merged",
                span_id="s2",
                parent_span_id="s1",
                attrs={"pr": "2"},
                dur_ms=1234,
            )
            lines = _read_jsonl(log_path)
            self.assertEqual(lines[0]["span_id"], "s2")
            self.assertEqual(lines[0]["parent_span_id"], "s1")
            self.assertEqual(lines[0]["dur_ms"], 1234)

    def test_emit_span_appends_not_overwrites(self):
        mod = _load_trace_module()
        with tempfile.TemporaryDirectory() as tmp:
            log_path = os.path.join(tmp, "trace-v3.jsonl")
            os.environ["TRACE_LOG_OVERRIDE"] = log_path
            mod.emit_span(trace_id="pr-3", kind="pr_opened", attrs={"pr": "3"})
            mod.emit_span(trace_id="pr-3", kind="pr_merged", attrs={"pr": "3"})
            lines = _read_jsonl(log_path)
            self.assertEqual(len(lines), 2)


# ---------------------------------------------------------------------------
# (b) pr-open — atomic gh-call + span-append, stubbed gh on PATH
# ---------------------------------------------------------------------------

class TestPrOpen(unittest.TestCase):
    def setUp(self):
        if not PR_OPEN.exists():
            self.skip_reason = f"tools/pipe/pr-open not found at {PR_OPEN}"
        else:
            self.skip_reason = None
        self.tmp = tempfile.mkdtemp(prefix="pr_open_test_")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _run(self, args, env_updates, cwd=None):
        if self.skip_reason:
            self.fail(self.skip_reason)  # must FAIL (not skip) pre-impl
        env = os.environ.copy()
        env.update(env_updates)
        cmd = [sys.executable, str(PR_OPEN)] + args
        return subprocess.run(cmd, capture_output=True, text=True, cwd=cwd or str(REPO_ROOT), env=env, timeout=30)

    def test_gh_success_appends_pr_opened_span(self):
        fake_gh_dir = _write_fake_gh(self.tmp)
        log_path = os.path.join(self.tmp, "trace-v3.jsonl")
        body_file = os.path.join(self.tmp, "body.md")
        with open(body_file, "w", encoding="utf-8") as f:
            f.write("Some PR body.\n\nCloses #1078\n")

        env_updates = {
            "PATH": fake_gh_dir + os.pathsep + os.environ.get("PATH", ""),
            "TRACE_LOG_OVERRIDE": log_path,
            "FAKE_GH_CREATE_EXIT": "0",
            "FAKE_GH_CREATE_STDOUT": "https://github.com/o/r/pull/4242",
        }
        result = self._run(
            ["--title", "t", "--body-file", body_file, "--base", "develop", "--head", "feat/1078-x"],
            env_updates,
        )
        self.assertEqual(result.returncode, 0, f"stdout={result.stdout!r} stderr={result.stderr!r}")
        lines = _read_jsonl(log_path)
        self.assertEqual(len(lines), 1, f"expected exactly 1 pr_opened span, got {lines}")
        span = lines[0]
        self.assertEqual(span["kind"], "pr_opened")
        self.assertEqual(span["attrs"]["pr"], "4242")
        self.assertEqual(span["attrs"]["branch"], "feat/1078-x")
        self.assertEqual(span["attrs"].get("slice"), "1078")

    def test_gh_failure_no_span_written(self):
        fake_gh_dir = _write_fake_gh(self.tmp)
        log_path = os.path.join(self.tmp, "trace-v3.jsonl")
        env_updates = {
            "PATH": fake_gh_dir + os.pathsep + os.environ.get("PATH", ""),
            "TRACE_LOG_OVERRIDE": log_path,
            "FAKE_GH_CREATE_EXIT": "1",
            "FAKE_GH_CREATE_STDERR": "gh: boom",
        }
        result = self._run(["--title", "t", "--body", "x"], env_updates)
        self.assertNotEqual(result.returncode, 0)
        lines = _read_jsonl(log_path)
        self.assertEqual(len(lines), 0, f"gh failure must write NO span; got {lines}")

    def test_log_unwritable_gh_never_executed(self):
        """Writability is validated FIRST — if the log path can't be created,
        gh must never run (no half-success: no PR created without a span)."""
        fake_gh_dir = _write_fake_gh(self.tmp)
        marker = os.path.join(self.tmp, "gh_was_called.marker")

        # A path with a FILE as an intermediate component can never be mkdir'd.
        blocker = os.path.join(self.tmp, "blocker.txt")
        with open(blocker, "w", encoding="utf-8") as f:
            f.write("x")
        bad_log_path = os.path.join(blocker, "trace-v3.jsonl")

        env_updates = {
            "PATH": fake_gh_dir + os.pathsep + os.environ.get("PATH", ""),
            "TRACE_LOG_OVERRIDE": bad_log_path,
            "FAKE_GH_CREATE_EXIT": "0",
            "FAKE_GH_MARKER_FILE": marker,
        }
        result = self._run(["--title", "t", "--body", "x"], env_updates)
        self.assertNotEqual(result.returncode, 0, "unwritable log path must fail non-zero")
        self.assertFalse(
            os.path.exists(marker),
            "gh must NEVER be invoked when the log path is unwritable (validate-first ordering)",
        )


# ---------------------------------------------------------------------------
# (c) pr-merge — sanctioned merge protocol wrapper
# ---------------------------------------------------------------------------

class TestPrMerge(unittest.TestCase):
    def setUp(self):
        if not PR_MERGE.exists():
            self.skip_reason = f"tools/pipe/pr-merge not found at {PR_MERGE}"
        else:
            self.skip_reason = None
        self.tmp = tempfile.mkdtemp(prefix="pr_merge_test_")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _run(self, args, env_updates, cwd=None):
        if self.skip_reason:
            self.fail(self.skip_reason)
        env = os.environ.copy()
        env.update(env_updates)
        cmd = [sys.executable, str(PR_MERGE)] + args
        return subprocess.run(cmd, capture_output=True, text=True, cwd=cwd or str(REPO_ROOT), env=env, timeout=60)

    def test_merged_appends_pr_merged_span(self):
        fake_gh_dir = _write_fake_gh(self.tmp)
        log_path = os.path.join(self.tmp, "trace-v3.jsonl")
        env_updates = {
            "PATH": fake_gh_dir + os.pathsep + os.environ.get("PATH", ""),
            "TRACE_LOG_OVERRIDE": log_path,
            "FAKE_GH_MERGE_EXIT": "0",
            "FAKE_GH_API_JSON": json.dumps({"merged": True, "merge_commit_sha": "deadbeef123"}),
            "PR_MERGE_POLL_TIMEOUT_S": "0",
            "PR_MERGE_CONFIRM_TIMEOUT_S": "0",
        }
        result = self._run(["777"], env_updates)
        self.assertEqual(result.returncode, 0, f"stdout={result.stdout!r} stderr={result.stderr!r}")
        lines = _read_jsonl(log_path)
        # slice #1130: a confirmed merge now also appends a verdict span
        # alongside pr_merged (ADR-0076 D3 criterion 3b).
        self.assertEqual(len(lines), 2, f"expected pr_merged + verdict spans, got {lines}")
        merged_spans = [l for l in lines if l["kind"] == "pr_merged"]
        self.assertEqual(len(merged_spans), 1, f"expected exactly 1 pr_merged span, got {lines}")
        span = merged_spans[0]
        self.assertEqual(span["kind"], "pr_merged")
        self.assertEqual(span["attrs"]["pr"], "777")
        self.assertEqual(span["attrs"]["sha"], "deadbeef123")
        verdict_spans = [l for l in lines if l["kind"] == "verdict"]
        self.assertEqual(len(verdict_spans), 1, f"expected exactly 1 verdict span, got {lines}")
        self.assertEqual(verdict_spans[0]["attrs"]["pr"], "777")
        self.assertEqual(verdict_spans[0]["attrs"]["verdict"], "APPROVE")
        self.assertEqual(verdict_spans[0]["attrs"]["critic"], "reviewer")
        self.assertEqual(verdict_spans[0]["attrs"]["round"], "1")

    def test_not_merged_after_retries_no_span(self):
        fake_gh_dir = _write_fake_gh(self.tmp)
        log_path = os.path.join(self.tmp, "trace-v3.jsonl")
        env_updates = {
            "PATH": fake_gh_dir + os.pathsep + os.environ.get("PATH", ""),
            "TRACE_LOG_OVERRIDE": log_path,
            "FAKE_GH_MERGE_EXIT": "1",
            "FAKE_GH_MERGE_STDERR": "GraphQL: Auto merge is not allowed for this repository",
            "FAKE_GH_UPDATE_BRANCH_EXIT": "0",
            "FAKE_GH_CHECKS_EXIT": "1",
            "FAKE_GH_CHECKS_STDOUT": "some-check FAILED",
            "PR_MERGE_POLL_TIMEOUT_S": "0",
            "PR_MERGE_CONFIRM_TIMEOUT_S": "0",
        }
        result = self._run(["778"], env_updates)
        self.assertNotEqual(result.returncode, 0)
        lines = _read_jsonl(log_path)
        self.assertEqual(len(lines), 0, f"unmerged PR must write NO span; got {lines}")


class TestPrMergePendingConfirm(unittest.TestCase):
    """Regression for reviewer round-1 finding #2 (PR #1089): the default
    invocation must never block past a small bounded budget (a synchronous
    ~8min/24min confirm-poll would be killed by the Bash tool's 120s-default/
    600s-max timeout in real reviewer usage -> silent half-success). Default
    invocation reports MERGE-PENDING (exit 3, no span) once its bounded
    budget elapses without a confirmed merge; `--confirm <n>` is the
    idempotent re-entry point that finishes the job on a later, separate
    Bash call. IDEMPOTENCE GUARD: a second `--confirm` must never double-
    append a `pr_merged` span for the same PR.
    """

    def setUp(self):
        if not PR_MERGE.exists():
            self.skip_reason = f"tools/pipe/pr-merge not found at {PR_MERGE}"
        else:
            self.skip_reason = None
        self.tmp = tempfile.mkdtemp(prefix="pr_merge_pending_test_")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _run(self, args, env_updates, cwd=None):
        if self.skip_reason:
            self.fail(self.skip_reason)
        env = os.environ.copy()
        env.update(env_updates)
        cmd = [sys.executable, str(PR_MERGE)] + args
        return subprocess.run(cmd, capture_output=True, text=True, cwd=cwd or str(REPO_ROOT), env=env, timeout=30)

    def test_default_invocation_bounded_never_blocks_past_budget(self):
        """Default (no --confirm) call: merge command queues (exit 0) but the
        REST confirm-poll never sees merged:true within the bounded budget ->
        MERGE-PENDING, exit 3, NO span written. Must return near-instantly
        (no real sleep) given PR_MERGE_BUDGET_S=0."""
        fake_gh_dir = _write_fake_gh(self.tmp)
        log_path = os.path.join(self.tmp, "trace-v3.jsonl")
        env_updates = {
            "PATH": fake_gh_dir + os.pathsep + os.environ.get("PATH", ""),
            "TRACE_LOG_OVERRIDE": log_path,
            "FAKE_GH_MERGE_EXIT": "0",
            "FAKE_GH_API_JSON": json.dumps({"merged": False}),
            "PR_MERGE_BUDGET_S": "0",
        }
        start = time.monotonic()
        result = self._run(["901"], env_updates)
        elapsed = time.monotonic() - start
        self.assertLess(elapsed, 10, "default invocation must not block for a long poll (budget=0)")
        self.assertEqual(
            result.returncode, 3,
            f"expected exit 3 (MERGE-PENDING); got {result.returncode}. "
            f"stdout={result.stdout!r} stderr={result.stderr!r}",
        )
        combined = (result.stdout + result.stderr).lower()
        self.assertIn("merge-pending", combined, f"expected loud MERGE-PENDING line; got {combined!r}")
        self.assertIn("--confirm", combined, f"expected --confirm re-invocation hint; got {combined!r}")
        self.assertIn("901", combined, "expected the PR number in the MERGE-PENDING hint")
        lines = _read_jsonl(log_path)
        self.assertEqual(len(lines), 0, f"pending state must write NO span; got {lines}")

    def test_confirm_then_idempotent_reinvoke_full_lifecycle(self):
        """Full lifecycle across 3 separate subprocess invocations sharing one
        log: (1) default call sees pending -> exit 3, no span; (2) --confirm
        with merged:true -> span appended exactly once; (3) --confirm again
        -> 'already recorded', exit 0, STILL exactly one span (idempotence
        guard: never double-append for the same PR)."""
        fake_gh_dir = _write_fake_gh(self.tmp)
        log_path = os.path.join(self.tmp, "trace-v3.jsonl")
        base_env = {
            "PATH": fake_gh_dir + os.pathsep + os.environ.get("PATH", ""),
            "TRACE_LOG_OVERRIDE": log_path,
        }

        # Step 1: default invocation — merge command queues, REST says not
        # merged yet, bounded budget expires -> MERGE-PENDING.
        pending_env = dict(base_env)
        pending_env.update({
            "FAKE_GH_MERGE_EXIT": "0",
            "FAKE_GH_API_JSON": json.dumps({"merged": False}),
            "PR_MERGE_BUDGET_S": "0",
        })
        r1 = self._run(["902"], pending_env)
        self.assertEqual(r1.returncode, 3, f"step1: stdout={r1.stdout!r} stderr={r1.stderr!r}")
        self.assertEqual(len(_read_jsonl(log_path)), 0, "step1: no span yet")

        # Step 2: --confirm, REST now reports merged:true -> span appended once.
        confirm_env = dict(base_env)
        confirm_env.update({
            "FAKE_GH_API_JSON": json.dumps({"merged": True, "merge_commit_sha": "feedface42"}),
            "PR_MERGE_BUDGET_S": "5",
        })
        r2 = self._run(["--confirm", "902"], confirm_env)
        self.assertEqual(r2.returncode, 0, f"step2: stdout={r2.stdout!r} stderr={r2.stderr!r}")
        lines_after_confirm = _read_jsonl(log_path)
        # slice #1130: a confirmed merge now also appends a verdict span
        # alongside pr_merged (ADR-0076 D3 criterion 3b).
        self.assertEqual(len(lines_after_confirm), 2, f"step2: expected pr_merged + verdict spans, got {lines_after_confirm}")
        merged_after_confirm = [l for l in lines_after_confirm if l["kind"] == "pr_merged"]
        self.assertEqual(len(merged_after_confirm), 1, f"step2: expected exactly 1 pr_merged span, got {lines_after_confirm}")
        self.assertEqual(merged_after_confirm[0]["attrs"]["pr"], "902")
        self.assertEqual(merged_after_confirm[0]["attrs"]["sha"], "feedface42")
        verdict_after_confirm = [l for l in lines_after_confirm if l["kind"] == "verdict"]
        self.assertEqual(len(verdict_after_confirm), 1, f"step2: expected exactly 1 verdict span, got {lines_after_confirm}")

        # Step 3: --confirm AGAIN (idempotent re-invoke) -> 'already recorded',
        # exit 0, and critically STILL exactly the same 2 spans (no duplicate).
        r3 = self._run(["--confirm", "902"], confirm_env)
        self.assertEqual(r3.returncode, 0, f"step3: stdout={r3.stdout!r} stderr={r3.stderr!r}")
        self.assertIn(
            "already recorded", (r3.stdout + r3.stderr).lower(),
            f"expected 'already recorded' on idempotent re-invoke; got stdout={r3.stdout!r} stderr={r3.stderr!r}",
        )
        lines_final = _read_jsonl(log_path)
        self.assertEqual(
            len(lines_final), 2,
            f"IDEMPOTENCE GUARD violated: expected still exactly 1 pr_merged + 1 verdict span after re-invoke, got {lines_final}",
        )


class TestPrMergeRestChecksOnNonzeroGhExit(unittest.TestCase):
    """Regression for slice #1100 (root-cause, proven live on PR #1095's
    merge): gh can exit non-zero AFTER a successful server-side merge
    ('Auto merge is not allowed for this repository' / a --delete-branch
    race with a sibling worktree holding the branch — both reported AFTER
    the merge already completed). `_do_default` must REST-check merged
    state before concluding failure on ANY non-zero gh exit — a real merge
    must never be silently lost with no span (rule #13 / ADR-0067 D3).

    FAILS before the fix: `_do_default` only ever calls the REST-confirm
    path when the `gh pr merge` command itself returned 0; on a nonzero
    exit it exhausts its retry budget and returns failure WITHOUT ever
    consulting the REST API — so a PR that is actually merged is reported
    as failed, with no span (the exact silent-half-success the wrapper
    exists to kill).
    PASSES after the fix: on exhausting the retry budget with a nonzero gh
    exit, the wrapper REST-checks once more; if the PR is actually merged
    it appends exactly one span and exits 0; if genuinely unmerged, the
    existing failure contract (nonzero exit, no span, never colliding with
    the reserved MERGE-PENDING exit code 3) is unchanged.
    """

    def setUp(self):
        if not PR_MERGE.exists():
            self.skip_reason = f"tools/pipe/pr-merge not found at {PR_MERGE}"
        else:
            self.skip_reason = None
        self.tmp = tempfile.mkdtemp(prefix="pr_merge_falseneg_test_")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _run(self, args, env_updates, cwd=None):
        if self.skip_reason:
            self.fail(self.skip_reason)
        env = os.environ.copy()
        env.update(env_updates)
        cmd = [sys.executable, str(PR_MERGE)] + args
        return subprocess.run(cmd, capture_output=True, text=True, cwd=cwd or str(REPO_ROOT), env=env, timeout=30)

    def test_nonzero_gh_exit_after_real_merge_still_appends_span(self):
        """gh pr merge exits 1 (simulating the 'Auto merge is not allowed'
        quirk reported AFTER the merge already happened server-side); REST
        reports merged=true throughout. The wrapper must confirm + append
        exactly ONE pr_merged span and exit 0 — never a false-negative."""
        fake_gh_dir = _write_fake_gh(self.tmp)
        log_path = os.path.join(self.tmp, "trace-v3.jsonl")
        env_updates = {
            "PATH": fake_gh_dir + os.pathsep + os.environ.get("PATH", ""),
            "TRACE_LOG_OVERRIDE": log_path,
            "FAKE_GH_MERGE_EXIT": "1",
            "FAKE_GH_MERGE_STDERR": "GraphQL: Auto merge is not allowed for this repository",
            "FAKE_GH_UPDATE_BRANCH_EXIT": "0",
            "FAKE_GH_CHECKS_EXIT": "0",
            "FAKE_GH_API_JSON": json.dumps({"merged": True, "merge_commit_sha": "abc999real"}),
            "PR_MERGE_BUDGET_S": "0",
        }
        result = self._run(["1095"], env_updates)
        self.assertEqual(result.returncode, 0, f"stdout={result.stdout!r} stderr={result.stderr!r}")
        lines = _read_jsonl(log_path)
        # slice #1130: a confirmed merge now also appends a verdict span
        # alongside pr_merged (ADR-0076 D3 criterion 3b).
        merged_spans = [l for l in lines if l["kind"] == "pr_merged"]
        self.assertEqual(len(merged_spans), 1, f"expected exactly 1 pr_merged span, got {lines}")
        span = merged_spans[0]
        self.assertEqual(span["kind"], "pr_merged")
        self.assertEqual(span["attrs"]["pr"], "1095")
        self.assertEqual(span["attrs"]["sha"], "abc999real")
        verdict_spans = [l for l in lines if l["kind"] == "verdict"]
        self.assertEqual(len(verdict_spans), 1, f"expected exactly 1 verdict span, got {lines}")

    def test_genuinely_unmerged_nonzero_exit_still_fails_no_span(self):
        """Contrast case: gh exits nonzero AND the REST API confirms the PR
        is genuinely NOT merged — existing failure contract unchanged
        (nonzero exit, no span, never exit 3 — that code is reserved
        exclusively for the MERGE-PENDING re-invoke contract)."""
        fake_gh_dir = _write_fake_gh(self.tmp)
        log_path = os.path.join(self.tmp, "trace-v3.jsonl")
        env_updates = {
            "PATH": fake_gh_dir + os.pathsep + os.environ.get("PATH", ""),
            "TRACE_LOG_OVERRIDE": log_path,
            "FAKE_GH_MERGE_EXIT": "1",
            "FAKE_GH_MERGE_STDERR": "some other real gh failure",
            "FAKE_GH_UPDATE_BRANCH_EXIT": "0",
            "FAKE_GH_CHECKS_EXIT": "0",
            "FAKE_GH_API_JSON": json.dumps({"merged": False}),
            "PR_MERGE_BUDGET_S": "0",
        }
        result = self._run(["1096"], env_updates)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotEqual(
            result.returncode, 3,
            "genuine non-merge must not collide with the reserved MERGE-PENDING exit-3 contract",
        )
        lines = _read_jsonl(log_path)
        self.assertEqual(len(lines), 0, f"genuinely-unmerged PR must write NO span; got {lines}")


# ---------------------------------------------------------------------------
# (d) acid query — ordered causal path / explicit failure for unknown PR
# ---------------------------------------------------------------------------

class TestAcidQuery(unittest.TestCase):
    def setUp(self):
        if not TRACE_PY.exists():
            self.skip_reason = f"tools/trace.py not found at {TRACE_PY}"
        else:
            self.skip_reason = None
        self.tmp = tempfile.mkdtemp(prefix="acid_query_test_")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write_fixture(self, log_path):
        spans = [
            {"v": 3, "ts": "2026-08-01T09:55:00Z", "trace_id": "pr-42", "span_id": "s0",
             "kind": "dispatch", "attrs": {"actor": "implementer"}},
            {"v": 3, "ts": "2026-08-01T10:00:00Z", "trace_id": "pr-42", "span_id": "s1",
             "kind": "pr_opened", "attrs": {"pr": "42", "branch": "feat/x"}},
            {"v": 3, "ts": "2026-08-01T10:05:00Z", "trace_id": "pr-42", "span_id": "s2",
             "parent_span_id": "s1", "kind": "pr_merged",
             "attrs": {"pr": "42", "sha": "abc123"}, "dur_ms": 300000},
            {"v": 3, "ts": "2026-08-01T11:00:00Z", "trace_id": "pr-99", "span_id": "s9",
             "kind": "pr_opened", "attrs": {"pr": "99"}},
        ]
        with open(log_path, "w", encoding="utf-8") as f:
            for s in spans:
                f.write(json.dumps(s) + "\n")

    def _run(self, args, env_updates):
        if self.skip_reason:
            self.fail(self.skip_reason)
        env = os.environ.copy()
        env.update(env_updates)
        cmd = [sys.executable, str(TRACE_PY)] + args
        return subprocess.run(cmd, capture_output=True, text=True, cwd=str(REPO_ROOT), env=env, timeout=30)

    def test_known_pr_returns_ordered_causal_chain(self):
        log_path = os.path.join(self.tmp, "trace-v3.jsonl")
        self._write_fixture(log_path)
        result = self._run(["path", "--pr", "42"], {"TRACE_LOG_OVERRIDE": log_path})
        self.assertEqual(result.returncode, 0, f"stdout={result.stdout!r} stderr={result.stderr!r}")
        out = result.stdout
        pos_s0 = out.find("s0")
        pos_s1 = out.find("s1")
        pos_s2 = out.find("s2")
        self.assertNotEqual(pos_s0, -1, "expected dispatch span s0 (same trace_id) in output")
        self.assertNotEqual(pos_s1, -1, "expected pr_opened span s1 in output")
        self.assertNotEqual(pos_s2, -1, "expected pr_merged span s2 in output")
        self.assertLess(pos_s0, pos_s1, "spans must be timestamp-ordered (s0 before s1)")
        self.assertLess(pos_s1, pos_s2, "spans must be timestamp-ordered (s1 before s2)")
        self.assertNotIn("s9", out, "PR #99's span must not appear in PR #42's causal path")

    def test_unknown_pr_exits_nonzero_with_explicit_error(self):
        log_path = os.path.join(self.tmp, "trace-v3.jsonl")
        self._write_fixture(log_path)
        result = self._run(["path", "--pr", "999"], {"TRACE_LOG_OVERRIDE": log_path})
        self.assertNotEqual(result.returncode, 0, "unknown PR must exit non-zero")
        self.assertIn(
            "no recorded trace for pr #999",
            (result.stdout + result.stderr).lower(),
            f"expected explicit 'no recorded trace' error; got stdout={result.stdout!r} stderr={result.stderr!r}",
        )


if __name__ == "__main__":
    unittest.main()
