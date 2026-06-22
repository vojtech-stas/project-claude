"""
Tests for slice #997 — firing-tree mtime+size parse-cache (PRD #993 cr.6).

Verifies that transcript.get_session_firing() caches the firing-tree parse
keyed on (transcript_path, mtime, size):
  - warm hit (unchanged path+mtime+size) skips re-parse: returns in <1s
  - cache invalidates when mtime or size changes (recomputes)

Runner: stdlib unittest (NO top-level pytest imports).
  python -m unittest tests.test_firing_mtime_cache_997 -v
"""

import sys
import time
import tempfile
import threading
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
# Group 1: cache key correctness — (path, mtime, size) all matter
# ---------------------------------------------------------------------------

class TestFiringMtimeSizeCacheKey(unittest.TestCase):
    """transcript.get_session_firing() must cache by (path, mtime, size).

    Uses a real temp file so stat() returns genuine mtime + size values.
    Mocks build_firing_tree to count how many times the parse is invoked.
    """

    def setUp(self):
        _inject_dashboard()
        import transcript as _t
        self._t = _t
        # Reset the global cache before each test so tests are independent
        with _t._firing_cache_lock:
            _t._firing_cache["path"]   = None
            _t._firing_cache["mtime"]  = None
            _t._firing_cache["size"]   = None
            _t._firing_cache["result"] = None

    def _make_fake_result(self, tag="test"):
        return {
            "groups": {tag: []},
            "nested_groups": {},
            "research_other": [],
            "dispatch_count": 0,
            "source": tag,
        }

    def test_cold_call_invokes_build_firing_tree(self):
        """First call (cold cache) must invoke build_firing_tree exactly once."""
        t = self._t
        call_count = {"n": 0}
        fake_result = self._make_fake_result("cold")

        def _fake_build(path):
            call_count["n"] += 1
            return fake_result

        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False, mode='w') as f:
            f.write('{"type":"test"}\n')
            tmp_path = Path(f.name)

        try:
            with patch.object(t, "resolve_transcript", return_value=tmp_path), \
                 patch.object(t, "build_firing_tree", side_effect=_fake_build):
                result = t.get_session_firing()

            self.assertEqual(call_count["n"], 1, "Cold call must invoke build_firing_tree once")
            self.assertEqual(result["source"], "cold")
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_warm_call_skips_build_firing_tree(self):
        """Second call with unchanged transcript (same mtime+size) must NOT re-invoke parse."""
        t = self._t
        call_count = {"n": 0}
        fake_result = self._make_fake_result("warm")

        def _fake_build(path):
            call_count["n"] += 1
            return fake_result

        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False, mode='w') as f:
            f.write('{"type":"test"}\n')
            tmp_path = Path(f.name)

        try:
            with patch.object(t, "resolve_transcript", return_value=tmp_path), \
                 patch.object(t, "build_firing_tree", side_effect=_fake_build):
                # Cold call
                t.get_session_firing()
                # Warm call — transcript unchanged
                result = t.get_session_firing()

            self.assertEqual(call_count["n"], 1, "Warm call must NOT re-invoke build_firing_tree")
            self.assertEqual(result["source"], "warm")
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_warm_call_returns_fast(self):
        """Warm cache hit must return in <1s (cr.6)."""
        t = self._t
        fake_result = self._make_fake_result("fast")

        def _fake_build_slow(path):
            # Simulate a slow parse (2s) to prove warm hit skips it
            time.sleep(2.0)
            return fake_result

        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False, mode='w') as f:
            f.write('{"type":"test"}\n')
            tmp_path = Path(f.name)

        try:
            with patch.object(t, "resolve_transcript", return_value=tmp_path), \
                 patch.object(t, "build_firing_tree", side_effect=_fake_build_slow):
                # Cold call — slow (>2s)
                t.get_session_firing()
                # Warm call — must return in <1s (cache hit skips slow build)
                t0 = time.monotonic()
                result = t.get_session_firing()
                elapsed = time.monotonic() - t0

            self.assertLess(elapsed, 1.0,
                f"Warm cache hit must return in <1s, but took {elapsed:.3f}s")
            self.assertEqual(result["source"], "fast")
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_mtime_change_invalidates_cache(self):
        """Changing file mtime (but same size) must invalidate the cache (recompute)."""
        t = self._t
        call_count = {"n": 0}

        def _fake_build(path):
            call_count["n"] += 1
            return self._make_fake_result(f"call-{call_count['n']}")

        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False, mode='w') as f:
            f.write('{"type":"test"}\n')
            tmp_path = Path(f.name)

        try:
            with patch.object(t, "resolve_transcript", return_value=tmp_path), \
                 patch.object(t, "build_firing_tree", side_effect=_fake_build):
                # Cold call
                t.get_session_firing()
                self.assertEqual(call_count["n"], 1)

                # Simulate mtime change by updating the cache with a stale mtime
                with t._firing_cache_lock:
                    t._firing_cache["mtime"] = t._firing_cache["mtime"] - 100.0

                # Next call: mtime differs → cache invalidated → recompute
                t.get_session_firing()
                self.assertEqual(call_count["n"], 2, "mtime change must trigger recompute")
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_size_change_invalidates_cache(self):
        """Changing file size (e.g. content appended, same mtime) must invalidate cache."""
        t = self._t
        call_count = {"n": 0}

        def _fake_build(path):
            call_count["n"] += 1
            return self._make_fake_result(f"call-{call_count['n']}")

        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False, mode='w') as f:
            f.write('{"type":"test"}\n')
            tmp_path = Path(f.name)

        try:
            with patch.object(t, "resolve_transcript", return_value=tmp_path), \
                 patch.object(t, "build_firing_tree", side_effect=_fake_build):
                # Cold call
                t.get_session_firing()
                self.assertEqual(call_count["n"], 1)

                # Simulate size change (cache's stored size is wrong)
                with t._firing_cache_lock:
                    t._firing_cache["size"] = t._firing_cache["size"] + 9999

                # Next call: size differs → cache invalidated → recompute
                t.get_session_firing()
                self.assertEqual(call_count["n"], 2, "size change must trigger recompute")
        finally:
            tmp_path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Group 2: cache-key fields present in _firing_cache
# ---------------------------------------------------------------------------

class TestFiringCacheStructure(unittest.TestCase):
    """transcript._firing_cache must have path, mtime, size, result fields."""

    def setUp(self):
        _inject_dashboard()
        import transcript as _t
        self._t = _t

    def test_cache_has_size_field(self):
        """_firing_cache must include a 'size' key for (path, mtime, size) keying."""
        self.assertIn(
            "size", self._t._firing_cache,
            "_firing_cache must have 'size' key for (path, mtime, size) cache key"
        )

    def test_cache_has_lock(self):
        """_firing_cache_lock must exist and be a Lock-like object."""
        self.assertTrue(
            hasattr(self._t, "_firing_cache_lock"),
            "transcript module must expose _firing_cache_lock"
        )
        lock = self._t._firing_cache_lock
        self.assertTrue(
            hasattr(lock, "acquire") and hasattr(lock, "release"),
            "_firing_cache_lock must be a threading.Lock-like object"
        )

    def test_cache_has_all_required_keys(self):
        """_firing_cache must have path, mtime, size, result keys."""
        required = {"path", "mtime", "size", "result"}
        actual = set(self._t._firing_cache.keys())
        missing = required - actual
        self.assertEqual(
            missing, set(),
            f"_firing_cache is missing required keys: {missing}"
        )


# ---------------------------------------------------------------------------
# Group 3: no-transcript graceful degradation
# ---------------------------------------------------------------------------

class TestFiringCacheNoTranscript(unittest.TestCase):
    """get_session_firing() must return honest-empty when no transcript found."""

    def setUp(self):
        _inject_dashboard()
        import transcript as _t
        self._t = _t
        # Clear cache
        with _t._firing_cache_lock:
            _t._firing_cache["path"]   = None
            _t._firing_cache["mtime"]  = None
            _t._firing_cache["size"]   = None
            _t._firing_cache["result"] = None

    def test_no_transcript_returns_error_dict(self):
        """When resolve_transcript returns None, get_session_firing must return error dict."""
        t = self._t
        with patch.object(t, "resolve_transcript", return_value=None):
            result = t.get_session_firing()
        self.assertIsInstance(result, dict)
        self.assertIn("error", result)

    def test_no_transcript_no_raise(self):
        """get_session_firing must never raise, even with no transcript."""
        t = self._t
        with patch.object(t, "resolve_transcript", return_value=None):
            try:
                t.get_session_firing()
            except Exception as e:
                self.fail(f"get_session_firing() raised unexpectedly: {e}")


# ---------------------------------------------------------------------------
# Group 4: index.html non-blocking pattern (cr.7) — structural checks
# ---------------------------------------------------------------------------

class TestNonBlockingPatterns(unittest.TestCase):
    """index.html must have non-blocking AbortController pattern for Health/Arch/Firing."""

    def _html_src(self):
        return (REPO_ROOT / "dashboard" / "index.html").read_text(encoding="utf-8")

    def test_health_has_abort_controller(self):
        """loadHealth() must use AbortController for non-blocking fetch."""
        html = self._html_src()
        self.assertIn(
            "AbortController",
            html,
            "index.html must use AbortController (non-blocking pattern, slice #997)",
        )

    def test_health_has_computing_text(self):
        """Health panel must show 'computing' text when slow/aborted."""
        html = self._html_src()
        self.assertIn(
            "computing",
            html,
            "index.html must show 'computing…' state on slow/aborted health fetch",
        )

    def test_health_auto_refresh_timer(self):
        """Health tab must have an auto-refresh setInterval."""
        html = self._html_src()
        self.assertIn(
            "_healthRefreshTimer",
            html,
            "index.html must have _healthRefreshTimer for health auto-refresh",
        )

    def test_firing_abort_controller(self):
        """fetchFiring() must use AbortController for non-blocking fetch."""
        html = self._html_src()
        self.assertIn(
            "_firingController",
            html,
            "index.html must have _firingController (non-blocking Firing panel)",
        )

    def test_firing_auto_refresh(self):
        """Firing tab must have a 30s auto-refresh setInterval inside startFiring."""
        html = self._html_src()
        # The auto-refresh is inside startFiring function
        self.assertIn(
            "30000",
            html,
            "index.html must have 30s auto-refresh for Firing tab",
        )

    def test_architecture_abort_controller(self):
        """loadArchitecture() must use AbortController for non-blocking fetch."""
        html = self._html_src()
        self.assertIn(
            "_archController",
            html,
            "index.html must have _archController (non-blocking Architecture panel)",
        )


if __name__ == "__main__":
    unittest.main()
