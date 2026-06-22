"""
Tests for PRD #993 slice #995 — gh_cache helper + /api/status non-blocking path.

NO top-level `import pytest` — stdlib unittest only.

Test groups:
  cr.1: gh_fetch returns within timeout+ε when gh is slow; result labeled stale/computing.
  cr.2: /api/status build path returns quickly when gh is slow; affected field degraded.
  cr.8: cached values carry fetched_at+source; data fields unchanged under normal gh.

Runner:
  python -m unittest tests.test_gh_cache_993 -v
  python -m pytest tests/test_gh_cache_993.py -v
"""

import json
import sys
import time
import threading
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

REPO_ROOT = Path(__file__).parent.parent
DASHBOARD_DIR = REPO_ROOT / "dashboard"

# Ensure dashboard/ is on sys.path so gh_cache + workitems are importable.
if str(DASHBOARD_DIR) not in sys.path:
    sys.path.insert(0, str(DASHBOARD_DIR))

import gh_cache  # noqa: E402 — needs sys.path set above

# Save a reference to the REAL subprocess.run before any monkeypatching occurs.
# Used by _slow_subprocess_run to pass non-gh commands through normally.
import subprocess as _subprocess_module
_real_subprocess_run = _subprocess_module.run


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _slow_subprocess_run(args, *, capture_output=False, text=False, encoding=None,
                          timeout=None, **kwargs):
    """Simulate a slow gh process; pass-through for git/other commands.

    Only slows down `gh` commands — git and other subprocess calls run normally
    (via the real subprocess.run) so that _build_status()'s git HEAD lookups
    and other non-gh subprocess calls are unaffected.

    NOTE: we must call the REAL subprocess.run for non-gh calls.  We access it
    via the saved reference _real_subprocess_run to avoid infinite recursion.
    """
    import subprocess as _sp
    # Only intercept gh commands
    if not args or args[0] != "gh":
        return _real_subprocess_run(
            args,
            capture_output=capture_output,
            text=text,
            encoding=encoding,
            timeout=timeout,
            **kwargs,
        )
    # Simulate a slow gh: sleep until the timeout fires, then raise TimeoutExpired
    if timeout is not None:
        time.sleep(timeout + 0.05)
        raise _sp.TimeoutExpired(cmd=args, timeout=timeout)
    # No timeout specified — sleep a long time (shouldn't happen in our code)
    time.sleep(30)
    return MagicMock(returncode=0, stdout="[]", stderr="")


def _fast_subprocess_run(args, *, capture_output=False, text=False, encoding=None,
                          timeout=None, **kwargs):
    """Simulate a gh process that returns instantly with valid JSON.

    Passes non-gh commands through to the real subprocess.run so that git
    calls and other subprocess operations are unaffected.
    """
    import subprocess as _sp
    if not args or args[0] != "gh":
        return _real_subprocess_run(
            args,
            capture_output=capture_output,
            text=text,
            encoding=encoding,
            timeout=timeout,
            **kwargs,
        )
    mock = MagicMock()
    mock.returncode = 0
    mock.stdout = '[{"number":1,"title":"test","state":"OPEN","labels":[],"createdAt":"2024-01-01"}]'
    mock.stderr = ""
    return mock


# ---------------------------------------------------------------------------
# cr.1 — degrade-not-block: gh_fetch returns within timeout+ε even when gh is slow
# ---------------------------------------------------------------------------

class TestGhFetchDegradeNotBlock(unittest.TestCase):
    """cr.1: inject a slow gh (via subprocess.run mock) and assert gh_fetch returns
    within timeout+ε with a labeled sentinel/stale value.

    Asserts it does NOT block for the sleep duration (~30s).
    """

    TIMEOUT = 1.0   # hard timeout passed to gh_fetch
    EPSILON = 1.5   # extra tolerance for process overhead

    def setUp(self):
        gh_cache.clear_cache()

    def tearDown(self):
        gh_cache.clear_cache()

    def test_returns_within_timeout_with_computing_sentinel(self):
        """gh_fetch with slow gh returns computing sentinel within timeout+ε (no prior cache)."""
        import subprocess
        with patch("subprocess.run", side_effect=_slow_subprocess_run):
            t0 = time.monotonic()
            result = gh_cache.gh_fetch(
                ["issue", "list", "--label", "prd"],
                ttl=15.0,
                timeout=self.TIMEOUT,
            )
            elapsed = time.monotonic() - t0

        # Must return quickly — not block for 30s
        self.assertLess(
            elapsed, self.TIMEOUT + self.EPSILON,
            msg=f"gh_fetch blocked for {elapsed:.2f}s; expected <{self.TIMEOUT + self.EPSILON}s",
        )
        # Must return a labeled sentinel
        self.assertIn(
            result.source, ("stale", "computing"),
            msg=f"Expected source 'stale' or 'computing' (no prior cache), got '{result.source}'",
        )
        # computing sentinel: value should be None (no prior data)
        if result.source == "computing":
            self.assertIsNone(
                result.value,
                msg="computing sentinel must have value=None",
            )
        # fetched_at must be a non-empty string
        self.assertIsInstance(result.fetched_at, str)
        self.assertGreater(len(result.fetched_at), 0)

    def test_returns_stale_when_prior_cache_exists(self):
        """gh_fetch returns stale prior-cache value when gh times out."""
        import subprocess

        # Prime the cache with a fast hit
        with patch("subprocess.run", side_effect=_fast_subprocess_run):
            first = gh_cache.gh_fetch(
                ["issue", "list", "--label", "slice-test-stale"],
                ttl=0.0,  # TTL=0 means it will always expire on next call
                timeout=5.0,
            )
        self.assertEqual(first.source, "live", "first call should be live")

        # Clear the TTL by using ttl=0 again; the entry is in cache but expired
        # Now inject a slow subprocess — gh_fetch should return the stale value
        gh_cache.clear_cache()

        # Re-prime with ttl=60 so it IS cached
        with patch("subprocess.run", side_effect=_fast_subprocess_run):
            gh_cache.gh_fetch(
                ["issue", "list", "--label", "slice-test-stale2"],
                ttl=60.0,
                timeout=5.0,
            )
        # Force expiry by directly manipulating the cache ts
        key = gh_cache._cmd_key(["issue", "list", "--label", "slice-test-stale2"])
        with gh_cache._gh_cache_lock:
            if key in gh_cache._gh_cache:
                gh_cache._gh_cache[key]["ts"] = 0  # force expired

        # Now call with slow gh — should return stale
        with patch("subprocess.run", side_effect=_slow_subprocess_run):
            t0 = time.monotonic()
            result = gh_cache.gh_fetch(
                ["issue", "list", "--label", "slice-test-stale2"],
                ttl=60.0,
                timeout=self.TIMEOUT,
            )
            elapsed = time.monotonic() - t0

        self.assertLess(
            elapsed, self.TIMEOUT + self.EPSILON,
            msg=f"gh_fetch stale path blocked {elapsed:.2f}s; expected <{self.TIMEOUT + self.EPSILON}s",
        )
        self.assertEqual(
            result.source, "stale",
            msg=f"Expected source='stale', got '{result.source}'",
        )
        self.assertIsNotNone(result.value, "stale value must not be None")

    def test_does_not_block_for_sleep_duration(self):
        """Timing assertion: gh_fetch must complete well before the mock's 30s sleep."""
        import subprocess
        with patch("subprocess.run", side_effect=_slow_subprocess_run):
            t0 = time.monotonic()
            gh_cache.gh_fetch(
                ["pr", "list", "--state", "open"],
                ttl=15.0,
                timeout=self.TIMEOUT,
            )
            elapsed = time.monotonic() - t0

        # 30s - (timeout + epsilon) is a large gap; if we finished in <3s we clearly
        # did not sleep the full 30s.
        self.assertLess(
            elapsed, 3.0,
            msg=f"gh_fetch appears to have blocked for the full sleep duration ({elapsed:.2f}s)",
        )


# ---------------------------------------------------------------------------
# cr.2 — /api/status responds quickly with affected field degraded when gh is slow
# ---------------------------------------------------------------------------

class TestApiStatusDegradeNotBlock(unittest.TestCase):
    """cr.2: _build_status() returns quickly (<2s) when gh is slow, with only
    open_work degraded (stale/computing); other fields intact.
    """

    STATUS_BUDGET = 2.0   # /api/status must respond within this

    def setUp(self):
        gh_cache.clear_cache()
        # Also clear workitems outer cache
        import workitems as _wi
        _wi._workitems_cache.clear()

    def tearDown(self):
        gh_cache.clear_cache()
        import workitems as _wi
        _wi._workitems_cache.clear()

    def _call_build_status_with_slow_gh(self) -> tuple[dict, float]:
        """Call server._build_status() with gh monkeypatched to be slow.

        Returns (result_dict, elapsed_seconds).
        """
        import subprocess
        import server

        with patch("subprocess.run", side_effect=_slow_subprocess_run):
            # Patch only the workitems + gh_cache subprocess calls, not the git ones.
            # We target gh_cache.subprocess.run to avoid breaking git subprocess calls.
            with patch.object(gh_cache.subprocess, "run", side_effect=_slow_subprocess_run):
                t0 = time.monotonic()
                result = server._build_status()
                elapsed = time.monotonic() - t0

        return result, elapsed

    def test_status_returns_within_budget_when_gh_slow(self):
        """_build_status() must complete within STATUS_BUDGET seconds under slow gh."""
        import server  # noqa: ensure importable
        import subprocess
        import workitems as _wi

        # Patch gh_cache's subprocess.run to be slow (this is what workitems calls)
        with patch.object(gh_cache.subprocess, "run", side_effect=_slow_subprocess_run):
            t0 = time.monotonic()
            result = server._build_status()
            elapsed = time.monotonic() - t0

        self.assertLess(
            elapsed, self.STATUS_BUDGET,
            msg=f"_build_status() took {elapsed:.2f}s under slow gh; budget is {self.STATUS_BUDGET}s",
        )

    def test_open_work_degraded_when_gh_slow(self):
        """open_work fields are degraded (source stale/computing) when gh is slow."""
        import server
        import workitems as _wi

        with patch.object(gh_cache.subprocess, "run", side_effect=_slow_subprocess_run):
            result = server._build_status()

        ow = result.get("open_work", {})
        # Data fields must still be present (prs/slices/captured/backlog)
        for key in ("prs", "slices", "captured", "backlog"):
            self.assertIn(key, ow, msg=f"open_work missing key '{key}'")
        # Source must indicate degraded state
        source = ow.get("source")
        self.assertIn(
            source, ("stale", "computing", None),
            msg=f"open_work.source expected stale/computing/None under slow gh, got '{source}'",
        )

    def test_other_fields_intact_when_gh_slow(self):
        """Non-gh-dependent fields (head_sha, server_sha, hooks_live) are intact
        even when gh is slow (they don't use gh_cache).
        """
        import server
        import workitems as _wi

        with patch.object(gh_cache.subprocess, "run", side_effect=_slow_subprocess_run):
            result = server._build_status()

        # These fields come from git / local files / health.py, not gh CLI
        self.assertIn("head_sha", result)
        self.assertIn("hooks_live", result)
        self.assertIsInstance(result["hooks_live"], dict)
        self.assertIn("alive", result["hooks_live"])
        # health_summary should be present (it uses TTL-cached health check)
        self.assertIn("health_summary", result)


# ---------------------------------------------------------------------------
# cr.8 — cached values carry fetched_at+source; data fields unchanged under normal gh
# ---------------------------------------------------------------------------

class TestGhCacheMetadataAndDataShape(unittest.TestCase):
    """cr.8: cached values carry fetched_at+source; data fields unchanged vs pre-change
    shape under identical (fast) gh responses.
    """

    def setUp(self):
        gh_cache.clear_cache()

    def tearDown(self):
        gh_cache.clear_cache()

    def test_live_result_carries_fetched_at_and_source(self):
        """A fresh gh_fetch call returns a GhResult with fetched_at and source='live'."""
        with patch.object(gh_cache.subprocess, "run", side_effect=_fast_subprocess_run):
            result = gh_cache.gh_fetch(
                ["issue", "list", "--label", "prd"],
                ttl=15.0,
                timeout=5.0,
            )

        self.assertEqual(result.source, "live", "fresh call must have source='live'")
        self.assertIsNotNone(result.fetched_at, "fetched_at must not be None")
        self.assertIsInstance(result.fetched_at, str, "fetched_at must be a str")
        self.assertGreater(len(result.fetched_at), 0, "fetched_at must be non-empty")

    def test_cache_hit_has_source_cache(self):
        """Second call within TTL returns source='cache'."""
        with patch.object(gh_cache.subprocess, "run", side_effect=_fast_subprocess_run):
            gh_cache.gh_fetch(
                ["issue", "list", "--label", "slice"],
                ttl=60.0,
                timeout=5.0,
            )
            # Second call — should hit cache
            result2 = gh_cache.gh_fetch(
                ["issue", "list", "--label", "slice"],
                ttl=60.0,
                timeout=5.0,
            )

        self.assertEqual(result2.source, "cache", "second call within TTL must have source='cache'")
        self.assertIsNotNone(result2.fetched_at)

    def test_open_work_shape_unchanged_under_normal_gh(self):
        """Under fast gh, open_work in _build_status() contains the same data keys
        as before this change (prs, slices, captured, backlog) plus new metadata.
        """
        import server
        import workitems as _wi

        _wi._workitems_cache.clear()

        with patch.object(gh_cache.subprocess, "run", side_effect=_fast_subprocess_run):
            result = server._build_status()

        ow = result.get("open_work", {})
        # Original data keys must all be present
        for key in ("prs", "slices", "captured", "backlog"):
            self.assertIn(key, ow, msg=f"open_work missing original key '{key}'")
        # Each count must be a non-negative integer
        for key in ("prs", "slices", "captured", "backlog"):
            val = ow[key]
            self.assertIsInstance(val, int, msg=f"open_work.{key} must be int, got {type(val)}")
            self.assertGreaterEqual(val, 0, msg=f"open_work.{key} must be >= 0")
        # New metadata keys must also be present
        self.assertIn("fetched_at", ow, "open_work must have fetched_at")
        self.assertIn("source", ow, "open_work must have source")

    def test_fetch_workitems_result_carries_metadata(self):
        """fetch_workitems() result dict carries _fetched_at and _source keys."""
        import workitems as _wi

        _wi._workitems_cache.clear()

        with patch.object(gh_cache.subprocess, "run", side_effect=_fast_subprocess_run):
            result = _wi.fetch_workitems()

        self.assertIn("_fetched_at", result, "fetch_workitems() result must have _fetched_at")
        self.assertIn("_source", result, "fetch_workitems() result must have _source")
        self.assertIn(result["_source"], ("live", "cache", "stale", "computing"),
                      msg=f"_source must be a known value, got '{result['_source']}'")


if __name__ == "__main__":
    unittest.main()
