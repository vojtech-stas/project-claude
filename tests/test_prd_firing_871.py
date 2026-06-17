"""
Tests for slice #871 — per-PRD workflow-firing timeline from gh data.

Three test groups (ADR-0067 D2 test-first ordering — this file committed before impl):

  1. parse_firing_timeline: prd_firing.parse_pr_firing_timeline() correctly
     extracts implementer/critic/merge events from a synthetic gh-comments payload.

  2. endpoint_shape: /api/prd-firing module function returns expected dict shape
     (no live server bind — AST/import test only per isolation rules).

  3. server_route_present: server.py contains the /api/prd-firing elif route;
     index.html contains a fetch('/api/prd-firing') call (DEAD-ROUTES compliance).

Runner: stdlib unittest + pytest compatible.
  python -m pytest tests/test_prd_firing_871.py -v
"""

import ast
import json
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
DASHBOARD_DIR = REPO_ROOT / "dashboard"
SERVER_PY = DASHBOARD_DIR / "server.py"
INDEX_HTML = DASHBOARD_DIR / "index.html"


def _inject_dashboard():
    s = str(DASHBOARD_DIR)
    if s not in sys.path:
        sys.path.insert(0, s)


# ---------------------------------------------------------------------------
# Group 1: parse_firing_timeline — synthetic gh-comments payload parsing
# ---------------------------------------------------------------------------

class TestParseFiringTimeline(unittest.TestCase):
    """prd_firing.parse_pr_firing_timeline() must produce correct firing events.

    Uses a synthetic gh-comments list that mimics what `gh pr view --json comments`
    returns for a PR with:
      - implementer start (PR createdAt)
      - reviewer BLOCK R1 comment
      - reviewer BLOCK R2 comment
      - reviewer APPROVE R3 comment
      - merge (PR mergedAt)
    """

    # Synthetic PR object matching what gh CLI returns
    _SYNTHETIC_PR = {
        "number": 868,
        "title": "feat(foo): add bar baz",
        "createdAt": "2026-06-16T02:00:00Z",
        "mergedAt": "2026-06-16T03:30:00Z",
        "body": "Closes #867\n\n## Scope\ntest scope",
        "comments": [
            # Noise comment — no CRITIC trailer
            {
                "createdAt": "2026-06-16T02:10:00Z",
                "body": "Thanks for the PR!",
                "author": {"login": "vojtech-stas"},
            },
            # Reviewer BLOCK R1
            {
                "createdAt": "2026-06-16T02:49:00Z",
                "body": (
                    "Review round 1.\n\n"
                    "```\n"
                    "VERDICT: BLOCK\n"
                    "REASON: missing test\n"
                    "ROUND: 1\n"
                    "CRITIC: reviewer\n"
                    "```"
                ),
                "author": {"login": "claude-bot"},
            },
            # Reviewer BLOCK R2
            {
                "createdAt": "2026-06-16T03:15:00Z",
                "body": (
                    "Review round 2.\n\n"
                    "VERDICT: BLOCK\n"
                    "REASON: still missing test\n"
                    "ROUND: 2\n"
                    "CRITIC: reviewer\n"
                ),
                "author": {"login": "claude-bot"},
            },
            # Reviewer APPROVE R3
            {
                "createdAt": "2026-06-16T03:28:00Z",
                "body": (
                    "Review round 3.\n\n"
                    "VERDICT: APPROVE\n"
                    "REASON: tests added\n"
                    "ROUND: 3\n"
                    "CRITIC: reviewer\n"
                ),
                "author": {"login": "claude-bot"},
            },
        ],
    }

    def setUp(self):
        _inject_dashboard()
        import prd_firing as _pf
        self._pf = _pf

    def test_returns_dict(self):
        """parse_pr_firing_timeline must return a dict."""
        result = self._pf.parse_pr_firing_timeline(self._SYNTHETIC_PR)
        self.assertIsInstance(result, dict)

    def test_pr_number_present(self):
        """Result must include pr_number=868."""
        result = self._pf.parse_pr_firing_timeline(self._SYNTHETIC_PR)
        self.assertEqual(result.get("pr_number"), 868)

    def test_implementer_event_present(self):
        """First event must be 'implementer' at PR createdAt."""
        result = self._pf.parse_pr_firing_timeline(self._SYNTHETIC_PR)
        events = result.get("events", [])
        self.assertTrue(len(events) > 0, "events must be non-empty")
        first = events[0]
        self.assertEqual(first.get("agent"), "implementer")
        self.assertEqual(first.get("ts"), "2026-06-16T02:00:00Z")

    def test_merge_event_present(self):
        """Last event must be 'merge' at PR mergedAt."""
        result = self._pf.parse_pr_firing_timeline(self._SYNTHETIC_PR)
        events = result.get("events", [])
        self.assertTrue(len(events) > 0, "events must be non-empty")
        last = events[-1]
        self.assertEqual(last.get("agent"), "merge")
        self.assertEqual(last.get("ts"), "2026-06-16T03:30:00Z")

    def test_block_verdicts_extracted(self):
        """Two BLOCK verdicts from reviewer must appear in events."""
        result = self._pf.parse_pr_firing_timeline(self._SYNTHETIC_PR)
        events = result.get("events", [])
        blocks = [
            e for e in events
            if e.get("verdict") == "BLOCK"
        ]
        self.assertEqual(len(blocks), 2, f"Expected 2 BLOCKs, got {len(blocks)}: {blocks}")

    def test_approve_verdict_extracted(self):
        """One APPROVE verdict from reviewer must appear in events."""
        result = self._pf.parse_pr_firing_timeline(self._SYNTHETIC_PR)
        events = result.get("events", [])
        approves = [
            e for e in events
            if e.get("verdict") == "APPROVE"
        ]
        self.assertEqual(len(approves), 1, f"Expected 1 APPROVE, got {approves}")

    def test_round_numbers_extracted(self):
        """Round numbers R1, R2, R3 must be on the critic events."""
        result = self._pf.parse_pr_firing_timeline(self._SYNTHETIC_PR)
        events = result.get("events", [])
        rounds = sorted(
            e.get("round") for e in events
            if e.get("round") is not None
        )
        self.assertEqual(rounds, [1, 2, 3], f"Expected rounds [1,2,3], got {rounds}")

    def test_critic_name_extracted(self):
        """All critic events must have agent='reviewer'."""
        result = self._pf.parse_pr_firing_timeline(self._SYNTHETIC_PR)
        events = result.get("events", [])
        critic_events = [e for e in events if e.get("verdict") is not None]
        for ev in critic_events:
            self.assertEqual(
                ev.get("agent"), "reviewer",
                f"Critic event should have agent=reviewer: {ev}"
            )

    def test_noise_comment_skipped(self):
        """Comment without CRITIC trailer must not add a critic event."""
        result = self._pf.parse_pr_firing_timeline(self._SYNTHETIC_PR)
        events = result.get("events", [])
        # Noise comment is at 02:10 — between implementer (02:00) and first BLOCK (02:49)
        noise_events = [
            e for e in events
            if e.get("ts") == "2026-06-16T02:10:00Z"
        ]
        self.assertEqual(
            noise_events, [],
            f"Noise comment at 02:10 must not produce an event: {noise_events}"
        )

    def test_closes_annotation_extracted(self):
        """Result must include closes_issues list derived from 'Closes #N' in body."""
        result = self._pf.parse_pr_firing_timeline(self._SYNTHETIC_PR)
        closes = result.get("closes_issues", [])
        self.assertIn(867, closes, f"Expected 867 in closes_issues, got {closes}")

    def test_events_chronological(self):
        """Events must be sorted chronologically by ts."""
        result = self._pf.parse_pr_firing_timeline(self._SYNTHETIC_PR)
        events = result.get("events", [])
        tss = [e.get("ts", "") for e in events]
        self.assertEqual(tss, sorted(tss), f"Events not sorted by ts: {tss}")

    def test_open_pr_no_merge_event(self):
        """PR with mergedAt=None must have no merge event."""
        open_pr = dict(self._SYNTHETIC_PR)
        open_pr = {**self._SYNTHETIC_PR, "mergedAt": None, "comments": []}
        result = self._pf.parse_pr_firing_timeline(open_pr)
        events = result.get("events", [])
        merge_events = [e for e in events if e.get("agent") == "merge"]
        self.assertEqual(merge_events, [], f"Open PR must not have merge event: {merge_events}")


# ---------------------------------------------------------------------------
# Group 2: endpoint shape — module-level function (offline, no live bind)
# ---------------------------------------------------------------------------

class TestEndpointShape(unittest.TestCase):
    """prd_firing.build_prd_firing_payload() returns expected dict shape.

    Tests the module function directly without a live server (offline import).
    Uses a synthetic list of pre-parsed PR timelines to validate shape.
    """

    def setUp(self):
        _inject_dashboard()
        import prd_firing as _pf
        self._pf = _pf

    def _synthetic_timeline(self, pr_num=100):
        """Build a minimal pre-parsed timeline dict."""
        return {
            "pr_number": pr_num,
            "pr_title": f"feat(test): pr {pr_num}",
            "closes_issues": [pr_num + 1],
            "events": [
                {"agent": "implementer", "ts": "2026-06-16T01:00:00Z"},
                {"agent": "reviewer", "ts": "2026-06-16T01:30:00Z",
                 "verdict": "APPROVE", "round": 1},
                {"agent": "merge", "ts": "2026-06-16T01:45:00Z"},
            ],
        }

    def test_payload_has_prs_key(self):
        """build_prd_firing_payload must return a dict with 'prs' key."""
        timelines = [self._synthetic_timeline(200)]
        result = self._pf.build_prd_firing_payload(timelines)
        self.assertIn("prs", result, f"Missing 'prs' key: {result}")

    def test_prs_is_list(self):
        """prs must be a list."""
        timelines = [self._synthetic_timeline(201)]
        result = self._pf.build_prd_firing_payload(timelines)
        self.assertIsInstance(result["prs"], list)

    def test_payload_has_fetched_at(self):
        """build_prd_firing_payload must include fetched_at timestamp."""
        timelines = [self._synthetic_timeline(202)]
        result = self._pf.build_prd_firing_payload(timelines)
        self.assertIn("fetched_at", result, f"Missing 'fetched_at' key: {result}")

    def test_empty_timelines_returns_empty_prs(self):
        """Empty timelines list must produce prs=[]."""
        result = self._pf.build_prd_firing_payload([])
        self.assertEqual(result.get("prs"), [])

    def test_payload_has_pr_count(self):
        """build_prd_firing_payload must include pr_count."""
        timelines = [self._synthetic_timeline(203), self._synthetic_timeline(204)]
        result = self._pf.build_prd_firing_payload(timelines)
        self.assertIn("pr_count", result, f"Missing 'pr_count': {result}")
        self.assertEqual(result["pr_count"], 2)


# ---------------------------------------------------------------------------
# Group 3: server route + index.html wire-up (AST/grep — no live bind)
# ---------------------------------------------------------------------------

class TestServerRoutePresent(unittest.TestCase):
    """server.py must have /api/prd-firing route; index.html must fetch it."""

    def _server_src(self):
        return SERVER_PY.read_text(encoding="utf-8")

    def _index_src(self):
        return INDEX_HTML.read_text(encoding="utf-8")

    def test_server_has_prd_firing_route(self):
        """server.py must contain elif path == '/api/prd-firing' route."""
        src = self._server_src()
        self.assertIn(
            '"/api/prd-firing"',
            src,
            "server.py must contain an elif path == '/api/prd-firing' route",
        )

    def test_index_fetches_prd_firing(self):
        """index.html must contain a fetch('/api/prd-firing') call (DEAD-ROUTES)."""
        html = self._index_src()
        self.assertIn(
            "/api/prd-firing",
            html,
            "index.html must fetch /api/prd-firing (DEAD-ROUTES compliance)",
        )

    def test_server_imports_prd_firing(self):
        """server.py must import from prd_firing module."""
        src = self._server_src()
        self.assertIn(
            "prd_firing",
            src,
            "server.py must import prd_firing module",
        )

    def test_server_py_parses(self):
        """server.py must be valid Python after adding the new route."""
        src = self._server_src()
        try:
            ast.parse(src)
        except SyntaxError as e:
            self.fail(f"server.py syntax error: {e}")

    def test_dead_routes_pass(self):
        """DEAD-ROUTES health check must return PASS (no dead routes)."""
        import subprocess
        script = f"""
import sys
sys.path.insert(0, r'{DASHBOARD_DIR}')
from health import check_dead_routes
import json
result = check_dead_routes()
print(json.dumps(result))
"""
        r = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True, text=True, timeout=30,
            cwd=str(DASHBOARD_DIR),
        )
        self.assertEqual(
            r.returncode, 0,
            f"check_dead_routes() subprocess failed:\n{r.stderr[:400]}"
        )
        data = json.loads(r.stdout.strip())
        dead = data.get("dead_routes", [])
        self.assertEqual(
            [],
            dead,
            f"DEAD-ROUTES: dead routes remaining: {dead}\ndetail: {data.get('detail')}",
        )


if __name__ == "__main__":
    unittest.main()
