"""
Regression tests for issue #1005 — Health board stuck Loading.

Two compounding defects:
  (a) /api/promotion runs check_release_ready() (full ci-checks.sh) synchronously
      on the HTTP request path, blocking for 40–300s.
  (b) loadHealth() in index.html uses Promise.all([/api/health, /api/promotion])
      so a hung /api/promotion blanks the entire Health board.

These tests FAIL on develop before the fix and PASS after.

NO top-level `import pytest` — stdlib unittest only.

Runner:
  python -m unittest tests.test_health_board_nonblocking_1005 -v
  python -m pytest tests/test_health_board_nonblocking_1005.py -v
"""

import re
import sys
import time
import threading
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

REPO_ROOT = Path(__file__).parent.parent
DASHBOARD_DIR = REPO_ROOT / "dashboard"

if str(DASHBOARD_DIR) not in sys.path:
    sys.path.insert(0, str(DASHBOARD_DIR))


# ---------------------------------------------------------------------------
# (a) Backend: _build_promotion_state() must NOT call check_release_ready()
#     inline on every request.  After the fix it serves held_reason from a
#     short-TTL background cache; the heavy gate is never on the request path.
# ---------------------------------------------------------------------------

class TestPromotionStateNonBlocking(unittest.TestCase):
    """Regression (a): _build_promotion_state() must return within a short
    budget even when check_release_ready() is extremely slow.

    Before the fix: _build_promotion_state() calls check_release_ready()
    inline → it will block for as long as the mock sleeps → test times out /
    takes >BUDGET.

    After the fix: check_release_ready() is NOT called on the request path
    (it runs in a background thread with a separate cache); the function
    returns within BUDGET with held_reason=None or a "computing" sentinel.
    """

    BUDGET = 2.0   # seconds — _build_promotion_state must return within this

    def _slow_check_release_ready(self):
        """Simulates check_release_ready() taking 60s (the ci-checks.sh wall time)."""
        time.sleep(60)
        return {"id": "RELEASE-READY", "result": "PASS", "verdict": "true", "detail": ""}

    def _slow_check_meta_tripwire(self):
        """Simulates check_meta_tripwire() also being slow."""
        time.sleep(30)
        return {"id": "META-TRIPWIRE", "result": "PASS", "detail": ""}

    def test_build_promotion_state_not_blocked_by_release_ready(self):
        """_build_promotion_state() returns within BUDGET even when
        check_release_ready() would block for 60s.

        Before fix: FAILS (blocks >60s).
        After fix:  PASSES (check_release_ready not called inline).
        """
        import health as _health_mod

        with patch.object(
            _health_mod, "check_release_ready",
            side_effect=self._slow_check_release_ready
        ):
            with patch.object(
                _health_mod, "check_meta_tripwire",
                side_effect=self._slow_check_meta_tripwire
            ):
                import server
                t0 = time.monotonic()
                result = server._build_promotion_state()
                elapsed = time.monotonic() - t0

        self.assertLess(
            elapsed, self.BUDGET,
            msg=(
                f"_build_promotion_state() blocked for {elapsed:.2f}s "
                f"(budget={self.BUDGET}s). check_release_ready() was called "
                f"inline on the request path — fix: cache it in a background thread."
            ),
        )
        # Payload schema must be intact regardless of held_reason source
        for key in ("develop_sha", "main_sha", "ahead", "behind",
                    "last_promotions", "held_reason"):
            self.assertIn(
                key, result,
                msg=f"_build_promotion_state() result missing key '{key}'",
            )

    def test_check_release_ready_not_called_inline(self):
        """check_release_ready() must NOT be called on the CALLING thread inside
        _build_promotion_state() — verifies the heavy gate is off the hot path.

        Before fix: called on main thread → calling_thread_ids includes main thread id.
        After fix:  called only in a daemon thread → calling_thread_ids excludes main
                    thread id, so no inline call recorded.
        """
        import health as _health_mod

        main_thread_id = threading.current_thread().ident
        calling_thread_ids = []

        def _spy_release_ready():
            calling_thread_ids.append(threading.current_thread().ident)
            return {"id": "RELEASE-READY", "result": "PASS", "verdict": "true", "detail": ""}

        with patch.object(_health_mod, "check_release_ready", side_effect=_spy_release_ready):
            import server
            server._build_promotion_state()

        # Allow background thread a moment to fire (it may already have).
        # We check WHICH thread called check_release_ready, not when.
        time.sleep(0.2)

        # The calling thread must NOT be the main thread.
        main_thread_calls = [tid for tid in calling_thread_ids if tid == main_thread_id]
        self.assertEqual(
            len(main_thread_calls), 0,
            msg=(
                f"check_release_ready() was called {len(main_thread_calls)} time(s) "
                f"on the calling (main) thread inside _build_promotion_state(). "
                f"After fix it must only run in a daemon background thread."
            ),
        )


# ---------------------------------------------------------------------------
# (b) Frontend: loadHealth() in index.html must NOT Promise.all the two fetches
#     together.  After the fix they are independent fetches with separate
#     try/catch so /api/promotion failure never blanks the health grids.
# ---------------------------------------------------------------------------

class TestLoadHealthDecoupled(unittest.TestCase):
    """Regression (b): index.html::loadHealth() must NOT couple /api/health
    and /api/promotion inside a single Promise.all.

    Before fix: the two fetches share one Promise.all — a hung /api/promotion
    blocks rendering of ALL health grids.

    After fix: they are fetched independently so only the promotion panel is
    affected by a slow/failed /api/promotion.
    """

    INDEX_HTML = REPO_ROOT / "dashboard" / "index.html"

    def _extract_load_health_body(self) -> str:
        """Extract the body of the loadHealth() function from index.html."""
        content = self.INDEX_HTML.read_text(encoding="utf-8")
        # Find loadHealth function — grab everything from its signature to the
        # closing brace (matched by counting { and }).
        m = re.search(r'async function loadHealth\(\)', content)
        if not m:
            self.fail("loadHealth() function not found in index.html")
        start = m.start()
        # Walk forward to find the opening brace
        brace_pos = content.index('{', start)
        depth = 0
        i = brace_pos
        while i < len(content):
            if content[i] == '{':
                depth += 1
            elif content[i] == '}':
                depth -= 1
                if depth == 0:
                    return content[brace_pos:i + 1]
            i += 1
        self.fail("Could not find closing brace of loadHealth() in index.html")

    def test_load_health_does_not_promise_all_health_and_promotion(self):
        """loadHealth() must NOT use Promise.all([/api/health, /api/promotion]).

        Before fix: Promise.all couples the two → FAILS this test.
        After fix:  they are separate fetches → PASSES.
        """
        body = self._extract_load_health_body()

        # Detect the coupled pattern: Promise.all that contains BOTH endpoints
        # in the same array literal.
        # Strategy: look for Promise.all(...) containing both 'api/health' and
        # 'api/promotion' inside its argument list.
        promise_all_blocks = re.findall(
            r'Promise\.all\s*\(\s*\[[\s\S]*?\]\s*\)',
            body,
        )
        coupled = [
            block for block in promise_all_blocks
            if "api/health" in block and "api/promotion" in block
        ]

        self.assertEqual(
            len(coupled), 0,
            msg=(
                "loadHealth() uses Promise.all([fetch('/api/health'), "
                "fetch('/api/promotion')]) — the two fetches are coupled. "
                "A hung /api/promotion will blank all health grids. "
                "Fix: separate the fetches into independent try/catch blocks."
            ),
        )

    def test_promotion_fetch_independent_of_health_render(self):
        """index.html::loadHealth() must have a separate fetch for /api/promotion
        that is NOT in the same Promise.all as /api/health.

        After fix: /api/promotion is fetched independently so only
        renderPromotionPanel() is affected by a slow response.
        """
        body = self._extract_load_health_body()

        # Both fetches must still be present (we're not removing /api/promotion)
        self.assertIn(
            "api/promotion", body,
            msg="loadHealth() must still fetch /api/promotion (just independently)",
        )
        self.assertIn(
            "api/health", body,
            msg="loadHealth() must still fetch /api/health",
        )

        # The two must NOT share a single Promise.all (already covered above,
        # but also assert that /api/health is fetched and its render happens
        # before or independently of /api/promotion).
        # Structural check: the phrase "await fetch('/api/health'" (or similar)
        # must appear at top-level in the function — not only nested inside a
        # Promise.all with /api/promotion.
        # Simpler guard: if they're still in a shared Promise.all, the
        # test_load_health_does_not_promise_all_health_and_promotion test above
        # already catches it.  This test just asserts both endpoints still exist.
        pass


if __name__ == "__main__":
    unittest.main()
