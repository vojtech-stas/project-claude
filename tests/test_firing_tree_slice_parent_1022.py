"""
Regression test for issue #1022 — firing-tree slice→PRD resolver misses
real slices whose bodies say "Part of PRD #N" and/or have native sub-issue
parent links.

Root causes (two):
  1. _PARENT_PRD_BODY_RE does NOT match the real template wording
     "Part of PRD #N" — only "slice of PRD #N" / "Parent: PRD #N" matched.
  2. _resolve_slice_to_prd does NOT query the native GitHub sub-issue parent
     endpoint (gh api .../issues/{n}/parent) before falling back to body parse.

These tests FAIL on develop b37f062 (before the fix) and PASS after (commit #2).

Assertions:
  (a) A slice whose body says "Part of PRD #993" → resolve_dispatch_to_prd
      returns 993.  FAILS before fix (returns None).
  (b) A prd-labeled issue #993 → resolve_dispatch_to_prd returns 993
      (unchanged — the _IS_PRD path must stay intact).
  (c) A non-PRD issue with no parent body + no sub-issue parent → returns None
      (must not create a phantom PRD node).
  (d) gh transport failure for the sub-issue parent endpoint → no crash; falls
      back gracefully (returns None or _GH_UNAVAILABLE → None from caller).

NO top-level `import pytest` — stdlib unittest only.

Runner:
  python -m unittest tests.test_firing_tree_slice_parent_1022 -v
  python -m pytest tests/test_firing_tree_slice_parent_1022.py -v
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

def _make_gh_run(
    issue_labels: dict[int, list[str]],
    issue_bodies: dict[int, str] | None = None,
    sub_issue_parents: dict[int, int | None] | None = None,
):
    """Return a fake _gh_run_transcript that responds to:
      - gh issue view <N> --json number,labels,body
      - gh api repos/.../issues/<N>/parent --jq .number

    issue_labels: {issue_number: [label_name, ...]}
    issue_bodies: {issue_number: body_text} (optional; defaults to "")
    sub_issue_parents: {issue_number: parent_prd_number or None}
      None  → simulate a 404 (no parent link)
      int   → simulate a parent link returning that number
      missing key → simulate a gh failure (rc=1)
    """
    if issue_bodies is None:
        issue_bodies = {}
    if sub_issue_parents is None:
        sub_issue_parents = {}

    def fake_gh_run(args: list[str], timeout: int = 15):
        # Handle: gh api repos/.../issues/<N>/parent --jq .number
        # The real call looks like: gh api repos/{owner}/{repo}/issues/{n}/parent --jq .number
        if "api" in args:
            # Find the issue number from the path segment
            num = None
            for a in args:
                if "/issues/" in a and "/parent" in a:
                    parts = a.split("/")
                    try:
                        idx = parts.index("issues")
                        num = int(parts[idx + 1])
                    except (ValueError, IndexError):
                        pass
                    break
            if num is None:
                return 1, ""
            if num not in sub_issue_parents:
                # Not in mock → simulate gh failure
                return 1, ""
            parent_val = sub_issue_parents[num]
            if parent_val is None:
                # Simulate 404 (no parent link) — the parent endpoint returns
                # an empty body or null; we'll model this as rc=0, stdout="null"
                return 0, "null"
            return 0, str(parent_val)

        # Handle: gh issue view <N> --json number,labels,body
        if "issue" not in args or "view" not in args:
            return 1, ""
        num = None
        for a in args:
            try:
                num = int(a)
                break
            except (ValueError, TypeError):
                continue
        if num is None:
            return 1, ""
        if num not in issue_labels:
            return 1, ""
        labels = [{"name": n} for n in issue_labels[num]]
        body = issue_bodies.get(num, "")
        return 0, json.dumps({"number": num, "labels": labels, "body": body})

    return fake_gh_run


# ---------------------------------------------------------------------------
# Case (a): "Part of PRD #N" body wording → must resolve to parent PRD
# ---------------------------------------------------------------------------

class TestPartOfPrdBodyWording(unittest.TestCase):
    """resolve_dispatch_to_prd(N) must return the parent PRD when the slice
    body uses the real template wording 'Part of PRD #N'.

    FAILS before fix (returns None — the regex misses 'Part of PRD').
    PASSES after fix (either via broadened regex or sub-issue parent endpoint).
    """

    def setUp(self):
        _inject_dashboard()
        import transcript
        self.transcript = transcript
        transcript._prd_cache.clear()
        transcript._disk_cache_data = {}

    def test_part_of_prd_body_wording_resolves_to_parent(self):
        """Slice #995 with body 'Part of PRD #993 — walking skeleton' and
        sub-issue parent 993 → resolve_dispatch_to_prd(995) must return 993.

        FAILS before fix: _PARENT_PRD_BODY_RE misses 'Part of PRD', and
        _resolve_slice_to_prd does not query sub-issue parent endpoint → None.
        PASSES after fix: either the broadened regex OR the sub-issue parent
        endpoint returns 993.
        """
        issue_labels = {
            995: ["slice"],
            993: ["prd"],
        }
        issue_bodies = {
            995: "Part of PRD #993 — walking skeleton of the firing tree feature.",
            993: "PRD body text.",
        }
        # Sub-issue parent endpoint: 995 → 993
        sub_issue_parents = {995: 993, 993: None}

        fake_gh = _make_gh_run(issue_labels, issue_bodies, sub_issue_parents)

        with patch.object(self.transcript, "_gh_run_transcript", side_effect=fake_gh):
            result = self.transcript.resolve_dispatch_to_prd(995)

        self.assertEqual(
            result, 993,
            msg=(
                f"resolve_dispatch_to_prd(995) returned {result!r} — expected 993.\n\n"
                "BEFORE FIX: _PARENT_PRD_BODY_RE misses 'Part of PRD #993'; "
                "_resolve_slice_to_prd does not query sub-issue parent → returns None.\n"
                "AFTER FIX: either broadened regex or sub-issue parent endpoint "
                "returns 993."
            ),
        )

    def test_part_of_prd_body_only_no_sub_issue_parent(self):
        """Slice #996 with body 'Part of PRD #993' but sub-issue parent is None
        (no native link) → must resolve via body fallback → 993.

        This tests the broadened body regex fallback when the sub-issue endpoint
        returns null/404 but the body wording is 'Part of PRD #N'.

        FAILS before fix: regex misses 'Part of PRD'.
        PASSES after fix: broadened regex matches.
        """
        issue_labels = {996: ["slice"]}
        issue_bodies = {996: "Part of PRD #993 — second slice."}
        # Sub-issue parent: 996 → null (no native link; fall through to body)
        sub_issue_parents = {996: None}

        fake_gh = _make_gh_run(issue_labels, issue_bodies, sub_issue_parents)

        with patch.object(self.transcript, "_gh_run_transcript", side_effect=fake_gh):
            result = self.transcript.resolve_dispatch_to_prd(996)

        self.assertEqual(
            result, 993,
            msg=(
                f"resolve_dispatch_to_prd(996) returned {result!r} — expected 993.\n\n"
                "BEFORE FIX: body regex misses 'Part of PRD #993' → returns None.\n"
                "AFTER FIX: broadened _PARENT_PRD_BODY_RE matches 'Part of PRD #993'."
            ),
        )


# ---------------------------------------------------------------------------
# Case (b): prd-labeled issue → returns itself (unchanged path)
# ---------------------------------------------------------------------------

class TestPrdLabeledIssueReturnsSelf(unittest.TestCase):
    """Genuine prd-labeled issue #993 → resolve_dispatch_to_prd(993) returns 993.

    This is the pre-existing behaviour; the fix must NOT break it.
    PASSES both before and after fix.
    """

    def setUp(self):
        _inject_dashboard()
        import transcript
        self.transcript = transcript
        transcript._prd_cache.clear()
        transcript._disk_cache_data = {}

    def test_prd_labeled_returns_self(self):
        """Issue #993 labeled 'prd' → resolve_dispatch_to_prd returns 993.

        The _IS_PRD sentinel path must stay intact regardless of fix.
        """
        issue_labels = {993: ["prd"]}
        issue_bodies = {993: "PRD body."}
        sub_issue_parents = {993: None}

        fake_gh = _make_gh_run(issue_labels, issue_bodies, sub_issue_parents)

        with patch.object(self.transcript, "_gh_run_transcript", side_effect=fake_gh):
            result = self.transcript.resolve_dispatch_to_prd(993)

        self.assertEqual(
            result, 993,
            msg=(
                f"resolve_dispatch_to_prd(993) returned {result!r} — expected 993.\n\n"
                "The fix must preserve the _IS_PRD path: a genuine PRD still resolves "
                "to itself."
            ),
        )


# ---------------------------------------------------------------------------
# Case (c): non-PRD issue, no parent body, no sub-issue parent → None
# ---------------------------------------------------------------------------

class TestNonPrdNoParentReturnsNone(unittest.TestCase):
    """Non-prd issue with no parent body AND no sub-issue parent → None.

    Must not create a phantom PRD node.
    PASSES both before and after fix (regression guard).
    """

    def setUp(self):
        _inject_dashboard()
        import transcript
        self.transcript = transcript
        transcript._prd_cache.clear()
        transcript._disk_cache_data = {}

    def test_captured_issue_no_parent_returns_none(self):
        """Issue #729 labeled 'captured' with no parent PRD in body and
        sub-issue parent = None → resolve_dispatch_to_prd returns None.
        """
        issue_labels = {729: ["captured"]}
        issue_bodies = {729: "A plain captured issue."}
        sub_issue_parents = {729: None}

        fake_gh = _make_gh_run(issue_labels, issue_bodies, sub_issue_parents)

        with patch.object(self.transcript, "_gh_run_transcript", side_effect=fake_gh):
            result = self.transcript.resolve_dispatch_to_prd(729)

        self.assertIsNone(
            result,
            msg=(
                f"resolve_dispatch_to_prd(729) returned {result!r} — expected None.\n\n"
                "A non-prd issue with no parent PRD must not create a phantom PRD node."
            ),
        )


# ---------------------------------------------------------------------------
# Case (d): gh transport failure → no crash, graceful None
# ---------------------------------------------------------------------------

class TestGhTransportFailureNoCrash(unittest.TestCase):
    """When gh fails (transport error) for the sub-issue parent AND issue view,
    resolve_dispatch_to_prd must not crash and must return None.
    """

    def setUp(self):
        _inject_dashboard()
        import transcript
        self.transcript = transcript
        transcript._prd_cache.clear()
        transcript._disk_cache_data = {}

    def test_gh_failure_returns_none_no_crash(self):
        """All gh calls fail → resolve_dispatch_to_prd(995) returns None
        (not crash, not phantom PRD).
        """
        def always_fail(args, timeout=15):
            return 1, ""

        with patch.object(self.transcript, "_gh_run_transcript", side_effect=always_fail):
            try:
                result = self.transcript.resolve_dispatch_to_prd(995)
            except Exception as exc:
                self.fail(
                    f"resolve_dispatch_to_prd raised {type(exc).__name__}: {exc} "
                    "— must not crash on gh transport failure."
                )

        self.assertIsNone(
            result,
            msg=(
                f"resolve_dispatch_to_prd(995) returned {result!r} — expected None.\n\n"
                "When gh is fully unavailable, must return None (not phantom PRD, "
                "not crash)."
            ),
        )


if __name__ == "__main__":
    unittest.main()
