"""
Regression test for issue #1061 — /api/session-firing must be non-blocking.

Bug: get_session_firing() blocks the HTTP request path on cold-parse of the
transcript (build_firing_tree() on an ~85k-event transcript + gh resolution
can take 30s+). The #997 mtime+size parse-cache only helps WARM loads —
nothing warms the cache on cold start, unlike /api/prd-firing which #962 gave
a background-warm daemon + {status:"computing"} cold sentinel.

Fix: serve_session_firing() — a stale-while-revalidate wrapper mirroring
prd_firing.serve_prd_firing() (issue #962): cold -> return {"status":
"computing"} immediately + kick ONE daemon thread to build the tree; warm ->
cached tree; transcript mtime/size change -> serve stale + refresh in
background.

Test design (ADR-0067 D3 — test-before-fix):
  This file is committed BEFORE the fix so the non-blocking tests fail on the
  current (blocking) implementation in transcript.py (no serve_session_firing
  wrapper exists — get_session_firing() is called directly and blocks).

Runner: stdlib unittest + pytest compatible (NO top-level pytest imports).
  python -m pytest tests/test_session_firing_warm_1061.py -v
  python tests/test_session_firing_warm_1061.py
"""

import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).parent.parent
DASHBOARD_DIR = REPO_ROOT / "dashboard"


def _inject_dashboard():
    s = str(DASHBOARD_DIR)
    if s not in sys.path:
        sys.path.insert(0, s)


def _make_tmp_transcript():
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False, mode="w") as f:
        f.write('{"type":"test"}\n')
        return Path(f.name)


def _reset_firing_cache(t):
    with t._firing_cache_lock:
        t._firing_cache["path"] = None
        t._firing_cache["mtime"] = None
        t._firing_cache["size"] = None
        t._firing_cache["result"] = None
    if hasattr(t, "_firing_cache_computing"):
        with t._firing_cache_lock:
            t._firing_cache_computing = False


# ---------------------------------------------------------------------------
# Group 1: Non-blocking serve — core regression check (#1061)
# ---------------------------------------------------------------------------

class TestNonBlockingServe(unittest.TestCase):
    """serve_session_firing() must return in <1s even when the tree build is slow.

    On the OLD (blocking) implementation there is no serve_session_firing()
    wrapper — the route calls get_session_firing() directly, which blocks on
    build_firing_tree() for the full duration. This test mocks
    build_firing_tree() to sleep 3s and asserts the serve path returns well
    under that.
    """

    SERVE_TIMEOUT_S = 1.0

    def setUp(self):
        _inject_dashboard()
        import transcript as _t
        self._t = _t
        _reset_firing_cache(_t)
        self._tmp_path = _make_tmp_transcript()

    def tearDown(self):
        self._tmp_path.unlink(missing_ok=True)

    def test_serve_returns_within_timeout_when_build_slow(self):
        """serve_session_firing() must return <1s when build_firing_tree() sleeps 3s.

        FAILS on old blocking get_session_firing() direct-call path — succeeds
        after the fix introduces the non-blocking serve wrapper.
        """
        t = self._t

        if not hasattr(t, "serve_session_firing"):
            self.fail(
                "transcript.serve_session_firing() does not exist. "
                "The fix must introduce a non-blocking serve_session_firing() "
                "that returns immediately with cached/computing data. "
                "(Issue #1061 regression: get_session_firing() blocks 30s+ cold)"
            )

        def _slow_build(path):
            time.sleep(3)
            return {
                "groups": {}, "nested_groups": {}, "research_other": [],
                "dispatch_count": 0, "source": str(path), "error": None,
            }

        with patch.object(t, "resolve_transcript", return_value=self._tmp_path), \
             patch.object(t, "build_firing_tree", side_effect=_slow_build):
            t0 = time.monotonic()
            result = t.serve_session_firing()
            elapsed = time.monotonic() - t0

        self.assertLess(
            elapsed, self.SERVE_TIMEOUT_S,
            f"serve_session_firing() took {elapsed:.2f}s — must be <{self.SERVE_TIMEOUT_S}s. "
            f"This indicates the serve path is still blocking on the tree build. "
            f"(Issue #1061 regression)"
        )
        self.assertIsInstance(result, dict)

    def test_serve_returns_computing_marker_on_cold_start(self):
        """Cold-start serve_session_firing() must return status='computing'."""
        t = self._t

        if not hasattr(t, "serve_session_firing"):
            self.fail("transcript.serve_session_firing() does not exist (#1061 fix missing)")

        def _slow_build(path):
            time.sleep(3)
            return {
                "groups": {}, "nested_groups": {}, "research_other": [],
                "dispatch_count": 0, "source": str(path), "error": None,
            }

        with patch.object(t, "resolve_transcript", return_value=self._tmp_path), \
             patch.object(t, "build_firing_tree", side_effect=_slow_build):
            result = t.serve_session_firing()

        self.assertEqual(
            result.get("status"), "computing",
            f"Cold-start serve_session_firing() must return status='computing', got: {result}"
        )


# ---------------------------------------------------------------------------
# Group 2: Second call after daemon completes returns the built tree (#1061)
# ---------------------------------------------------------------------------

class TestBackgroundCompletion(unittest.TestCase):
    """After the daemon finishes, the next serve call must return the built tree."""

    def setUp(self):
        _inject_dashboard()
        import transcript as _t
        self._t = _t
        _reset_firing_cache(_t)
        self._tmp_path = _make_tmp_transcript()

    def tearDown(self):
        self._tmp_path.unlink(missing_ok=True)

    def test_second_call_after_daemon_returns_built_tree(self):
        """First (cold) call returns computing; after the daemon completes, the
        next call must return the actual built tree — not another computing marker.
        """
        t = self._t

        if not hasattr(t, "serve_session_firing"):
            self.skipTest("serve_session_firing() not yet implemented (pre-fix)")

        built_event = threading.Event()
        fake_tree = {
            "groups": {"p": []}, "nested_groups": {}, "research_other": [],
            "dispatch_count": 7, "source": str(self._tmp_path), "error": None,
        }

        def _fast_build(path):
            built_event.set()
            return fake_tree

        with patch.object(t, "resolve_transcript", return_value=self._tmp_path), \
             patch.object(t, "build_firing_tree", side_effect=_fast_build):
            first = t.serve_session_firing()
            self.assertEqual(first.get("status"), "computing")

            # Wait for the daemon thread to finish building
            self.assertTrue(
                built_event.wait(timeout=5.0),
                "build_firing_tree() was never invoked by the background daemon "
                "within 5s — fix must kick a background build on cold start"
            )
            # Give the daemon a brief moment to store the result under lock
            deadline = time.monotonic() + 3.0
            second = None
            while time.monotonic() < deadline:
                second = t.serve_session_firing()
                if second.get("status") != "computing":
                    break
                time.sleep(0.05)

        self.assertIsNotNone(second)
        self.assertNotEqual(
            second.get("status"), "computing",
            "Second call after daemon completion must return the built tree, "
            "not another computing marker"
        )
        self.assertEqual(second.get("dispatch_count"), 7)


# ---------------------------------------------------------------------------
# Group 3: mtime-unchanged repeat serves cache without rebuilding (#1061)
# ---------------------------------------------------------------------------

class TestWarmServeSkipsRebuild(unittest.TestCase):
    """Once warm, repeat serve_session_firing() calls must not rebuild the tree."""

    def setUp(self):
        _inject_dashboard()
        import transcript as _t
        self._t = _t
        _reset_firing_cache(_t)
        self._tmp_path = _make_tmp_transcript()

    def tearDown(self):
        self._tmp_path.unlink(missing_ok=True)

    def test_warm_repeat_does_not_rebuild(self):
        t = self._t

        if not hasattr(t, "serve_session_firing"):
            self.skipTest("serve_session_firing() not yet implemented (pre-fix)")

        build_count = {"n": 0}
        built_event = threading.Event()

        def _counting_build(path):
            build_count["n"] += 1
            built_event.set()
            return {
                "groups": {}, "nested_groups": {}, "research_other": [],
                "dispatch_count": build_count["n"], "source": str(path), "error": None,
            }

        with patch.object(t, "resolve_transcript", return_value=self._tmp_path), \
             patch.object(t, "build_firing_tree", side_effect=_counting_build):
            # Cold call — kicks background build
            t.serve_session_firing()
            self.assertTrue(built_event.wait(timeout=5.0), "background build never ran")

            # Wait until the cache reflects the completed build (status != computing)
            deadline = time.monotonic() + 3.0
            warm = None
            while time.monotonic() < deadline:
                warm = t.serve_session_firing()
                if warm.get("status") != "computing":
                    break
                time.sleep(0.05)

            # Repeat calls with unchanged mtime/size must NOT trigger another build
            t.serve_session_firing()
            t.serve_session_firing()

        self.assertEqual(
            build_count["n"], 1,
            f"mtime-unchanged repeat calls must serve cache without rebuilding, "
            f"but build_firing_tree() was called {build_count['n']} times"
        )


if __name__ == "__main__":
    unittest.main()
