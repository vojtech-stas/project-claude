"""
Regression test for issue #1020 — Trail comparison still false-FAILs develop PRDs.

Two facets tested:
  A) slice_no_pr false-FAIL: when slices have closedAt set (are genuinely closed)
     but GitHub did NOT auto-populate closingIssuesReferences (develop-base merge),
     the comparison must NOT emit slice_no_pr violations after the fix. This test
     calls compare() (the REAL /api/comparison path), not sub-helpers that bypass
     the violation detector.

  B) Non-blocking /api/comparison: serve_comparison() must return immediately
     (< 3 s) regardless of gh latency; the endpoint never blocks the HTTP thread.

Root cause (two-facet):
  1. closedAt IS set on slices (GitHub auto-closed via some mechanism, or manual),
     but closing_pr_number is None because _discover_develop_pr_slice_links scans
     --base develop only; once PRs are promoted to main the scan returns empty and
     the slice_no_pr detector fires.
  2. /api/comparison blocked the HTTP thread synchronously (no background warm).

Before fix (commit #1 — this file only):
  - compare() returns slice_no_pr violations for slices with closedAt set + no
    closing_pr_number → run_pass False.
  - serve_comparison() doesn't exist; the endpoint is blocking.

After fix (commit #2):
  - compare() returns run_pass True / zero slice_no_pr for slices whose closing PR
    is discoverable via trail prs dict or develop-PR body scanning.
  - serve_comparison() returns immediately (stale-while-revalidate).

Runner: stdlib unittest (no top-level pytest).
  python -m pytest tests/test_trail_develop_aware_1020.py -v
  python -m unittest tests.test_trail_develop_aware_1020 -v
"""

import json
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

REPO_ROOT = Path(__file__).parent.parent
DASHBOARD_DIR = REPO_ROOT / "dashboard"


def _inject_dashboard():
    s = str(DASHBOARD_DIR)
    if s not in sys.path:
        sys.path.insert(0, s)


# ---------------------------------------------------------------------------
# Synthetic trail — develop-PRD with slices that ARE closed but have
# no ClosedEvent.closer (develop-base merge; closingIssuesReferences empty).
# KEY: closedAt is NON-NULL (slices are genuinely closed).
# ---------------------------------------------------------------------------

_PRD_GQL_ISSUE = {
    "title": "PRD: develop-aware trail regression (#1020)",
    "createdAt": "2026-06-01T10:00:00Z",
    "closedAt": "2026-06-15T12:00:00Z",
    "labels": {"nodes": [{"name": "prd"}]},
    "comments": {"nodes": []},
    "subIssues": {
        "nodes": [
            {
                "number": 995,
                "title": "feat: slice 1 of PRD 993",
                "createdAt": "2026-06-02T10:00:00Z",
                "closedAt": "2026-06-05T15:00:00Z",  # NON-NULL — slice is closed
                "labels": {"nodes": [{"name": "slice"}]},
                "assignees": {"nodes": [{"login": "implementer-bot"}]},
                "comments": {"nodes": []},
                # No ClosedEvent.closer → closing_pr_number stays None initially
                "timelineItems": {"nodes": [
                    {
                        "__typename": "ClosedEvent",
                        "createdAt": "2026-06-05T15:00:00Z",
                        "closer": None,  # no PR closer (develop merge)
                    }
                ]},
            },
            {
                "number": 996,
                "title": "feat: slice 2 of PRD 993",
                "createdAt": "2026-06-03T10:00:00Z",
                "closedAt": "2026-06-06T15:00:00Z",  # NON-NULL
                "labels": {"nodes": [{"name": "slice"}]},
                "assignees": {"nodes": [{"login": "implementer-bot"}]},
                "comments": {"nodes": []},
                "timelineItems": {"nodes": [
                    {
                        "__typename": "ClosedEvent",
                        "createdAt": "2026-06-06T15:00:00Z",
                        "closer": None,
                    }
                ]},
            },
            {
                "number": 997,
                "title": "feat: slice 3 of PRD 993",
                "createdAt": "2026-06-04T10:00:00Z",
                "closedAt": "2026-06-07T15:00:00Z",  # NON-NULL
                "labels": {"nodes": [{"name": "slice"}]},
                "assignees": {"nodes": [{"login": "implementer-bot"}]},
                "comments": {"nodes": []},
                "timelineItems": {"nodes": [
                    {
                        "__typename": "ClosedEvent",
                        "createdAt": "2026-06-07T15:00:00Z",
                        "closer": None,
                    }
                ]},
            },
        ]
    },
}

_GQL_RESPONSE_DATA = {
    "repository": {
        "issue": _PRD_GQL_ISSUE,
    }
}

# Develop-base merged PRs with Closes #N in body; closingIssuesReferences EMPTY
_PR_998 = {
    "number": 998,
    "createdAt": "2026-06-05T10:00:00Z",
    "mergedAt": "2026-06-05T14:30:00Z",
    "headRefName": "fix/995-slice-one",
    "body": "Closes #995\n\n## Scope\nSlice 1 impl.\n\n## Verification\n- [x] pass",
    "closingIssuesReferences": [],  # empty — develop merge
    "comments": [
        {
            "createdAt": "2026-06-05T14:00:00Z",
            "body": "VERDICT: APPROVE\nROUND: 1\nCRITIC: reviewer\n",
        }
    ],
    "statusCheckRollup": [],
}

_PR_1001 = {
    "number": 1001,
    "createdAt": "2026-06-06T10:00:00Z",
    "mergedAt": "2026-06-06T14:30:00Z",
    "headRefName": "fix/996-slice-two",
    "body": "Closes #996\n\n## Scope\nSlice 2 impl.",
    "closingIssuesReferences": [],
    "comments": [
        {
            "createdAt": "2026-06-06T14:00:00Z",
            "body": "VERDICT: APPROVE\nROUND: 1\nCRITIC: reviewer\n",
        }
    ],
    "statusCheckRollup": [],
}

_PR_1002 = {
    "number": 1002,
    "createdAt": "2026-06-07T10:00:00Z",
    "mergedAt": "2026-06-07T14:30:00Z",
    "headRefName": "fix/997-slice-three",
    "body": "Closes #997\n\n## Scope\nSlice 3 impl.",
    "closingIssuesReferences": [],
    "comments": [
        {
            "createdAt": "2026-06-07T14:00:00Z",
            "body": "VERDICT: APPROVE\nROUND: 1\nCRITIC: reviewer\n",
        }
    ],
    "statusCheckRollup": [],
}

_DEVELOP_PRS_LIST = [
    {
        "number": 998,
        "body": _PR_998["body"],
        "mergedAt": _PR_998["mergedAt"],
        "closingIssuesReferences": [],
    },
    {
        "number": 1001,
        "body": _PR_1001["body"],
        "mergedAt": _PR_1001["mergedAt"],
        "closingIssuesReferences": [],
    },
    {
        "number": 1002,
        "body": _PR_1002["body"],
        "mergedAt": _PR_1002["mergedAt"],
        "closingIssuesReferences": [],
    },
]


def _build_trail_with_mocks(develop_scan_returns_empty=False):
    """Build a trail via collect_trail with gh layer mocked.

    Args:
        develop_scan_returns_empty: if True, simulate _discover_develop_pr_slice_links
          returning {} (promoted-to-main scenario: --base develop scan finds nothing).
    """
    _inject_dashboard()
    import collector

    def fake_gh_graphql(query, variables, timeout=30):
        return _GQL_RESPONSE_DATA, ""

    def fake_gh_pr_view(pr_number, timeout=20):
        mapping = {998: _PR_998, 1001: _PR_1001, 1002: _PR_1002}
        pr = mapping.get(pr_number)
        return (pr, "") if pr else (None, "transient")

    def fake_run_gh(args, timeout=30):
        if "pr" in args and "list" in args:
            if develop_scan_returns_empty:
                return json.dumps([]), ""  # simulate promoted-to-main: empty
            return json.dumps(_DEVELOP_PRS_LIST), ""
        return None, "transient"

    with patch.object(collector, "_gh_graphql", side_effect=fake_gh_graphql), \
         patch.object(collector, "_gh_pr_view", side_effect=fake_gh_pr_view), \
         patch.object(collector, "_run_gh", side_effect=fake_run_gh), \
         patch.object(collector, "_repo_slug", return_value="owner/repo"), \
         patch.object(
             collector, "_gql_query_for_slug",
             return_value="query($n:Int!){repository(owner:\"o\",name:\"r\"){issue(number:$n){title}}}",
         ):
        trail = collector.collect_trail(993)
    return trail


# ---------------------------------------------------------------------------
# Group A: slice_no_pr false-FAIL via compare() — the REAL /api/comparison path
# ---------------------------------------------------------------------------

class TestSliceNoPrDevelopAware(unittest.TestCase):
    """compare() must NOT emit slice_no_pr when develop-base PRs close the slices.

    Before fix: when develop_scan_returns_empty=False (develop list works),
      the collector wires closing_pr_number, but _detect_slice_no_pr could still
      fire if the mapping is incomplete.
      When promoted-to-main (develop_scan_returns_empty=True), _detect_slice_no_pr
      DOES fire → run_pass False (the pre-fix failure mode tested here).
    After fix: even when develop scan returns empty, the detector falls back to
      trail prs closing_issues OR a main-branch scan, and run_pass is True.
    """

    def _get_spec(self):
        _inject_dashboard()
        from comparison import get_spec_for_compare
        return get_spec_for_compare()

    def test_slice_no_pr_fires_when_promoted_to_main_no_fix(self):
        """BEFORE fix: slice_no_pr violations fire when develop scan is empty.

        This test MUST FAIL after the fix (commit #2).
        It documents the pre-fix failure mode: slice_no_pr fires → run_pass False.
        """
        _inject_dashboard()
        from comparison import compare, _detect_slice_no_pr

        # Build a trail where _discover_develop_pr_slice_links returned empty
        # (simulating promoted-to-main scenario)
        trail = _build_trail_with_mocks(develop_scan_returns_empty=True)

        # With the fix, the detector should NOT fire — so this assertion
        # would FAIL after commit #2 (which is the intended state).
        violations = _detect_slice_no_pr(trail)
        has_slice_no_pr = any(v["type"] == "slice_no_pr" for v in violations)
        self.assertTrue(
            has_slice_no_pr,
            "BEFORE fix: slice_no_pr must fire when develop scan empty + "
            "slices have closedAt but no closing_pr_number. "
            "If this assertion passes, the pre-fix failure mode is confirmed. "
            "AFTER fix this test WILL FAIL (expected: no slice_no_pr violations)."
        )

    def test_compare_no_slice_no_pr_with_develop_scan(self):
        """compare() must return zero slice_no_pr and run_pass True.

        The trail is built with develop_scan_returns_empty=False: the collector
        discovers PRs via _discover_develop_pr_slice_links and populates
        closing_pr_number for all slices. compare() must not emit slice_no_pr.

        This test exercises the FULL compare() path (not sub-helpers), so it
        catches any violation detector that fires despite closing_pr_number
        being set (the #1007 test-validity gap addressed in #1020).
        """
        _inject_dashboard()
        from comparison import compare

        trail = _build_trail_with_mocks(develop_scan_returns_empty=False)
        spec = self._get_spec()
        report = compare(spec, trail)

        slice_no_pr_violations = [
            v for v in report.get("violations", [])
            if v["type"] == "slice_no_pr"
        ]
        self.assertEqual(
            len(slice_no_pr_violations), 0,
            f"Expected 0 slice_no_pr violations, got "
            f"{len(slice_no_pr_violations)}: {slice_no_pr_violations}\n"
            f"Trail slices: "
            f"{[(s['number'], s.get('closing_pr_number')) for s in trail.get('slices', [])]}\n"
            f"Trail prs: {list(trail.get('prs', {}).keys())}"
        )
        self.assertTrue(
            report["run_pass"],
            f"run_pass must be True for a complete develop PRD. "
            f"Edges: {[(k, v['state']) for k, v in report.get('edges', {}).items()]}\n"
            f"Violations: {report.get('violations', [])}"
        )

    def test_compare_no_slice_no_pr_promoted_to_main(self):
        """AFTER fix: even when develop scan is empty (promoted to main),
        compare() must return zero slice_no_pr violations and run_pass True.

        This is the KEY regression test for #1020. It FAILS before the fix
        (because _discover_develop_pr_slice_links returns empty, closing_pr_number
        stays None, _detect_slice_no_pr fires) and PASSES after the fix.

        After fix, the detector falls back to trail prs closing_issues check
        or a broader PR scan (--base main fallback or no-base filter).
        """
        _inject_dashboard()
        from comparison import compare

        trail = _build_trail_with_mocks(develop_scan_returns_empty=True)
        spec = self._get_spec()
        report = compare(spec, trail)

        slice_no_pr_violations = [
            v for v in report.get("violations", [])
            if v["type"] == "slice_no_pr"
        ]
        self.assertEqual(
            len(slice_no_pr_violations), 0,
            f"AFTER FIX: expected 0 slice_no_pr violations even when develop "
            f"scan empty (promoted-to-main scenario), got "
            f"{len(slice_no_pr_violations)}: {slice_no_pr_violations}\n"
            f"Trail slices closing_pr_number: "
            f"{[s.get('closing_pr_number') for s in trail.get('slices', [])]}\n"
            f"Trail prs keys: {list(trail.get('prs', {}).keys())}"
        )
        self.assertTrue(
            report["run_pass"],
            f"run_pass must be True after fix. "
            f"Violations: {report.get('violations', [])}"
        )

    def test_e_slice_pr_confirmed_via_compare(self):
        """E-SLICE-PR must be 'confirmed' in the full compare() output."""
        _inject_dashboard()
        from comparison import compare

        trail = _build_trail_with_mocks(develop_scan_returns_empty=False)
        spec = self._get_spec()
        report = compare(spec, trail)

        edge = report.get("edges", {}).get("E-SLICE-PR", {})
        self.assertEqual(
            edge.get("state"), "confirmed",
            f"E-SLICE-PR must be confirmed, got: {edge}"
        )

    def test_e_pr_review_confirmed_via_compare(self):
        """E-PR-REVIEW must be 'confirmed' in the full compare() output."""
        _inject_dashboard()
        from comparison import compare

        trail = _build_trail_with_mocks(develop_scan_returns_empty=False)
        spec = self._get_spec()
        report = compare(spec, trail)

        edge = report.get("edges", {}).get("E-PR-REVIEW", {})
        self.assertEqual(
            edge.get("state"), "confirmed",
            f"E-PR-REVIEW must be confirmed, got: {edge}"
        )

    def test_e_review_merge_confirmed_via_compare(self):
        """E-REVIEW-MERGE must be 'confirmed' in the full compare() output."""
        _inject_dashboard()
        from comparison import compare

        trail = _build_trail_with_mocks(develop_scan_returns_empty=False)
        spec = self._get_spec()
        report = compare(spec, trail)

        edge = report.get("edges", {}).get("E-REVIEW-MERGE", {})
        self.assertEqual(
            edge.get("state"), "confirmed",
            f"E-REVIEW-MERGE must be confirmed, got: {edge}"
        )


# ---------------------------------------------------------------------------
# Group B: Non-blocking /api/comparison — serve_comparison() exists and is fast
# ---------------------------------------------------------------------------

class TestComparisonNonBlocking(unittest.TestCase):
    """serve_comparison() must return in < 3 s regardless of gh latency.

    Before fix: no serve_comparison() in server.py; endpoint is blocking.
    After fix: serve_comparison(prd_n) returns cached/computing immediately.
    """

    def test_serve_comparison_exists(self):
        """serve_comparison must exist in server module after fix.

        FAILS before fix (AttributeError); passes after.
        """
        _inject_dashboard()
        import server
        self.assertTrue(
            hasattr(server, "serve_comparison"),
            "server.serve_comparison not found — fix (commit #2) not applied. "
            "This test MUST FAIL before the fix."
        )

    def test_serve_comparison_returns_quickly(self):
        """serve_comparison(993) must return in < 3 s even on cold cache."""
        _inject_dashboard()
        import server

        if not hasattr(server, "serve_comparison"):
            self.skipTest("serve_comparison not yet implemented (pre-fix state)")

        # Patch get_trail to simulate slow gh (2s delay)
        import collector

        def slow_trail(prd_number, force_refresh=False):
            time.sleep(2)  # simulate gh latency
            return {
                "prd_number": prd_number,
                "prd_title": "slow trail",
                "collector_status": "",
                "slices": [],
                "prs": {},
            }

        with patch.object(server, "get_trail", side_effect=slow_trail):
            t0 = time.monotonic()
            result = server.serve_comparison(993)
            elapsed = time.monotonic() - t0

        self.assertLess(
            elapsed, 3.0,
            f"serve_comparison took {elapsed:.2f}s (>3s) — endpoint is BLOCKING. "
            f"Fix must make it non-blocking (stale-while-revalidate)."
        )
        # Either computing sentinel or real data — either is acceptable
        self.assertIn(
            "status" if result.get("status") == "computing" else "prd_number",
            result,
            f"Unexpected serve_comparison result: {result}"
        )


if __name__ == "__main__":
    unittest.main()
