"""
Regression tests for PRD #919 slice #922 — slicer-provenance guard.

Verifies:
1. body_has_provenance() returns True for a body with the canonical trailer.
2. body_has_provenance() returns False for a hand-made slice body with no marker.
3. body_has_provenance() is case-insensitive.
4. body_has_provenance() handles empty / None-ish body gracefully.
5. The aggregation logic: a list of fixture issue dicts — any missing the
   trailer causes the guard to report failures (mirrors main()'s missing list).

All tests are offline, deterministic, and network-free.

Runner: stdlib unittest + pytest compatible.
  python -m pytest tests/test_slicer_provenance.py -v
  python -m unittest tests.test_slicer_provenance -v
"""

import sys
import unittest
from pathlib import Path

# ---------------------------------------------------------------------------
# Ensure tools/ is importable
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parent.parent
_TOOLS_DIR = _REPO_ROOT / "tools"
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))

# Import using importlib to handle the hyphenated module name
import importlib.util as _ilu

_spec = _ilu.spec_from_file_location(
    "check_slicer_provenance",
    str(_TOOLS_DIR / "check-slicer-provenance.py"),
)
_mod = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

body_has_provenance = _mod.body_has_provenance


# ---------------------------------------------------------------------------
# Tests for body_has_provenance()
# ---------------------------------------------------------------------------


class TestBodyHasProvenance(unittest.TestCase):
    """Unit tests for the pure body_has_provenance() function."""

    # ------------------------------------------------------------------ True
    def test_canonical_trailer_detected(self):
        """Canonical Slicer-provenance: trailer is detected."""
        body = (
            "## Parent\n\nPRD #919\n\n"
            "## What ships\n\nSomething.\n\n"
            "Slicer-provenance: slicer-critic-APPROVED decomposition of PRD #919 (round 2)."
        )
        self.assertTrue(body_has_provenance(body))

    def test_trailer_at_first_line(self):
        """Trailer on the very first line is detected."""
        body = "Slicer-provenance: slicer-critic-APPROVED decomposition of PRD #1 (round 1)."
        self.assertTrue(body_has_provenance(body))

    def test_trailer_case_insensitive_lower(self):
        """Lowercase 'slicer-provenance:' is accepted."""
        body = "slicer-provenance: anything goes here"
        self.assertTrue(body_has_provenance(body))

    def test_trailer_case_insensitive_mixed(self):
        """Mixed-case 'SLICER-PROVENANCE:' is accepted."""
        body = "SLICER-PROVENANCE: uppercase variant"
        self.assertTrue(body_has_provenance(body))

    def test_trailer_with_leading_whitespace(self):
        """Trailer with leading spaces/tabs is detected (tolerate minor indentation)."""
        body = "  Slicer-provenance: indented trailer"
        self.assertTrue(body_has_provenance(body))

    # ---------------------------------------------------------------- False
    def test_hand_made_slice_no_marker(self):
        """A hand-made slice body without the marker returns False (the acceptance criterion)."""
        body = (
            "## Parent\n\nPRD #919\n\n"
            "## What ships\n\nThis slice was hand-created via raw gh issue create.\n\n"
            "## Acceptance criteria\n\n- [ ] Something\n"
        )
        self.assertFalse(body_has_provenance(body))

    def test_empty_body(self):
        """Empty string returns False."""
        self.assertFalse(body_has_provenance(""))

    def test_none_equivalent_empty(self):
        """None-equivalent (falsy) string returns False."""
        self.assertFalse(body_has_provenance(""))

    def test_body_with_slicer_word_but_no_trailer(self):
        """'slicer' appearing in prose but NOT as a trailer key returns False."""
        body = (
            "The slicer subagent created this.\n"
            "Provenance is important.\n"
            "But there is no Slicer-provenance: trailer here."
        )
        self.assertFalse(body_has_provenance(body))

    def test_provenance_in_middle_of_line_not_detected(self):
        """'Slicer-provenance:' NOT at the start of a (stripped) line returns False."""
        body = "See also Slicer-provenance: this is mid-sentence"
        # "See also Slicer-provenance:" → stripped starts with "See also..." → False
        self.assertFalse(body_has_provenance(body))


# ---------------------------------------------------------------------------
# Tests for aggregation logic (mirrors main()'s `missing` list logic)
# ---------------------------------------------------------------------------


class TestAggregationLogic(unittest.TestCase):
    """Tests for the aggregation logic over a list of fixture issue dicts."""

    @staticmethod
    def _missing_numbers(issues: list[dict]) -> list[int]:
        """Replicate main()'s aggregation to find missing-trailer issue numbers."""
        return [
            issue["number"]
            for issue in issues
            if not body_has_provenance(issue.get("body") or "")
        ]

    def test_all_with_trailer_returns_empty_list(self):
        """All issues with the trailer → missing list is empty → guard passes."""
        issues = [
            {
                "number": 101,
                "body": (
                    "## Parent\n\nPRD #919\n\n"
                    "Slicer-provenance: slicer-critic-APPROVED decomposition of PRD #919 (round 1)."
                ),
            },
            {
                "number": 102,
                "body": "Slicer-provenance: slicer-critic-APPROVED decomposition of PRD #920 (round 1).",
            },
        ]
        self.assertEqual(self._missing_numbers(issues), [])

    def test_one_missing_trailer_flagged(self):
        """One issue lacking the trailer is flagged in the missing list."""
        issues = [
            {
                "number": 201,
                "body": (
                    "Slicer-provenance: slicer-critic-APPROVED decomposition of PRD #919 (round 1)."
                ),
            },
            {
                "number": 202,
                "body": "## Parent\n\nNo provenance trailer here.",
            },
        ]
        missing = self._missing_numbers(issues)
        self.assertEqual(missing, [202])

    def test_multiple_missing_trailers_all_flagged(self):
        """Multiple issues lacking the trailer are all in the missing list."""
        issues = [
            {"number": 301, "body": "hand-made body one"},
            {"number": 302, "body": "hand-made body two"},
            {
                "number": 303,
                "body": "Slicer-provenance: approved.",
            },
        ]
        missing = self._missing_numbers(issues)
        self.assertIn(301, missing)
        self.assertIn(302, missing)
        self.assertNotIn(303, missing)

    def test_empty_issue_list_no_missing(self):
        """Empty issue list → no missing → guard passes vacuously."""
        self.assertEqual(self._missing_numbers([]), [])

    def test_issue_with_none_body_flagged(self):
        """An issue whose body key is None is treated as missing-trailer (flagged)."""
        issues = [{"number": 401, "body": None}]
        self.assertEqual(self._missing_numbers(issues), [401])


if __name__ == "__main__":
    unittest.main()
