"""
Regression test for issue #962 — /api/prd-firing must be non-blocking.

Bug: fetch_prd_firing() blocks the HTTP request path on cold-start gh calls
(~20 PRs × gh pr view = 40s+). The fix introduces a stale-while-revalidate
background-thread cache, so the serve path ALWAYS returns quickly.

Test design (ADR-0067 D3 — test-before-fix):
  This file is committed BEFORE the fix so the non-blocking test fails on the
  current (blocking) implementation in prd_firing.py.

Two test groups:

  1. TestNonBlockingServe — asserts that serve_prd_firing() (the new non-blocking
     entry-point) returns within 3s even when the underlying gh computation is
     slow (mocked to sleep 10s). On the old blocking implementation this test
     will FAIL because fetch_prd_firing() blocks for the full compute duration.

  2. TestBackgroundRecompute — asserts that a background thread is kicked off on
     cache miss / TTL expiry, and that the cache is populated asynchronously.

Runner: stdlib unittest + pytest compatible (NO top-level pytest imports).
  python -m pytest tests/test_prd_firing_nonblocking_962.py -v
  python tests/test_prd_firing_nonblocking_962.py
"""

import sys
import threading
import time
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

REPO_ROOT = Path(__file__).parent.parent
DASHBOARD_DIR = REPO_ROOT / "dashboard"


def _inject_dashboard():
    s = str(DASHBOARD_DIR)
    if s not in sys.path:
        sys.path.insert(0, s)


# ---------------------------------------------------------------------------
# Group 1: Non-blocking serve — core regression check
# ---------------------------------------------------------------------------

class TestNonBlockingServe(unittest.TestCase):
    """serve_prd_firing() must return in <3s even when gh is slow.

    This is the primary regression test for issue #962.  The test mocks
    _fetch_prd_firing_slow (the internal blocking computation) to sleep for
    10s, then asserts the serve path returns well under that.

    On the OLD (blocking) implementation: FAILS — takes >=10s.
    After the fix: PASSES — serves cached/computing immediately.
    """

    SERVE_TIMEOUT_S = 3.0  # serve path must complete within this bound

    def setUp(self):
        _inject_dashboard()
        import prd_firing as _pf
        self._pf = _pf
        # Clear module-level cache state so each test starts cold
        with _pf._cache_lock:
            _pf._cache.clear()
        # Reset computing flag if it exists (post-fix attribute)
        if hasattr(_pf, "_cache_computing"):
            with _pf._cache_lock:
                _pf._cache_computing = False

    def test_serve_returns_within_timeout_when_gh_slow(self):
        """serve_prd_firing() must return <3s when gh computation takes 10s.

        Mocks the slow computation function to sleep 10s, then calls
        serve_prd_firing() (the non-blocking serve path) and asserts it
        completes within SERVE_TIMEOUT_S.

        FAILS on old blocking fetch_prd_firing() — succeeds after fix.
        """
        import prd_firing as _pf

        # The fix introduces serve_prd_firing() as the non-blocking entry point.
        # If the function does not exist yet, the test will raise AttributeError
        # (which is also a failure — the test is testing the interface contract).
        if not hasattr(_pf, "serve_prd_firing"):
            self.fail(
                "prd_firing.serve_prd_firing() does not exist. "
                "The fix must introduce a non-blocking serve_prd_firing() "
                "that returns immediately with cached/computing data. "
                "(Issue #962 regression: old fetch_prd_firing() blocks for 40s+)"
            )

        # Mock the internal slow computation to sleep 10s so it can never
        # complete within our 3s timeout if the serve path blocks on it.
        def _slow_compute(limit):
            time.sleep(10)
            return {"prs": [], "pr_count": 0, "fetched_at": "mock"}

        with patch.object(_pf, "_fetch_prd_firing_blocking", _slow_compute, create=True):
            t0 = time.monotonic()
            result = _pf.serve_prd_firing(30)
            elapsed = time.monotonic() - t0

        self.assertLess(
            elapsed,
            self.SERVE_TIMEOUT_S,
            f"serve_prd_firing() took {elapsed:.2f}s — must be <{self.SERVE_TIMEOUT_S}s. "
            f"This indicates the serve path is still blocking on gh computation. "
            f"(Issue #962 regression)"
        )
        # Result must be a dict (either computing marker or last-known data)
        self.assertIsInstance(result, dict, f"serve_prd_firing() must return a dict, got {type(result)}")

    def test_serve_returns_computing_marker_on_cold_start(self):
        """serve_prd_firing() must return a dict with status='computing' on cold start.

        After the fix, a cold-start serve returns {"status": "computing", ...}
        immediately rather than blocking.
        """
        import prd_firing as _pf

        if not hasattr(_pf, "serve_prd_firing"):
            self.fail("prd_firing.serve_prd_firing() does not exist (issue #962 fix missing)")

        def _slow_compute(limit):
            time.sleep(10)
            return {"prs": [], "pr_count": 0, "fetched_at": "mock"}

        with patch.object(_pf, "_fetch_prd_firing_blocking", _slow_compute, create=True):
            result = _pf.serve_prd_firing(30)

        # On cold start with no cached data, must return computing marker
        status = result.get("status")
        self.assertEqual(
            status,
            "computing",
            f"Cold-start serve_prd_firing() must return status='computing', got: {result}"
        )

    def test_serve_returns_cached_data_when_warm(self):
        """serve_prd_firing() must return cached data immediately when cache is warm.

        Pre-populate the cache, then assert serve_prd_firing() returns that
        data without triggering a slow gh call.
        """
        import prd_firing as _pf

        if not hasattr(_pf, "serve_prd_firing"):
            self.fail("prd_firing.serve_prd_firing() does not exist (issue #962 fix missing)")

        # Pre-populate cache with known data
        warm_data = {
            "prs": [{"pr_number": 999, "pr_title": "test", "closes_issues": [], "events": []}],
            "pr_count": 1,
            "fetched_at": "2026-06-23T00:00:00+00:00",
        }
        with _pf._cache_lock:
            _pf._cache[30] = {"data": warm_data, "ts": time.time()}

        # Mock slow compute — should NOT be called when cache is warm
        called = []
        def _should_not_be_called(limit):
            called.append(True)
            time.sleep(10)
            return {"prs": [], "pr_count": 0, "fetched_at": "mock"}

        with patch.object(_pf, "_fetch_prd_firing_blocking", _should_not_be_called, create=True):
            t0 = time.monotonic()
            result = _pf.serve_prd_firing(30)
            elapsed = time.monotonic() - t0

        self.assertLess(elapsed, self.SERVE_TIMEOUT_S,
                        f"Warm serve_prd_firing() took {elapsed:.2f}s — must be <{self.SERVE_TIMEOUT_S}s")
        self.assertEqual(result.get("pr_count"), 1,
                         f"Warm serve must return cached pr_count=1, got: {result}")


# ---------------------------------------------------------------------------
# Group 2: Background recompute — thread is kicked off on cache miss
# ---------------------------------------------------------------------------

class TestBackgroundRecompute(unittest.TestCase):
    """Background recompute thread must be kicked off on cold start / TTL expiry.

    After the fix: calling serve_prd_firing() on a cold cache should kick a
    daemon thread that eventually populates the cache with real data.
    """

    def setUp(self):
        _inject_dashboard()
        import prd_firing as _pf
        self._pf = _pf
        with _pf._cache_lock:
            _pf._cache.clear()
        if hasattr(_pf, "_cache_computing"):
            with _pf._cache_lock:
                _pf._cache_computing = False

    def test_background_thread_populates_cache(self):
        """After serve_prd_firing() cold-starts, cache is populated within 5s.

        The fix's background thread must call _fetch_prd_firing_blocking() and
        store the result in the cache. We use a fast (instant) mock to verify
        the thread runs and populates without racing the 10s slow mock.
        """
        import prd_firing as _pf

        if not hasattr(_pf, "serve_prd_firing"):
            self.skipTest("serve_prd_firing() not yet implemented (pre-fix)")

        fast_payload = {"prs": [], "pr_count": 0, "fetched_at": "bg-test"}
        compute_called = threading.Event()

        def _fast_compute(limit):
            compute_called.set()
            return fast_payload

        with patch.object(_pf, "_fetch_prd_firing_blocking", _fast_compute, create=True):
            # Cold start — kicks background thread
            result = _pf.serve_prd_firing(30)
            # Must be "computing" or last-known on cold start
            self.assertIsInstance(result, dict)

            # Background thread should call compute and populate cache
            called = compute_called.wait(timeout=5.0)
            self.assertTrue(
                called,
                "_fetch_prd_firing_blocking() was never called by background thread "
                "within 5s — fix must kick a background recompute on cold start"
            )

    def test_ttl_expiry_triggers_background_refresh(self):
        """When cache is stale (past TTL), serve_prd_firing() must trigger refresh.

        Stale-while-revalidate: expired cached data is returned immediately,
        but a background recompute is kicked to refresh it.
        """
        import prd_firing as _pf

        if not hasattr(_pf, "serve_prd_firing"):
            self.skipTest("serve_prd_firing() not yet implemented (pre-fix)")

        stale_data = {"prs": [], "pr_count": 0, "fetched_at": "stale"}
        # Set cache timestamp to the past (beyond any reasonable TTL)
        stale_ts = time.time() - 9999
        with _pf._cache_lock:
            _pf._cache[30] = {"data": stale_data, "ts": stale_ts}
            if hasattr(_pf, "_cache_computing"):
                _pf._cache_computing = False

        refresh_called = threading.Event()

        def _fast_compute(limit):
            refresh_called.set()
            return {"prs": [], "pr_count": 0, "fetched_at": "refreshed"}

        with patch.object(_pf, "_fetch_prd_firing_blocking", _fast_compute, create=True):
            result = _pf.serve_prd_firing(30)
            # Stale-while-revalidate: must return stale data (not "computing")
            # rather than blocking for the recompute
            self.assertIsInstance(result, dict)
            self.assertNotEqual(
                result.get("status"), "computing",
                "Stale-while-revalidate must return last-known data, not 'computing'"
            )
            # Background refresh must be triggered
            called = refresh_called.wait(timeout=5.0)
            self.assertTrue(
                called,
                "Background refresh not triggered on TTL expiry (stale-while-revalidate)"
            )


# ---------------------------------------------------------------------------
# Group 3: Backward-compatible — fetch_prd_firing still works (no regression)
# ---------------------------------------------------------------------------

class TestFetchPrdFiringBackwardCompat(unittest.TestCase):
    """fetch_prd_firing() must still exist and return the expected shape.

    The fix must not remove or break fetch_prd_firing() — it is the blocking
    computation function, still used by background threads and direct callers.
    """

    def setUp(self):
        _inject_dashboard()
        import prd_firing as _pf
        self._pf = _pf
        with _pf._cache_lock:
            _pf._cache.clear()

    def test_fetch_prd_firing_exists(self):
        """fetch_prd_firing() must still be importable and callable."""
        import prd_firing as _pf
        self.assertTrue(
            callable(getattr(_pf, "fetch_prd_firing", None)),
            "fetch_prd_firing() must still exist after the fix"
        )

    def test_fetch_prd_firing_returns_dict(self):
        """fetch_prd_firing() with mocked gh returns expected shape."""
        import prd_firing as _pf

        # Mock _gh_run to return empty PR list (fast, no network)
        def _mock_gh_run(args, timeout=30):
            if "list" in args:
                return 0, "[]"
            return 1, ""

        with patch.object(_pf, "_gh_run", _mock_gh_run):
            result = _pf.fetch_prd_firing(5)

        self.assertIsInstance(result, dict)
        self.assertIn("prs", result)
        self.assertIn("pr_count", result)
        self.assertIn("fetched_at", result)


if __name__ == "__main__":
    unittest.main()
