"""
Regression tests for issue #1007 — two-tier PR/PRD correlation.

Root cause: when PRs are merged to 'develop' (not the default branch),
GitHub does NOT auto-close referenced issues, so:
  - slice issues have no ClosedEvent.closer → closing_pr_number is None
  - closingIssuesReferences on the PR is empty

These tests FAIL on develop before the fix (commit #1) and PASS after (commit #2).

Trimmed by PRD #1214 slice #1218 (module deletion): Groups B and C exercised
prd_firing.py exclusively and were deleted with their subject. Only Group A
survives — it exercises collector.py/comparison.py (kept modules).

  A) Trail comparison: a PRD with slices closed by develop-base PRs resolves
     E-SLICE-PR / E-PR-REVIEW / E-REVIEW-MERGE as 'confirmed', not 'missing'.

Test strategy: mock the gh layer inside collector so no live network calls
are made; inject synthetic data that mimics the develop-delivery scenario
(closingIssuesReferences EMPTY, Closes #N in PR body).

Runner: stdlib unittest (NO top-level pytest import).
  python -m pytest tests/test_twotier_correlation_1007.py -v
  python -m unittest tests.test_twotier_correlation_1007 -v
"""

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).parent.parent
DASHBOARD_DIR = REPO_ROOT / "dashboard"


def _inject_dashboard():
    s = str(DASHBOARD_DIR)
    if s not in sys.path:
        sys.path.insert(0, s)


# ---------------------------------------------------------------------------
# Shared synthetic data — develop-delivery scenario
# ---------------------------------------------------------------------------

# PRD issue #993 (prd-labeled) with three sub-issue slices
_PRD_GQL_ISSUE = {
    "title": "PRD: two-tier correlation test fixture",
    "createdAt": "2026-06-01T10:00:00Z",
    "closedAt": "2026-06-10T15:00:00Z",
    "labels": {"nodes": [{"name": "prd"}]},
    "comments": {"nodes": []},
    "subIssues": {
        "nodes": [
            # Slice #995 — NOT closed by GitHub (develop merge), no ClosedEvent
            {
                "number": 995,
                "title": "feat: slice 1 of PRD 993",
                "createdAt": "2026-06-02T10:00:00Z",
                "closedAt": None,       # GitHub did NOT close it (develop merge)
                "labels": {"nodes": [{"name": "slice"}]},
                "assignees": {"nodes": [{"login": "implementer-bot"}]},
                "comments": {"nodes": []},
                "timelineItems": {"nodes": []},  # No ClosedEvent.closer
            },
            # Slice #996 — also NOT closed by GitHub
            {
                "number": 996,
                "title": "feat: slice 2 of PRD 993",
                "createdAt": "2026-06-03T10:00:00Z",
                "closedAt": None,
                "labels": {"nodes": [{"name": "slice"}]},
                "assignees": {"nodes": [{"login": "implementer-bot"}]},
                "comments": {"nodes": []},
                "timelineItems": {"nodes": []},
            },
            # Slice #997 — also NOT closed by GitHub
            {
                "number": 997,
                "title": "feat: slice 3 of PRD 993",
                "createdAt": "2026-06-04T10:00:00Z",
                "closedAt": None,
                "labels": {"nodes": [{"name": "slice"}]},
                "assignees": {"nodes": [{"login": "implementer-bot"}]},
                "comments": {"nodes": []},
                "timelineItems": {"nodes": []},
            },
        ]
    },
}

# PRs that close the slices — merged to develop, closingIssuesReferences EMPTY
_PR_998 = {
    "number": 998,
    "title": "feat(slice1): implement slice 1 (#995)",
    "createdAt": "2026-06-05T10:00:00Z",
    "mergedAt": "2026-06-05T15:00:00Z",
    "headRefName": "feat/995-slice-one",
    "body": (
        "Closes #995\n\n## Scope\nImplements slice 1.\n\n"
        "## Verification\n- [x] tests pass\n\n"
        "RESULT: SUCCESS\n"
    ),
    # EMPTY — GitHub doesn't populate for develop-base merges
    "closingIssuesReferences": [],
    "comments": [
        {
            "createdAt": "2026-06-05T14:30:00Z",
            "body": (
                "```\nVERDICT: APPROVE\nREASON: LGTM\nROUND: 1\nCRITIC: reviewer\n```"
            ),
        }
    ],
    "statusCheckRollup": [],
}

_PR_1001 = {
    "number": 1001,
    "title": "feat(slice2): implement slice 2 (#996)",
    "createdAt": "2026-06-06T10:00:00Z",
    "mergedAt": "2026-06-06T15:00:00Z",
    "headRefName": "feat/996-slice-two",
    "body": "Closes #996\n\n## Scope\nSlice 2.",
    "closingIssuesReferences": [],
    "comments": [
        {
            "createdAt": "2026-06-06T14:30:00Z",
            "body": "VERDICT: APPROVE\nROUND: 1\nCRITIC: reviewer\n",
        }
    ],
    "statusCheckRollup": [],
}

_PR_1002 = {
    "number": 1002,
    "title": "feat(slice3): implement slice 3 (#997)",
    "createdAt": "2026-06-07T10:00:00Z",
    "mergedAt": "2026-06-07T15:00:00Z",
    "headRefName": "feat/997-slice-three",
    "body": "Closes #997\n\n## Scope\nSlice 3.",
    "closingIssuesReferences": [],
    "comments": [
        {
            "createdAt": "2026-06-07T14:30:00Z",
            "body": "VERDICT: APPROVE\nROUND: 1\nCRITIC: reviewer\n",
        }
    ],
    "statusCheckRollup": [],
}

# GQL response wrapping the PRD issue
_GQL_RESPONSE_DATA = {
    "repository": {
        "issue": _PRD_GQL_ISSUE,
    }
}

# gh pr list --base develop --state merged response (JSON)
_DEVELOP_PRS_LIST = [
    {
        "number": 998,
        "title": _PR_998["title"],
        "body": _PR_998["body"],
        "mergedAt": _PR_998["mergedAt"],
        "closingIssuesReferences": [],
    },
    {
        "number": 1001,
        "title": _PR_1001["title"],
        "body": _PR_1001["body"],
        "mergedAt": _PR_1001["mergedAt"],
        "closingIssuesReferences": [],
    },
    {
        "number": 1002,
        "title": _PR_1002["title"],
        "body": _PR_1002["body"],
        "mergedAt": _PR_1002["mergedAt"],
        "closingIssuesReferences": [],
    },
]

# ---------------------------------------------------------------------------
# Group A: Trail comparison evaluators — develop-base PRD
# ---------------------------------------------------------------------------

class TestTrailComparisonDevelopBase(unittest.TestCase):
    """E-SLICE-PR / E-PR-REVIEW / E-REVIEW-MERGE must resolve 'confirmed'
    for a PRD whose slices were closed by develop-base PRs.

    Before fix: closing_pr_number is None for every slice → prs={} →
      E-SLICE-PR = 'missing', E-PR-REVIEW = 'missing', E-REVIEW-MERGE = 'missing'.
    After fix: _discover_develop_pr_slice_links populates closing_pr_number →
      prs are fetched → evaluators return 'confirmed'.
    """

    def _build_trail(self):
        """Build a trail via collect_trail with gh layer mocked."""
        _inject_dashboard()
        import collector

        def fake_gh_graphql(query, variables, timeout=30):
            return _GQL_RESPONSE_DATA, ""

        def fake_gh_pr_view(pr_number, timeout=20):
            mapping = {998: _PR_998, 1001: _PR_1001, 1002: _PR_1002}
            pr = mapping.get(pr_number)
            if pr:
                return pr, ""
            return None, "transient"

        def fake_run_gh(args, timeout=30):
            # Simulate `gh pr list --base develop --state merged --json ...`
            if "pr" in args and "list" in args and "develop" in args:
                return json.dumps(_DEVELOP_PRS_LIST), ""
            return None, "transient"

        with patch.object(collector, "_gh_graphql", side_effect=fake_gh_graphql), \
             patch.object(collector, "_gh_pr_view", side_effect=fake_gh_pr_view), \
             patch.object(collector, "_run_gh", side_effect=fake_run_gh), \
             patch.object(collector, "_repo_slug", return_value="owner/repo"), \
             patch.object(collector, "_gql_query_for_slug",
                          return_value="query($n:Int!){repository(owner:\"o\",name:\"r\"){issue(number:$n){title}}}"):
            trail = collector.collect_trail(993)
        return trail

    def test_e_slice_pr_confirmed(self):
        """E-SLICE-PR must be 'confirmed' — slices link to develop-base PRs."""
        _inject_dashboard()
        import comparison
        trail = self._build_trail()
        state, detail = comparison._eval_slice_closed_by_pr(trail)
        self.assertEqual(
            state, "confirmed",
            f"E-SLICE-PR expected 'confirmed', got '{state}': {detail}\n"
            f"Trail slices: {[s.get('closing_pr_number') for s in trail.get('slices', [])]}\n"
            f"Trail prs keys: {list(trail.get('prs', {}).keys())}"
        )

    def test_e_pr_review_confirmed(self):
        """E-PR-REVIEW must be 'confirmed' — PRs have APPROVE verdicts."""
        _inject_dashboard()
        import comparison
        trail = self._build_trail()
        state, detail = comparison._eval_pr_has_verdict(trail)
        self.assertEqual(
            state, "confirmed",
            f"E-PR-REVIEW expected 'confirmed', got '{state}': {detail}\n"
            f"Trail prs keys: {list(trail.get('prs', {}).keys())}"
        )

    def test_e_review_merge_confirmed(self):
        """E-REVIEW-MERGE must be 'confirmed' — PRs merged after APPROVE."""
        _inject_dashboard()
        import comparison
        trail = self._build_trail()
        state, detail = comparison._eval_reviewed_before_merge(trail)
        self.assertEqual(
            state, "confirmed",
            f"E-REVIEW-MERGE expected 'confirmed', got '{state}': {detail}"
        )

    def test_trail_prs_populated(self):
        """Trail must have 3 PRs (one per slice) after develop-base discovery."""
        trail = self._build_trail()
        prs = trail.get("prs", {})
        self.assertEqual(
            len(prs), 3,
            f"Expected 3 PRs in trail, got {len(prs)}: {list(prs.keys())}"
        )

    def test_slices_have_closing_pr_number(self):
        """Each slice must have closing_pr_number populated via develop-PR lookup."""
        trail = self._build_trail()
        slices = trail.get("slices", [])
        self.assertEqual(len(slices), 3, f"Expected 3 slices, got {len(slices)}")
        for s in slices:
            self.assertIsNotNone(
                s.get("closing_pr_number"),
                f"Slice #{s.get('number')} missing closing_pr_number"
            )


if __name__ == "__main__":
    unittest.main()
