"""
Regression test for issue #1018 — resolve_dispatch_to_prd must NOT return
a phantom PRD number when the referenced issue is NOT prd-labeled and has
no resolvable parent PRD.

Root cause: _resolve_slice_to_prd returned None in two distinct cases:
  (a) issue IS labeled 'prd'  → correct to treat as a PRD
  (b) issue is NOT labeled 'prd' but has no parent body pattern
      → INCORRECT: resolve_dispatch_to_prd treated this as "is a PRD"
        and returned N as a phantom PRD number

These tests FAIL on develop before the fix and PASS after (commit #2).

Assertions:
  1. A dispatch on a non-prd-labeled issue (#999, labels=['captured']) with
     no resolvable parent PRD → resolve_dispatch_to_prd returns None.
  2. A dispatch on a genuine prd-labeled issue (#993) → returns 993.
  3. _derive_prd_label() for a non-prd issue returns a non-PRD bucket label
     (not 'PRD #999').

NO top-level `import pytest` — stdlib unittest only.

Runner:
  python -m unittest tests.test_no_phantom_prd_1018 -v
  python -m pytest tests/test_no_phantom_prd_1018.py -v
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
# Shared gh mock helpers
# ---------------------------------------------------------------------------

def _make_gh_run(issue_labels: dict[int, list[str]], issue_bodies: dict[int, str] | None = None):
    """Return a fake _gh_run_transcript that maps issue numbers to label/body data.

    issue_labels: {issue_number: [label_name, ...]}
    issue_bodies: {issue_number: body_text} (optional; defaults to "" for each)
    """
    if issue_bodies is None:
        issue_bodies = {}

    def fake_gh_run(args: list[str], timeout: int = 15):
        # Only handle: gh issue view <N> --json number,labels,body
        if "issue" not in args or "view" not in args:
            return 1, ""
        # Find the numeric argument (the issue number)
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
            # Issue not in our mock → simulate not found
            return 1, ""
        labels = [{"name": n} for n in issue_labels[num]]
        body = issue_bodies.get(num, "")
        return 0, json.dumps({"number": num, "labels": labels, "body": body})

    return fake_gh_run


# ---------------------------------------------------------------------------
# Test group 1: Non-prd-labeled issue → resolve_dispatch_to_prd returns None
# ---------------------------------------------------------------------------

class TestNonPrdIssueNoPhantomPrd(unittest.TestCase):
    """resolve_dispatch_to_prd(N) must return None when issue #N is NOT
    labeled 'prd' and has no resolvable parent PRD in its body.

    Before fix: _resolve_slice_to_prd returns None for both 'is a PRD' and
      'not a PRD but no parent found' cases; resolve_dispatch_to_prd then
      falls into the 'result is None → return N' branch, creating phantom PRD.
    After fix:  _resolve_slice_to_prd distinguishes the two cases; the
      'not a PRD but no parent found' case causes resolve_dispatch_to_prd
      to return None (not N).
    """

    def setUp(self):
        _inject_dashboard()
        import transcript
        self.transcript = transcript
        # Clear the in-process cache between tests so mocks take effect
        transcript._prd_cache.clear()
        transcript._disk_cache_data = {}

    def test_captured_issue_no_prd_parent_returns_none(self):
        """Issue #999 labeled 'captured' with no parent PRD body
        → resolve_dispatch_to_prd(999) must return None, NOT 999.

        FAILS before fix: returns 999 (phantom PRD).
        PASSES after fix: returns None (routes to maintenance bucket).
        """
        # Issue #999 is captured (not prd, not slice), no parent in body
        issue_labels = {999: ["captured"]}
        issue_bodies = {999: "This is a captured issue with no PRD parent."}

        fake_gh = _make_gh_run(issue_labels, issue_bodies)

        with patch.object(self.transcript, "_gh_run_transcript", side_effect=fake_gh):
            result = self.transcript.resolve_dispatch_to_prd(999)

        self.assertIsNone(
            result,
            msg=(
                f"resolve_dispatch_to_prd(999) returned {result!r} — "
                "expected None for a captured (non-prd) issue with no parent PRD.\n\n"
                "BEFORE FIX: _resolve_slice_to_prd returns None for both 'is a PRD' "
                "and 'not a PRD, no parent' → caller incorrectly returns N as a phantom PRD.\n"
                "AFTER FIX:  the two None-cases are distinguished; 'not a PRD, no parent' "
                "→ resolve_dispatch_to_prd returns None (maintenance bucket)."
            ),
        )

    def test_slice_issue_no_prd_label_no_parent_body_returns_none(self):
        """Issue #888 labeled 'slice' but with no parent PRD body pattern
        → resolve_dispatch_to_prd(888) must return None.

        A slice with a malformed or missing parent-PRD annotation should NOT
        create a phantom 'PRD #888' node; it should return None.

        FAILS before fix: returns 888.
        PASSES after fix: returns None.
        """
        issue_labels = {888: ["slice"]}
        issue_bodies = {888: "Some slice body without the 'slice N of PRD #M' pattern."}

        fake_gh = _make_gh_run(issue_labels, issue_bodies)

        with patch.object(self.transcript, "_gh_run_transcript", side_effect=fake_gh):
            result = self.transcript.resolve_dispatch_to_prd(888)

        self.assertIsNone(
            result,
            msg=(
                f"resolve_dispatch_to_prd(888) returned {result!r} — "
                "expected None for a slice issue with no parseable parent PRD body.\n\n"
                "BEFORE FIX: returns 888 (phantom PRD node).\n"
                "AFTER FIX:  returns None (maintenance bucket)."
            ),
        )

    def test_pr_number_no_parent_prd_returns_none(self):
        """A PR number #1000 (which is not a gh issue → issue view fails)
        that also has no 'Closes #slice' → resolve_dispatch_to_prd returns None.

        FAILS before fix: may return 1000 via the self-fallback path.
        PASSES after fix: returns None.

        Note: since _resolve_slice_to_prd and _resolve_pr_to_prd both fail for
        an unknown number, the function should return None (gh unavailable path).
        This test locks down that None is returned for completely unknown #N.
        """
        # Mock: no issue 1000 exists (rc=1 for issue view), no PR either
        def fake_gh_run_none(args: list[str], timeout: int = 15):
            return 1, ""

        with patch.object(self.transcript, "_gh_run_transcript", side_effect=fake_gh_run_none):
            result = self.transcript.resolve_dispatch_to_prd(1000)

        # gh unavailable → must return None (not 1000 as a phantom PRD)
        self.assertIsNone(
            result,
            msg=(
                f"resolve_dispatch_to_prd(1000) returned {result!r} — "
                "expected None when gh is unavailable (issue not found).\n\n"
                "BEFORE FIX: may return 1000 as a phantom PRD via self-fallback.\n"
                "AFTER FIX:  returns None (gh unavailable path is unchanged; "
                "but we assert this contract explicitly)."
            ),
        )


# ---------------------------------------------------------------------------
# Test group 2: Genuine prd-labeled issue → returns its own number
# ---------------------------------------------------------------------------

class TestPrdLabeledIssueReturnsSelf(unittest.TestCase):
    """resolve_dispatch_to_prd(N) when #N IS labeled 'prd' must return N.

    This is the pre-existing behaviour that the fix must preserve.
    """

    def setUp(self):
        _inject_dashboard()
        import transcript
        self.transcript = transcript
        transcript._prd_cache.clear()
        transcript._disk_cache_data = {}

    def test_prd_labeled_issue_returns_own_number(self):
        """Issue #993 labeled 'prd' → resolve_dispatch_to_prd(993) must return 993.

        PASSES both before and after fix.
        This test is a sanity guard: the fix must not break the PRD self-resolution.
        """
        issue_labels = {993: ["prd"]}
        issue_bodies = {993: "This is a PRD issue body."}

        fake_gh = _make_gh_run(issue_labels, issue_bodies)

        with patch.object(self.transcript, "_gh_run_transcript", side_effect=fake_gh):
            result = self.transcript.resolve_dispatch_to_prd(993)

        self.assertEqual(
            result, 993,
            msg=(
                f"resolve_dispatch_to_prd(993) returned {result!r} — "
                "expected 993 for a prd-labeled issue (self-resolution).\n\n"
                "The fix must preserve this: a genuine PRD still maps to itself."
            ),
        )

    def test_slice_issue_with_parent_body_returns_parent(self):
        """Issue #956 labeled 'slice' with 'slice 1 of PRD #950' body
        → resolve_dispatch_to_prd(956) must return 950.

        PASSES both before and after fix (parent-body resolution path is unaffected).
        """
        issue_labels = {956: ["slice"]}
        issue_bodies = {956: "Walking-skeleton slice of PRD #950 — implementing the thing."}

        fake_gh = _make_gh_run(issue_labels, issue_bodies)

        with patch.object(self.transcript, "_gh_run_transcript", side_effect=fake_gh):
            result = self.transcript.resolve_dispatch_to_prd(956)

        self.assertEqual(
            result, 950,
            msg=(
                f"resolve_dispatch_to_prd(956) returned {result!r} — "
                "expected 950 (parent PRD parsed from body).\n\n"
                "The fix must preserve this: slice-with-parent-body still resolves to PRD."
            ),
        )


# ---------------------------------------------------------------------------
# Test group 3: _derive_prd_label — non-prd issue gets non-PRD bucket label
# ---------------------------------------------------------------------------

class TestDerivePrdLabelNonPrd(unittest.TestCase):
    """_derive_prd_label() for a non-prd-labeled dispatch must NOT produce
    a 'PRD #N' bucket label.

    Before fix: resolve_dispatch_to_prd(999) returns 999 (phantom PRD)
      → _derive_prd_label returns 'PRD #999'.
    After fix:  resolve_dispatch_to_prd(999) returns None
      → _derive_prd_label returns a non-PRD fallback (e.g. '#999 (gh unavailable)'
        or the agent_type).
    """

    def setUp(self):
        _inject_dashboard()
        import transcript
        self.transcript = transcript
        transcript._prd_cache.clear()
        transcript._disk_cache_data = {}

    def test_captured_issue_dispatch_not_prd_labeled(self):
        """_derive_prd_label for a description referencing #999 (captured)
        must NOT return 'PRD #999'.

        FAILS before fix: returns 'PRD #999'.
        PASSES after fix: returns a non-PRD label.
        """
        issue_labels = {999: ["captured"]}
        issue_bodies = {999: "Captured issue — no PRD parent."}

        fake_gh = _make_gh_run(issue_labels, issue_bodies)

        with patch.object(self.transcript, "_gh_run_transcript", side_effect=fake_gh):
            label = self.transcript._derive_prd_label(
                "backlog-critic for #999", "backlog-critic", use_gh=True
            )

        self.assertNotEqual(
            label, "PRD #999",
            msg=(
                f"_derive_prd_label returned {label!r} — must NOT be 'PRD #999' "
                "for a captured (non-prd) issue.\n\n"
                "BEFORE FIX: resolve_dispatch_to_prd returns 999 → label='PRD #999'.\n"
                "AFTER FIX:  resolve_dispatch_to_prd returns None → label is a "
                "non-PRD fallback (e.g. '#999 (gh unavailable)' or agent_type)."
            ),
        )
        self.assertFalse(
            label.startswith("PRD #"),
            msg=(
                f"_derive_prd_label returned {label!r} which starts with 'PRD #' — "
                "no non-prd-labeled issue should produce a 'PRD #N' bucket.\n\n"
                "BEFORE FIX: phantom 'PRD #999' bucket.\n"
                "AFTER FIX:  non-PRD fallback label."
            ),
        )


if __name__ == "__main__":
    unittest.main()
