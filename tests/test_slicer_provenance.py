"""
Regression tests for PRD #919 slice #922 — slicer-provenance guard.
Extended for slice #1067 — recognize the rule-#13 root-cause lane.

Verifies:
1. body_has_provenance() returns True for a body with the canonical trailer.
2. body_has_provenance() returns False for a hand-made slice body with no marker.
3. body_has_provenance() is case-insensitive.
4. body_has_provenance() handles empty / None-ish body gracefully.
5. The aggregation logic: a list of fixture issue dicts — any missing the
   trailer causes the guard to report failures (mirrors main()'s missing list).
6. is_root_cause_exempt() recognizes the `root-cause` label (rule #13 lane)
   as exempt from the Slicer-provenance requirement — no blanket exemptions.
7. The lane-aware aggregation (classify_issues): a root-cause-labeled slice
   with no trailer is exempt (not flagged); a non-root-cause slice with no
   trailer is still flagged (PRD-decomposition slices keep the strict rule).

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
is_root_cause_exempt = _mod.is_root_cause_exempt
classify_issues = _mod.classify_issues


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


# ---------------------------------------------------------------------------
# Tests for is_root_cause_exempt() — slice #1067, the rule-#13 lane
# ---------------------------------------------------------------------------


class TestIsRootCauseExempt(unittest.TestCase):
    """Unit tests for the pure is_root_cause_exempt() function.

    Narrow-scope by design (issue #1067): ONLY the `root-cause` label grants
    exemption. No blanket exemptions for other labels or PRD-decomposition
    slices — those keep the strict Slicer-provenance requirement.
    """

    def test_root_cause_label_is_exempt(self):
        """A slice carrying the `root-cause` label is exempt."""
        labels = [{"name": "slice"}, {"name": "root-cause"}]
        self.assertTrue(is_root_cause_exempt(labels))

    def test_slice_only_label_not_exempt(self):
        """A slice with only the `slice` label (PRD-decomposition) is NOT exempt."""
        labels = [{"name": "slice"}]
        self.assertFalse(is_root_cause_exempt(labels))

    def test_captured_label_alone_not_exempt(self):
        """`captured` label alone does NOT grant exemption (narrow scope, no blanket)."""
        labels = [{"name": "slice"}, {"name": "captured"}]
        self.assertFalse(is_root_cause_exempt(labels))

    def test_empty_labels_not_exempt(self):
        """No labels at all → not exempt."""
        self.assertFalse(is_root_cause_exempt([]))

    def test_missing_labels_key_not_exempt(self):
        """Falsy/None labels value → not exempt (defensive)."""
        self.assertFalse(is_root_cause_exempt(None))

    def test_root_cause_label_case_and_shape_tolerant(self):
        """Label dicts with the exact 'root-cause' name (as GitHub returns) are matched."""
        labels = [{"name": "root-cause", "color": "B60205"}]
        self.assertTrue(is_root_cause_exempt(labels))


# ---------------------------------------------------------------------------
# Tests for classify_issues() — lane-aware aggregation (slice #1067)
# ---------------------------------------------------------------------------


class TestClassifyIssues(unittest.TestCase):
    """Tests for the lane-aware classification replacing the old flat check.

    classify_issues() returns a dict with three buckets:
      - slicer_ok: slicer-lane issues that DO carry the trailer
      - root_cause_exempt: root-cause-labeled issues (trailer or not — exempt)
      - missing: slicer-lane issues that lack the trailer (still flagged)
    """

    def test_root_cause_slice_no_trailer_is_exempt_not_missing(self):
        """The acceptance criterion: root-cause label + no trailer -> exempt, not flagged."""
        issues = [
            {
                "number": 1050,
                "body": "**Symptom:** ...\n**Root cause:** ...\n**Proposed:** ...",
                "labels": [{"name": "slice"}, {"name": "root-cause"}],
            }
        ]
        result = classify_issues(issues)
        self.assertEqual(result["missing"], [])
        self.assertIn(1050, result["root_cause_exempt"])

    def test_non_root_cause_slice_no_trailer_is_flagged(self):
        """A slicer-lane slice without the trailer and without root-cause label is flagged."""
        issues = [
            {
                "number": 806,
                "body": "## Parent\n\nPRD #800\n\nNo trailer here.",
                "labels": [{"name": "slice"}],
            }
        ]
        result = classify_issues(issues)
        self.assertEqual(result["missing"], [806])
        self.assertEqual(result["root_cause_exempt"], [])

    def test_slicer_lane_with_trailer_passes(self):
        """A slicer-lane slice WITH the trailer passes (slicer_ok bucket)."""
        issues = [
            {
                "number": 922,
                "body": "Slicer-provenance: slicer-critic-APPROVED decomposition of PRD #919 (round 1).",
                "labels": [{"name": "slice"}],
            }
        ]
        result = classify_issues(issues)
        self.assertEqual(result["missing"], [])
        self.assertIn(922, result["slicer_ok"])

    def test_root_cause_with_trailer_still_counted_exempt_lane(self):
        """A root-cause slice that DOES happen to carry the trailer is still in the
        root_cause_exempt bucket (label-driven classification, not trailer-driven)."""
        issues = [
            {
                "number": 1052,
                "body": "Slicer-provenance: some trailer anyway.",
                "labels": [{"name": "slice"}, {"name": "root-cause"}],
            }
        ]
        result = classify_issues(issues)
        self.assertEqual(result["missing"], [])
        self.assertIn(1052, result["root_cause_exempt"])

    def test_mixed_batch_honest_counts(self):
        """Mixed batch of both lanes reports honest per-lane counts."""
        issues = [
            {"number": 1, "body": "Slicer-provenance: ok.", "labels": [{"name": "slice"}]},
            {
                "number": 2,
                "body": "no trailer",
                "labels": [{"name": "slice"}, {"name": "root-cause"}],
            },
            {"number": 3, "body": "no trailer, no root-cause", "labels": [{"name": "slice"}]},
        ]
        result = classify_issues(issues)
        self.assertEqual(result["slicer_ok"], [1])
        self.assertEqual(result["root_cause_exempt"], [2])
        self.assertEqual(result["missing"], [3])

    def test_issue_with_no_labels_key_defaults_to_strict_lane(self):
        """An issue dict missing the 'labels' key entirely is treated as slicer-lane
        (strict) rather than silently exempted."""
        issues = [{"number": 5, "body": "no trailer"}]
        result = classify_issues(issues)
        self.assertEqual(result["missing"], [5])


if __name__ == "__main__":
    unittest.main()
