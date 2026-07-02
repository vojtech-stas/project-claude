"""
tests/test_test_ordering_squash_1060.py — slice #1060 regression tests.

Root cause (#1060): the pipeline squash-merges every PR (ADR-0042 D3),
collapsing a PR's test+fix commits into ONE develop commit. The
TEST-ORDERING evaluator (dashboard/health.py::check_test_ordering) walked
develop history directly, saw one commit touching both tests/ and
non-tests/ files, and — worse — picked up UNRELATED sibling PRs' commits
from the `origin/main...{merge_commit}` range as false "fix precedes test"
signals. This produced a structural false-negative for every squash-merged
fix/* PR (observed live: PR #1045's squash commit touches both tests/ and
non-tests/, but two prior sibling commits from OTHER PRs land earlier in
the range and get misread as a preceding fix; PRs 1045/1047/1049/1051/
1055/1058 all flagged disordered despite reviewer-verified test-first
branches).

Fix: for a squash-merged PR (merge commit has exactly one parent AND gh's
PR commit list has >1 commit), fetch the PR's ORIGINAL branch commit oids
via `gh pr view N --json commits` (routed through the health gh_cache
seam, `_health_gh_fetch`) and evaluate test-before-fix ordering on THAT
commit sequence using the same file-touch classification logic already
used for the direct-history path. When gh is unavailable, or one of the
PR's original commit objects is no longer reachable locally, the PR is
counted 'unverifiable' — never silently ordered, never falsely disordered.

Both the gh JSON layer AND the underlying `git` subprocess calls
(`git show -s --format=%P`, `git cat-file -t`, `git diff-tree`) are
stubbed so this test is fully hermetic — it does not depend on the shape
of this repo's own ambient commit history, which would otherwise be a
latent source of flakiness as the branch evolves.

All three cases below fail before the fix (current code has no gh-aware
squash path at all — it always uses the direct-history walk, which is
what produces the false-negative) and pass after.

stdlib unittest only — no top-level pytest dependency (per ADR-0067 D1).
"""

import importlib
import json
import os
import sys
import unittest
from unittest.mock import patch


_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_TESTS_DIR)
_DASHBOARD_DIR = os.path.join(_REPO_ROOT, "dashboard")
if _DASHBOARD_DIR not in sys.path:
    sys.path.insert(0, _DASHBOARD_DIR)


def _reimport(module_name: str):
    if module_name in sys.modules:
        del sys.modules[module_name]
    return importlib.import_module(module_name)


class _GhResult:
    """Minimal stand-in for gh_cache.GhResult (a NamedTuple)."""

    def __init__(self, value, fetched_at="2026-01-01T00:00:00+00:00", source="live"):
        self.value = value
        self.fetched_at = fetched_at
        self.source = source


class _FakeCompletedProcess:
    def __init__(self, stdout="", returncode=0):
        self.stdout = stdout
        self.returncode = returncode


# Fixture shas — fully synthetic, never resolved against a real object db
# (the fake `git` subprocess responder below answers for all of them).
MERGE_SHA = "1111111111111111111111111111111111111111"
TEST_COMMIT_SHA = "2222222222222222222222222222222222222222"
FIX_COMMIT_SHA = "3333333333333333333333333333333333333333"


class TestSquashAwareOrdering(unittest.TestCase):
    """gh-aware squash path: evaluate ordering on the PR's ORIGINAL commits."""

    def setUp(self):
        self.health = _reimport("health")

    def _stub_gh(self, pr_list_payload, commits_by_pr):
        """Install a fake _gh_fetch_impl that answers:
          - `pr list ...` -> pr_list_payload (JSON string)
          - `pr view <n> --json commits` -> commits_by_pr[n] (JSON string)
        """
        health = self.health

        def _fake_gh_fetch(args, *, ttl, timeout):
            if args[:2] == ["pr", "list"]:
                return _GhResult(value=pr_list_payload)
            if args[:2] == ["pr", "view"]:
                pr_num = int(args[2])
                payload = commits_by_pr.get(pr_num)
                if payload is None:
                    return _GhResult(value=None, source="computing")
                return _GhResult(value=payload)
            return _GhResult(value=None, source="computing")

        health._gh_fetch_impl = _fake_gh_fetch
        health._GH_CACHE_AVAILABLE = True

    def _commit_payload(self, oids_and_headlines):
        return json.dumps({
            "commits": [
                {"oid": oid, "messageHeadline": headline}
                for oid, headline in oids_and_headlines
            ]
        })

    def _fake_subprocess_run(self, files_by_sha):
        """Return a subprocess.run stand-in that answers the specific git
        invocations check_test_ordering makes, without touching real git:
          - ["git", "show", "-s", "--format=%P", MERGE_SHA] -> one parent
            (squash signal)
          - ["git", "cat-file", "-t", <oid>] -> "commit" (rc=0) for any oid
            present in files_by_sha, else rc=1 (unreachable)
          - ["git", "diff-tree", ..., <oid>] -> newline-joined files from
            files_by_sha[oid]
        """
        def _run(args, **kwargs):
            if args[:2] == ["git", "show"]:
                # -s --format=%P <sha> -> single fake parent (squash: 1 parent)
                return _FakeCompletedProcess(stdout="parentparentparentparentparentparentparentpare\n")
            if args[:2] == ["git", "cat-file"]:
                oid = args[-1]
                if oid in files_by_sha:
                    return _FakeCompletedProcess(stdout="commit\n", returncode=0)
                return _FakeCompletedProcess(stdout="", returncode=1)
            if args[:2] == ["git", "diff-tree"]:
                oid = args[-1]
                files = files_by_sha.get(oid, [])
                return _FakeCompletedProcess(stdout="\n".join(files))
            if args[:2] == ["git", "log"]:
                # Direct-history path — not exercised by these squash tests.
                return _FakeCompletedProcess(stdout="")
            raise AssertionError(f"unexpected subprocess.run call: {args}")

        return _run

    def test_squash_merged_pr_test_before_fix_scores_ordered(self):
        """A squash-merged PR whose gh commit list is [test(...), fix(...)]
        scores ORDERED.

        FAILS BEFORE THE FIX: the current code has no gh-aware squash path;
        it evaluates the single squash commit via the direct-history walk,
        which (per the #1060 root-cause trace) can misclassify or fold
        sibling-PR commits into the range and score this disordered.
        """
        pr_list = json.dumps([
            {
                "number": 90001,
                "headRefName": "fix/90001-squash-ordered",
                "mergeCommit": {"oid": MERGE_SHA},
                "closingIssuesReferences": [{"number": 9000}],
            }
        ])
        # gh's ORIGINAL branch commit list: test commit precedes fix commit.
        commits_payload = self._commit_payload([
            (TEST_COMMIT_SHA, "test(widget): lock in ordering behavior (#9000)"),
            (FIX_COMMIT_SHA, "fix(widget): correct the ordering bug (#9000)"),
        ])
        self._stub_gh(pr_list, {90001: commits_payload})

        files_by_sha = {
            TEST_COMMIT_SHA: ["tests/test_widget.py"],
            FIX_COMMIT_SHA: ["widget.py"],
        }

        with patch("subprocess.run", side_effect=self._fake_subprocess_run(files_by_sha)):
            result = self.health.check_test_ordering()

        self.assertEqual(result["id"], "TEST-ORDERING")
        self.assertNotIn(90001, result.get("disordered", []),
                          "squash-merged PR with test-before-fix gh order "
                          "must NOT be in the disordered bucket")
        self.assertNotIn(90001, result.get("unverifiable", []))

    def test_squash_merged_pr_fix_before_test_scores_disordered(self):
        """A squash-merged PR whose gh commit list is [fix(...), test(...)]
        (fix precedes test) scores DISORDERED — no blanket pass for every
        squash-merged PR.
        """
        pr_list = json.dumps([
            {
                "number": 90002,
                "headRefName": "fix/90002-squash-disordered",
                "mergeCommit": {"oid": MERGE_SHA},
                "closingIssuesReferences": [{"number": 9001}],
            }
        ])
        # gh's ORIGINAL branch commit list: fix commit precedes test commit.
        commits_payload = self._commit_payload([
            (FIX_COMMIT_SHA, "fix(widget): correct the ordering bug (#9001)"),
            (TEST_COMMIT_SHA, "test(widget): lock in ordering behavior (#9001)"),
        ])
        self._stub_gh(pr_list, {90002: commits_payload})

        files_by_sha = {
            FIX_COMMIT_SHA: ["widget.py"],
            TEST_COMMIT_SHA: ["tests/test_widget.py"],
        }

        with patch("subprocess.run", side_effect=self._fake_subprocess_run(files_by_sha)):
            result = self.health.check_test_ordering()

        self.assertIn(90002, result.get("disordered", []),
                       "fix-before-test gh order must score disordered — "
                       "gh-awareness must not become a blanket pass")

    def test_gh_unavailable_for_commits_scores_unverifiable(self):
        """When `gh pr view N --json commits` is unavailable (computing
        sentinel / timeout), the PR is bucketed 'unverifiable' — NOT
        disordered, NOT silently ordered.
        """
        pr_list = json.dumps([
            {
                "number": 90003,
                "headRefName": "fix/90003-squash-gh-down",
                "mergeCommit": {"oid": MERGE_SHA},
                "closingIssuesReferences": [{"number": 9002}],
            }
        ])
        # commits_by_pr has NO entry for 90003 -> _stub_gh returns computing.
        self._stub_gh(pr_list, {})

        with patch("subprocess.run", side_effect=self._fake_subprocess_run({})):
            result = self.health.check_test_ordering()

        self.assertNotIn(90003, result.get("disordered", []),
                          "gh-unavailable PR must not be falsely disordered")
        unverifiable = result.get("unverifiable", [])
        self.assertIn(90003, unverifiable,
                       "gh-unavailable PR must be bucketed unverifiable")

    def test_squash_commit_object_gc_scores_unverifiable(self):
        """When gh reports commit oids but one is no longer reachable
        locally (e.g. GC'd), the PR is bucketed 'unverifiable' rather than
        crashing or silently scoring ordered/disordered.
        """
        pr_list = json.dumps([
            {
                "number": 90004,
                "headRefName": "fix/90004-squash-gc",
                "mergeCommit": {"oid": MERGE_SHA},
                "closingIssuesReferences": [{"number": 9003}],
            }
        ])
        commits_payload = self._commit_payload([
            (TEST_COMMIT_SHA, "test(widget): lock in ordering behavior (#9003)"),
            (FIX_COMMIT_SHA, "fix(widget): correct the ordering bug (#9003)"),
        ])
        self._stub_gh(pr_list, {90004: commits_payload})

        # Only TEST_COMMIT_SHA is "reachable" — FIX_COMMIT_SHA is missing,
        # simulating a GC'd object.
        files_by_sha = {
            TEST_COMMIT_SHA: ["tests/test_widget.py"],
        }

        with patch("subprocess.run", side_effect=self._fake_subprocess_run(files_by_sha)):
            result = self.health.check_test_ordering()

        self.assertNotIn(90004, result.get("disordered", []))
        self.assertIn(90004, result.get("unverifiable", []))


if __name__ == "__main__":
    unittest.main()
