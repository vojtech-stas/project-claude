"""
tests/test_pr_merge_verdict_1130.py

New-feature tests for slice #1130 (PRD #1127 / ADR-0076 D3): tools/pipe/
pr-merge's reviewer-VERDICT-assertion precondition + the `verdict` v3 span
emitted alongside `pr_merged` on a confirmed merge.

Covers PRD #1127 §2 criteria 3a/3b:
  (a) 3a: a PR carrying no reviewer comment matching `VERDICT:\\s*APPROVE`
      (the exact signal `.claude/hooks/stop-reviewer-gate.sh` greps) is
      refused -- non-zero exit, named reason, NO merge attempt (`gh pr
      merge` never invoked), NO span written.
  (b) 3a: an unfetchable comment list (gh failure) is treated as refusal,
      not silent pass-through.
  (c) 3b: a confirmed merge with a matching APPROVE comment appends a
      `verdict` span (attrs: critic, round, verdict, pr) derived from that
      comment, IN ADDITION to the existing `pr_merged` span.
  (d) the most-recent matching APPROVE comment (e.g. a round-2 APPROVE after
      an earlier round-1 BLOCK) is the one the verdict span is derived from.
  (e) `--confirm` mode enforces the same precondition when no `pr_merged`
      span is yet recorded for the PR.
  (f) the existing idempotence guard (`--confirm` on an ALREADY-recorded PR)
      makes ZERO gh calls -- the verdict-assertion precondition must not be
      re-run once a merge is already recorded (preserves the pre-existing
      "already recorded" no-gh-calls contract).

Fixture discipline (rule #21): every write in these tests targets a temp
path via TRACE_LOG_OVERRIDE -- never a real `.claude/logs/*` store.

Runner: stdlib unittest + pytest compatible.
    python -m pytest tests/test_pr_merge_verdict_1130.py -v
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
PR_MERGE = REPO_ROOT / "tools" / "pipe" / "pr-merge"


# ---------------------------------------------------------------------------
# Shared fake-gh fixture (mirrors tests/test_trace_skeleton_1078.py's pattern)
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


def _read_marker(path):
    p = Path(path)
    if not p.exists():
        return []
    return [l.strip() for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


class PrMergeVerdictTestBase(unittest.TestCase):
    def setUp(self):
        if not PR_MERGE.exists():
            self.skip_reason = f"tools/pipe/pr-merge not found at {PR_MERGE}"
        else:
            self.skip_reason = None
        self.tmp = tempfile.mkdtemp(prefix="pr_merge_verdict_1130_")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _run(self, args, env_updates):
        if self.skip_reason:
            self.fail(self.skip_reason)
        env = os.environ.copy()
        env.update(env_updates)
        cmd = [sys.executable, str(PR_MERGE)] + args
        return subprocess.run(cmd, capture_output=True, text=True, cwd=str(REPO_ROOT), env=env, timeout=30)


# ---------------------------------------------------------------------------
# (a) refusal: no matching APPROVE comment -- no merge attempt, no span
# ---------------------------------------------------------------------------

class TestRefusalNoApproveComment(PrMergeVerdictTestBase):
    def test_no_comments_refused_gh_merge_never_invoked(self):
        fake_gh_dir = _write_fake_gh(self.tmp)
        log_path = os.path.join(self.tmp, "trace-v3.jsonl")
        marker = os.path.join(self.tmp, "gh_calls.marker")
        env_updates = {
            "PATH": fake_gh_dir + os.pathsep + os.environ.get("PATH", ""),
            "TRACE_LOG_OVERRIDE": log_path,
            "FAKE_GH_VIEW_JSON": json.dumps({"comments": []}),
            "FAKE_GH_MARKER_FILE": marker,
        }
        result = self._run(["555"], env_updates)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("VERDICT: APPROVE", result.stderr, f"expected named reason; got stderr={result.stderr!r}")
        self.assertEqual(_read_jsonl(log_path), [], "refusal must write no span")

        calls = _read_marker(marker)
        merge_calls = [c for c in calls if c.startswith("pr merge")]
        self.assertEqual(merge_calls, [], f"gh pr merge must NEVER be invoked on refusal; calls={calls}")

    def test_non_matching_comment_refused(self):
        """A comment that mentions VERDICT but not APPROVE (e.g. a BLOCK) must
        not satisfy the precondition."""
        fake_gh_dir = _write_fake_gh(self.tmp)
        log_path = os.path.join(self.tmp, "trace-v3.jsonl")
        env_updates = {
            "PATH": fake_gh_dir + os.pathsep + os.environ.get("PATH", ""),
            "TRACE_LOG_OVERRIDE": log_path,
            "FAKE_GH_VIEW_JSON": json.dumps({"comments": [{"body": "VERDICT: BLOCK\nREASON: nope\nROUND: 1"}]}),
        }
        result = self._run(["556"], env_updates)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(_read_jsonl(log_path), [])

    def test_gh_failure_fetching_comments_treated_as_refusal(self):
        """An unfetchable comment list (gh error) must refuse -- never a
        silent pass-through to the merge attempt."""
        fake_gh_dir = _write_fake_gh(self.tmp)
        log_path = os.path.join(self.tmp, "trace-v3.jsonl")
        marker = os.path.join(self.tmp, "gh_calls.marker")
        env_updates = {
            "PATH": fake_gh_dir + os.pathsep + os.environ.get("PATH", ""),
            "TRACE_LOG_OVERRIDE": log_path,
            "FAKE_GH_VIEW_EXIT": "1",
            "FAKE_GH_MARKER_FILE": marker,
        }
        result = self._run(["557"], env_updates)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(_read_jsonl(log_path), [])
        calls = _read_marker(marker)
        merge_calls = [c for c in calls if c.startswith("pr merge")]
        self.assertEqual(merge_calls, [], f"gh pr merge must NEVER be invoked on refusal; calls={calls}")


# ---------------------------------------------------------------------------
# (c)/(d) success: verdict span derived from the matched APPROVE comment
# ---------------------------------------------------------------------------

class TestVerdictSpanOnConfirmedMerge(PrMergeVerdictTestBase):
    def test_verdict_span_appended_alongside_pr_merged(self):
        fake_gh_dir = _write_fake_gh(self.tmp)
        log_path = os.path.join(self.tmp, "trace-v3.jsonl")
        env_updates = {
            "PATH": fake_gh_dir + os.pathsep + os.environ.get("PATH", ""),
            "TRACE_LOG_OVERRIDE": log_path,
            "FAKE_GH_VIEW_JSON": json.dumps({"comments": [
                {"body": "VERDICT: APPROVE\nREASON: looks good\nROUND: 2\nCRITIC: reviewer"},
            ]}),
            "FAKE_GH_MERGE_EXIT": "0",
            "FAKE_GH_API_JSON": json.dumps({"merged": True, "merge_commit_sha": "cafef00d"}),
            "PR_MERGE_BUDGET_S": "5",
        }
        result = self._run(["600"], env_updates)
        self.assertEqual(result.returncode, 0, f"stdout={result.stdout!r} stderr={result.stderr!r}")

        lines = _read_jsonl(log_path)
        self.assertEqual(len(lines), 2, f"expected pr_merged + verdict spans, got {lines}")

        merged = [l for l in lines if l["kind"] == "pr_merged"][0]
        self.assertEqual(merged["attrs"]["pr"], "600")
        self.assertEqual(merged["attrs"]["sha"], "cafef00d")

        verdict = [l for l in lines if l["kind"] == "verdict"][0]
        self.assertEqual(verdict["attrs"]["pr"], "600")
        self.assertEqual(verdict["attrs"]["verdict"], "APPROVE")
        self.assertEqual(verdict["attrs"]["round"], "2")
        self.assertEqual(verdict["attrs"]["critic"], "reviewer")

    def test_most_recent_approve_comment_wins(self):
        """A round-1 BLOCK followed by a round-2 APPROVE: the verdict span
        must derive from the round-2 APPROVE (most recent match), not any
        stray earlier comment."""
        fake_gh_dir = _write_fake_gh(self.tmp)
        log_path = os.path.join(self.tmp, "trace-v3.jsonl")
        env_updates = {
            "PATH": fake_gh_dir + os.pathsep + os.environ.get("PATH", ""),
            "TRACE_LOG_OVERRIDE": log_path,
            "FAKE_GH_VIEW_JSON": json.dumps({"comments": [
                {"body": "VERDICT: BLOCK\nREASON: fix x\nROUND: 1\nCRITIC: reviewer"},
                {"body": "VERDICT: APPROVE\nREASON: fixed\nROUND: 2\nCRITIC: reviewer"},
            ]}),
            "FAKE_GH_MERGE_EXIT": "0",
            "FAKE_GH_API_JSON": json.dumps({"merged": True, "merge_commit_sha": "abc123"}),
            "PR_MERGE_BUDGET_S": "5",
        }
        result = self._run(["601"], env_updates)
        self.assertEqual(result.returncode, 0, f"stdout={result.stdout!r} stderr={result.stderr!r}")
        lines = _read_jsonl(log_path)
        verdict = [l for l in lines if l["kind"] == "verdict"][0]
        self.assertEqual(verdict["attrs"]["round"], "2")


# ---------------------------------------------------------------------------
# (e)/(f) --confirm mode: same precondition unless already recorded
# ---------------------------------------------------------------------------

class TestConfirmModeVerdictAssertion(PrMergeVerdictTestBase):
    def test_confirm_mode_refuses_without_approve_comment(self):
        fake_gh_dir = _write_fake_gh(self.tmp)
        log_path = os.path.join(self.tmp, "trace-v3.jsonl")
        env_updates = {
            "PATH": fake_gh_dir + os.pathsep + os.environ.get("PATH", ""),
            "TRACE_LOG_OVERRIDE": log_path,
            "FAKE_GH_VIEW_JSON": json.dumps({"comments": []}),
            "FAKE_GH_API_JSON": json.dumps({"merged": True, "merge_commit_sha": "zzz"}),
            "PR_MERGE_BUDGET_S": "5",
        }
        result = self._run(["--confirm", "602"], env_updates)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(_read_jsonl(log_path), [], "confirm-mode refusal must write no span")

    def test_confirm_mode_already_recorded_makes_zero_gh_calls(self):
        """Pre-existing idempotence contract (unchanged): when a pr_merged
        span already exists, --confirm exits 0 WITHOUT any gh calls at all --
        the verdict-assertion precondition must not re-run in this path."""
        fake_gh_dir = _write_fake_gh(self.tmp)
        log_path = os.path.join(self.tmp, "trace-v3.jsonl")
        marker = os.path.join(self.tmp, "gh_calls.marker")
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(json.dumps({
                "v": 3, "ts": "2026-08-02T09:00:00Z", "trace_id": "pr-603",
                "span_id": "seed1", "kind": "pr_merged",
                "attrs": {"pr": "603", "sha": "already"},
            }) + "\n")
        env_updates = {
            "PATH": fake_gh_dir + os.pathsep + os.environ.get("PATH", ""),
            "TRACE_LOG_OVERRIDE": log_path,
            "FAKE_GH_MARKER_FILE": marker,
        }
        result = self._run(["--confirm", "603"], env_updates)
        self.assertEqual(result.returncode, 0, f"stdout={result.stdout!r} stderr={result.stderr!r}")
        self.assertIn("already recorded", (result.stdout + result.stderr).lower())
        calls = _read_marker(marker)
        self.assertEqual(calls, [], f"already-recorded path must make ZERO gh calls; calls={calls}")
        # No new span appended (still exactly the seeded pr_merged span).
        lines = _read_jsonl(log_path)
        self.assertEqual(len(lines), 1)


if __name__ == "__main__":
    unittest.main()
