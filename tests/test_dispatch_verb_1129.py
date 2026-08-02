"""
tests/test_dispatch_verb_1129.py

Regression / new-feature tests for slice #1129 (PRD #1127 walking skeleton) —
the `tools/pipe/dispatch` precondition-checked verb, its `dispatch_end`
counterpart, and the tracestore "running now" query.

Test-first discipline (rule #13 rider / ADR-0067 D3 shape, applied here to a
new-feature slice, mirroring the precedent set by tests/test_trace_skeleton_
1078.py for the sibling PRD #1075 walking skeleton): this commit lands BEFORE
`tools/pipe/dispatch` exists.

FAILS before impl: every TestDispatch* test errors (FileNotFoundError) because
tools/pipe/dispatch does not exist yet.
PASSES after impl: tools/pipe/dispatch lands in the next commit and satisfies
every assertion here; dashboard/tracestore.py's `running` query is covered by
TestRunningNowQuery (uses the tracestore module directly — no subprocess).

Covers PRD #1127 §2 criteria 1a/1b/1c/1d/1e/2a/2b:
  (a) 1a: closed or nonexistent slice -> refuse, non-zero, no span
  (b) 1b: missing Slicer-provenance trailer AND no root-cause label -> refuse
  (c) 1c: assigned to a different identity (non-empty assignees, self absent)
      -> refuse; empty assignees OR self-assigned -> passes this precondition
  (d) 1d: an active (unterminated) dispatch span already exists for the slice
      -> refuse (duplicate-dispatch mutex)
  (e) 1e: all preconditions hold -> dispatch span emitted (slice/prd/
      session_id attrs), exit 0
  (f) 2a: `dispatch --end <slice> --result <r>` emits the matching
      dispatch_end span
  (g) 2b: tracestore "running now" query returns exactly the dispatch spans
      lacking a terminal dispatch_end, verified before/after a termination

Runner: stdlib unittest + pytest compatible.
  python -m pytest tests/test_dispatch_verb_1129.py -v
"""

import importlib.util
import json
import os
import platform
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
TOOLS_DIR = REPO_ROOT / "tools"
TRACE_PY = TOOLS_DIR / "trace.py"
DISPATCH = TOOLS_DIR / "pipe" / "dispatch"
TRACESTORE_PY = REPO_ROOT / "dashboard" / "tracestore.py"


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _load_trace_module():
    spec = importlib.util.spec_from_file_location("trace_v3_dispatch_test", TRACE_PY)
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

if sub0 == "api":
    path = args[1] if len(args) > 1 else ""
    if path == "user":
        print(os.environ.get("FAKE_GH_USER_JSON", '{"login": "bot"}'))
        sys.exit(int(os.environ.get("FAKE_GH_USER_EXIT", "0")))
    elif "/issues/" in path:
        print(os.environ.get("FAKE_GH_ISSUE_JSON", "{}"))
        sys.exit(int(os.environ.get("FAKE_GH_ISSUE_EXIT", "0")))
    else:
        print("{}")
        sys.exit(0)
else:
    sys.exit(0)
"""


def _write_fake_gh(dirpath):
    """Write a fake `gh` binary into dirpath; prepend dirpath to PATH to
    shadow the real `gh`. Behavior selected via env vars (FAKE_GH_*)."""
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


_OPEN_PROVENANCE_ISSUE = json.dumps({
    "number": 1129,
    "state": "open",
    "body": "## Parent\n\nPRD #1127\n\nSlicer-provenance: slicer-critic-APPROVED\n",
    "labels": [{"name": "slice"}],
    "assignees": [],
})


class DispatchTestBase(unittest.TestCase):
    def setUp(self):
        if not DISPATCH.exists():
            self.skip_reason = f"tools/pipe/dispatch not found at {DISPATCH}"
        else:
            self.skip_reason = None
        self.tmp = tempfile.mkdtemp(prefix="dispatch_test_")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _run(self, args, env_updates, cwd=None):
        if self.skip_reason:
            self.fail(self.skip_reason)  # must FAIL (not skip) pre-impl
        env = os.environ.copy()
        env.update(env_updates)
        cmd = [sys.executable, str(DISPATCH)] + args
        return subprocess.run(cmd, capture_output=True, text=True, cwd=cwd or str(REPO_ROOT), env=env, timeout=30)


# ---------------------------------------------------------------------------
# (a) 1a: closed / nonexistent slice
# ---------------------------------------------------------------------------

class TestRefusalClosedOrNonexistent(DispatchTestBase):
    def test_closed_slice_refused_no_span(self):
        fake_gh_dir = _write_fake_gh(self.tmp)
        log_path = os.path.join(self.tmp, "trace-v3.jsonl")
        closed_issue = json.dumps({
            "number": 1129, "state": "closed",
            "body": "Slicer-provenance: x\n", "labels": [{"name": "slice"}],
            "assignees": [],
        })
        env_updates = {
            "PATH": fake_gh_dir + os.pathsep + os.environ.get("PATH", ""),
            "TRACE_LOG_OVERRIDE": log_path,
            "FAKE_GH_ISSUE_JSON": closed_issue,
        }
        result = self._run(["1129"], env_updates)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(_read_jsonl(log_path), [])

    def test_nonexistent_slice_refused_no_span(self):
        fake_gh_dir = _write_fake_gh(self.tmp)
        log_path = os.path.join(self.tmp, "trace-v3.jsonl")
        env_updates = {
            "PATH": fake_gh_dir + os.pathsep + os.environ.get("PATH", ""),
            "TRACE_LOG_OVERRIDE": log_path,
            "FAKE_GH_ISSUE_EXIT": "1",
        }
        result = self._run(["99999"], env_updates)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(_read_jsonl(log_path), [])


# ---------------------------------------------------------------------------
# (b) 1b: missing provenance trailer + no root-cause label
# ---------------------------------------------------------------------------

class TestRefusalMissingProvenance(DispatchTestBase):
    def test_no_trailer_no_root_cause_label_refused(self):
        fake_gh_dir = _write_fake_gh(self.tmp)
        log_path = os.path.join(self.tmp, "trace-v3.jsonl")
        issue = json.dumps({
            "number": 1129, "state": "open",
            "body": "no provenance trailer here\n",
            "labels": [{"name": "slice"}],
            "assignees": [],
        })
        env_updates = {
            "PATH": fake_gh_dir + os.pathsep + os.environ.get("PATH", ""),
            "TRACE_LOG_OVERRIDE": log_path,
            "FAKE_GH_ISSUE_JSON": issue,
        }
        result = self._run(["1129"], env_updates)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(_read_jsonl(log_path), [])

    def test_root_cause_label_without_trailer_passes_provenance(self):
        """root-cause label is the alternate provenance signal (no Slicer-
        provenance trailer required for the root-cause lane)."""
        fake_gh_dir = _write_fake_gh(self.tmp)
        log_path = os.path.join(self.tmp, "trace-v3.jsonl")
        issue = json.dumps({
            "number": 1129, "state": "open",
            "body": "no trailer, but root-cause labeled\n",
            "labels": [{"name": "slice"}, {"name": "root-cause"}],
            "assignees": [],
        })
        env_updates = {
            "PATH": fake_gh_dir + os.pathsep + os.environ.get("PATH", ""),
            "TRACE_LOG_OVERRIDE": log_path,
            "FAKE_GH_ISSUE_JSON": issue,
        }
        result = self._run(["1129"], env_updates)
        self.assertEqual(result.returncode, 0, f"stdout={result.stdout!r} stderr={result.stderr!r}")
        lines = _read_jsonl(log_path)
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0]["kind"], "dispatch")


# ---------------------------------------------------------------------------
# (c) 1c: wrong assignee
# ---------------------------------------------------------------------------

class TestRefusalWrongAssignee(DispatchTestBase):
    def test_assigned_to_someone_else_refused(self):
        fake_gh_dir = _write_fake_gh(self.tmp)
        log_path = os.path.join(self.tmp, "trace-v3.jsonl")
        issue = json.dumps({
            "number": 1129, "state": "open",
            "body": "Slicer-provenance: x\n",
            "labels": [{"name": "slice"}],
            "assignees": [{"login": "someone-else"}],
        })
        env_updates = {
            "PATH": fake_gh_dir + os.pathsep + os.environ.get("PATH", ""),
            "TRACE_LOG_OVERRIDE": log_path,
            "FAKE_GH_ISSUE_JSON": issue,
            "FAKE_GH_USER_JSON": json.dumps({"login": "bot"}),
        }
        result = self._run(["1129"], env_updates)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(_read_jsonl(log_path), [])

    def test_empty_assignees_passes(self):
        fake_gh_dir = _write_fake_gh(self.tmp)
        log_path = os.path.join(self.tmp, "trace-v3.jsonl")
        env_updates = {
            "PATH": fake_gh_dir + os.pathsep + os.environ.get("PATH", ""),
            "TRACE_LOG_OVERRIDE": log_path,
            "FAKE_GH_ISSUE_JSON": _OPEN_PROVENANCE_ISSUE,
        }
        result = self._run(["1129"], env_updates)
        self.assertEqual(result.returncode, 0, f"stdout={result.stdout!r} stderr={result.stderr!r}")

    def test_self_assigned_passes(self):
        fake_gh_dir = _write_fake_gh(self.tmp)
        log_path = os.path.join(self.tmp, "trace-v3.jsonl")
        issue = json.dumps({
            "number": 1129, "state": "open",
            "body": "Slicer-provenance: x\n",
            "labels": [{"name": "slice"}],
            "assignees": [{"login": "bot"}],
        })
        env_updates = {
            "PATH": fake_gh_dir + os.pathsep + os.environ.get("PATH", ""),
            "TRACE_LOG_OVERRIDE": log_path,
            "FAKE_GH_ISSUE_JSON": issue,
            "FAKE_GH_USER_JSON": json.dumps({"login": "bot"}),
        }
        result = self._run(["1129"], env_updates)
        self.assertEqual(result.returncode, 0, f"stdout={result.stdout!r} stderr={result.stderr!r}")


# ---------------------------------------------------------------------------
# (d) 1d: duplicate-dispatch mutex
# ---------------------------------------------------------------------------

class TestRefusalActiveDispatchMutex(DispatchTestBase):
    def test_active_unterminated_dispatch_refused(self):
        fake_gh_dir = _write_fake_gh(self.tmp)
        log_path = os.path.join(self.tmp, "trace-v3.jsonl")
        # Seed an existing, unterminated dispatch span for slice 1129.
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(json.dumps({
                "v": 3, "ts": "2026-08-02T09:00:00Z", "trace_id": "slice-1129",
                "span_id": "seed1", "kind": "dispatch",
                "attrs": {"slice": "1129", "session_id": "other-session"},
            }) + "\n")
        env_updates = {
            "PATH": fake_gh_dir + os.pathsep + os.environ.get("PATH", ""),
            "TRACE_LOG_OVERRIDE": log_path,
            "FAKE_GH_ISSUE_JSON": _OPEN_PROVENANCE_ISSUE,
        }
        result = self._run(["1129"], env_updates)
        self.assertNotEqual(result.returncode, 0)
        lines = _read_jsonl(log_path)
        self.assertEqual(len(lines), 1, "no NEW span may be appended on mutex refusal")

    def test_terminated_dispatch_does_not_block_new_dispatch(self):
        fake_gh_dir = _write_fake_gh(self.tmp)
        log_path = os.path.join(self.tmp, "trace-v3.jsonl")
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(json.dumps({
                "v": 3, "ts": "2026-08-02T09:00:00Z", "trace_id": "slice-1129",
                "span_id": "seed1", "kind": "dispatch",
                "attrs": {"slice": "1129", "session_id": "other-session"},
            }) + "\n")
            f.write(json.dumps({
                "v": 3, "ts": "2026-08-02T09:05:00Z", "trace_id": "slice-1129",
                "span_id": "seed2", "kind": "dispatch_end",
                "attrs": {"slice": "1129", "result": "SUCCESS"},
            }) + "\n")
        env_updates = {
            "PATH": fake_gh_dir + os.pathsep + os.environ.get("PATH", ""),
            "TRACE_LOG_OVERRIDE": log_path,
            "FAKE_GH_ISSUE_JSON": _OPEN_PROVENANCE_ISSUE,
        }
        result = self._run(["1129"], env_updates)
        self.assertEqual(result.returncode, 0, f"stdout={result.stdout!r} stderr={result.stderr!r}")
        lines = _read_jsonl(log_path)
        self.assertEqual(len(lines), 3)


# ---------------------------------------------------------------------------
# (e) 1e: success emits dispatch span with slice/prd/session_id attrs
# ---------------------------------------------------------------------------

class TestSuccessEmitsDispatchSpan(DispatchTestBase):
    def test_success_span_has_slice_prd_session_id(self):
        fake_gh_dir = _write_fake_gh(self.tmp)
        log_path = os.path.join(self.tmp, "trace-v3.jsonl")
        issue = json.dumps({
            "number": 1129, "state": "open",
            "body": "## Parent\n\nPRD #1127 -- guarded-verb pipeline engine\n\nSlicer-provenance: x\n",
            "labels": [{"name": "slice"}],
            "assignees": [],
        })
        env_updates = {
            "PATH": fake_gh_dir + os.pathsep + os.environ.get("PATH", ""),
            "TRACE_LOG_OVERRIDE": log_path,
            "FAKE_GH_ISSUE_JSON": issue,
            "CLAUDE_SESSION_ID": "test-session-42",
        }
        result = self._run(["1129"], env_updates)
        self.assertEqual(result.returncode, 0, f"stdout={result.stdout!r} stderr={result.stderr!r}")
        lines = _read_jsonl(log_path)
        self.assertEqual(len(lines), 1)
        span = lines[0]
        self.assertEqual(span["kind"], "dispatch")
        self.assertEqual(span["attrs"]["slice"], "1129")
        self.assertEqual(span["attrs"]["prd"], "1127")
        self.assertEqual(span["attrs"]["session_id"], "test-session-42")


# ---------------------------------------------------------------------------
# (f) 2a: --end emits dispatch_end
# ---------------------------------------------------------------------------

class TestDispatchEnd(DispatchTestBase):
    def test_end_emits_dispatch_end_span(self):
        log_path = os.path.join(self.tmp, "trace-v3.jsonl")
        env_updates = {"TRACE_LOG_OVERRIDE": log_path}
        result = self._run(["--end", "1129", "--result", "SUCCESS"], env_updates)
        self.assertEqual(result.returncode, 0, f"stdout={result.stdout!r} stderr={result.stderr!r}")
        lines = _read_jsonl(log_path)
        self.assertEqual(len(lines), 1)
        span = lines[0]
        self.assertEqual(span["kind"], "dispatch_end")
        self.assertEqual(span["attrs"]["slice"], "1129")
        self.assertEqual(span["attrs"]["result"], "SUCCESS")


# ---------------------------------------------------------------------------
# (g) 2b: tracestore "running now" query
# ---------------------------------------------------------------------------

class TestRunningNowQuery(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="running_now_test_")
        self.log_path = os.path.join(self.tmp, "trace-v3.jsonl")
        self.db_path = os.path.join(self.tmp, "trace.db")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _load_tracestore_module(self):
        spec = importlib.util.spec_from_file_location("tracestore_dispatch_test", TRACESTORE_PY)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def _write(self, spans):
        with open(self.log_path, "w", encoding="utf-8") as f:
            for s in spans:
                f.write(json.dumps(s) + "\n")

    def test_returns_exactly_unterminated_dispatch_spans_before_after_termination(self):
        ts_mod = self._load_tracestore_module()
        self._write([
            {"v": 3, "ts": "2026-08-02T09:00:00Z", "trace_id": "slice-1130",
             "span_id": "d1", "kind": "dispatch",
             "attrs": {"slice": "1130", "prd": "1127", "session_id": "s1"}},
            {"v": 3, "ts": "2026-08-02T09:01:00Z", "trace_id": "slice-1131",
             "span_id": "d2", "kind": "dispatch",
             "attrs": {"slice": "1131", "prd": "1127", "session_id": "s1"}},
            {"v": 3, "ts": "2026-08-02T09:02:00Z", "trace_id": "slice-1131",
             "span_id": "d2end", "kind": "dispatch_end",
             "attrs": {"slice": "1131", "result": "SUCCESS"}},
        ])

        running_before = ts_mod.running_dispatches(log_path=self.log_path, db_path_=self.db_path)
        running_slices = {r["attrs"]["slice"] for r in running_before}
        self.assertEqual(running_slices, {"1130"}, f"expected only slice 1130 still running, got {running_before}")

        # Terminate slice 1130's dispatch.
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "v": 3, "ts": "2026-08-02T09:03:00Z", "trace_id": "slice-1130",
                "span_id": "d1end", "kind": "dispatch_end",
                "attrs": {"slice": "1130", "result": "SUCCESS"},
            }) + "\n")

        running_after = ts_mod.running_dispatches(log_path=self.log_path, db_path_=self.db_path)
        self.assertEqual(running_after, [], f"expected zero running dispatches after termination, got {running_after}")

    def test_cli_running_subcommand_present(self):
        result = subprocess.run(
            [sys.executable, str(TRACESTORE_PY), "running", "--help"],
            capture_output=True, text=True, cwd=str(REPO_ROOT), timeout=30,
        )
        self.assertEqual(result.returncode, 0, f"stdout={result.stdout!r} stderr={result.stderr!r}")


if __name__ == "__main__":
    unittest.main()
