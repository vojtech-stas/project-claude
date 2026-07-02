"""
Regression test for issue #1030 — firing-tree mislabels genuinely-non-PRD
dispatches as "#N (gh unavailable)" when gh actually succeeded.

Root cause: resolve_dispatch_to_prd() collapses THREE distinct outcomes into
a single `None` return: (a) gh transport failure (_GH_UNAVAILABLE), (b)
resolved-but-genuinely-no-PRD-parent, (c) unresolvable.  _derive_prd_label()
then labels ALL `None` results as "#N (gh unavailable)" — so a genuinely
non-PRD issue (gh fully available, no PRD parent) is mislabeled as a
transient gh problem.

These tests FAIL on develop before the fix and PASS after (commit #2):
  (a) A non-PRD issue with a SUCCESSFUL gh lookup (no PRD parent found) →
      _derive_prd_label() must yield a "non-PRD" label, NOT "gh unavailable".
  (b) A gh TRANSPORT FAILURE (_GH_UNAVAILABLE) → must still yield
      "(gh unavailable)" (unchanged behaviour for the real failure case).

NO top-level `import pytest` — stdlib unittest only.

Runner:
  python -m unittest tests.test_firing_nonprd_label_1030 -v
  python -m pytest tests/test_firing_nonprd_label_1030.py -v
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).parent.parent
DASHBOARD_DIR = REPO_ROOT / "dashboard"


def _inject_dashboard() -> None:
    s = str(DASHBOARD_DIR)
    if s not in sys.path:
        sys.path.insert(0, s)


# ---------------------------------------------------------------------------
# gh mock helpers
# ---------------------------------------------------------------------------

def _make_gh_run_success_no_parent(issue_labels: dict, issue_bodies: dict | None = None):
    """Return a fake _gh_run_transcript where `gh issue view` SUCCEEDS for the
    given issue numbers (rc=0) but the issue has no PRD parent (not
    prd-labeled, no body reference, no sub-issue parent link) — and the repo
    slug lookup (needed for the sub-issue /parent fallback) ALSO succeeds, so
    the overall gh transport is fully healthy.
    """
    if issue_bodies is None:
        issue_bodies = {}

    def fake_gh_run(args: list[str], timeout: int = 15):
        # gh repo view --json nameWithOwner -q .nameWithOwner
        if "repo" in args and "view" in args:
            return 0, "owner/repo"

        # gh api repos/{slug}/issues/{n}/parent --jq .number
        if "api" in args:
            # Simulate a healthy 404-shaped "no parent" response (rc=0, null).
            return 0, "null"

        # gh issue view <N> --json number,labels,body
        if "issue" in args and "view" in args:
            num = None
            for a in args:
                try:
                    num = int(a)
                    break
                except (ValueError, TypeError):
                    continue
            if num is None or num not in issue_labels:
                return 1, ""
            labels = [{"name": n} for n in issue_labels[num]]
            body = issue_bodies.get(num, "")
            return 0, json.dumps({"number": num, "labels": labels, "body": body})

        return 1, ""

    return fake_gh_run


def _always_fail_gh(args: list[str], timeout: int = 15):
    """Simulate a full gh transport failure (rc != 0) for every call."""
    return 1, ""


# ---------------------------------------------------------------------------
# Case (a): gh SUCCEEDS, issue has no PRD parent → "non-PRD" label
# ---------------------------------------------------------------------------

class TestNonPrdLabelWhenGhSucceeds(unittest.TestCase):
    """A genuinely-non-PRD issue with a SUCCESSFUL gh lookup must NOT be
    labeled "(gh unavailable)" — gh worked fine, there's just no PRD parent.

    FAILS before fix: _derive_prd_label returns "#999 (gh unavailable)".
    PASSES after fix: _derive_prd_label returns "#999 (non-PRD)" (or an
    equivalent label that does NOT contain the substring "gh unavailable").
    """

    def setUp(self):
        _inject_dashboard()
        import transcript
        self.transcript = transcript
        transcript._prd_cache.clear()
        transcript._prd_cache_ts = 0.0
        transcript._disk_cache_data = {}
        transcript._transcript_repo_slug = None

    def tearDown(self):
        import transcript
        transcript._prd_cache.clear()
        transcript._prd_cache_ts = 0.0
        transcript._disk_cache_data = None
        transcript._transcript_repo_slug = None

    def test_derive_prd_label_non_prd_not_gh_unavailable(self):
        """_derive_prd_label() for a genuinely-non-PRD issue (gh succeeded)
        must NOT contain "gh unavailable" in the label.
        """
        issue_labels = {999: ["captured"]}
        issue_bodies = {999: "A plain captured issue with no PRD parent."}
        fake_gh = _make_gh_run_success_no_parent(issue_labels, issue_bodies)

        with patch.object(self.transcript, "_gh_run_transcript", side_effect=fake_gh):
            label = self.transcript._derive_prd_label(
                "backlog-critic for #999", "backlog-critic", use_gh=True
            )

        self.assertNotIn(
            "gh unavailable", label,
            msg=(
                f"_derive_prd_label returned {label!r} — must NOT say "
                "'gh unavailable' when gh actually succeeded and the issue "
                "simply has no PRD parent.\n\n"
                "BEFORE FIX: resolve_dispatch_to_prd collapses gh-success-"
                "no-parent and gh-transport-failure into the same None → "
                "label='#999 (gh unavailable)'.\n"
                "AFTER FIX: label should read something like '#999 (non-PRD)'."
            ),
        )
        self.assertIn("999", label, f"Expected issue number in label, got: {label!r}")

    def test_resolve_dispatch_to_prd_still_returns_none(self):
        """Public contract of resolve_dispatch_to_prd(N) -> int | None is
        unchanged: a genuinely-non-PRD issue still returns None (existing
        callers depend on this — see #1018 regression tests).
        """
        issue_labels = {999: ["captured"]}
        issue_bodies = {999: "A plain captured issue with no PRD parent."}
        fake_gh = _make_gh_run_success_no_parent(issue_labels, issue_bodies)

        with patch.object(self.transcript, "_gh_run_transcript", side_effect=fake_gh):
            result = self.transcript.resolve_dispatch_to_prd(999)

        self.assertIsNone(
            result,
            msg=f"resolve_dispatch_to_prd(999) returned {result!r}, expected None.",
        )


# ---------------------------------------------------------------------------
# Case (b): gh TRANSPORT FAILURE → "(gh unavailable)" label preserved
# ---------------------------------------------------------------------------

class TestGhUnavailableLabelPreserved(unittest.TestCase):
    """A real gh transport failure must still produce the "(gh unavailable)"
    label — this is the genuine-failure case and must not regress.
    """

    def setUp(self):
        _inject_dashboard()
        import transcript
        self.transcript = transcript
        transcript._prd_cache.clear()
        transcript._prd_cache_ts = 0.0
        transcript._disk_cache_data = {}
        transcript._transcript_repo_slug = None

    def tearDown(self):
        import transcript
        transcript._prd_cache.clear()
        transcript._prd_cache_ts = 0.0
        transcript._disk_cache_data = None
        transcript._transcript_repo_slug = None

    def test_derive_prd_label_gh_unavailable_on_transport_failure(self):
        """_derive_prd_label() must say "gh unavailable" when gh transport
        genuinely fails (rc != 0 on the primary issue-view call).
        """
        with patch.object(self.transcript, "_gh_run_transcript", side_effect=_always_fail_gh):
            label = self.transcript._derive_prd_label(
                "Run implementer for #958", "implementer", use_gh=True
            )

        self.assertIn(
            "gh unavailable", label,
            msg=(
                f"_derive_prd_label returned {label!r} — expected 'gh "
                "unavailable' to be preserved for a genuine gh transport "
                "failure."
            ),
        )
        self.assertIn("958", label, f"Expected issue number in label, got: {label!r}")

    def test_resolve_dispatch_to_prd_returns_none_on_failure(self):
        """Public contract preserved: gh transport failure -> None."""
        with patch.object(self.transcript, "_gh_run_transcript", side_effect=_always_fail_gh):
            result = self.transcript.resolve_dispatch_to_prd(958)

        self.assertIsNone(
            result,
            msg=f"resolve_dispatch_to_prd(958) returned {result!r}, expected None.",
        )


if __name__ == "__main__":
    unittest.main()
