"""
Regression test for issue #1027 — firing-tree resolution cache + body-first order.

Root causes (two compounding gaps from #1022):
  1. _resolve_slice_to_prd calls the sub-issue /parent endpoint FIRST (a 2nd
     gh call) for every slice — even though the slice body (already fetched by
     gh issue view) usually contains "Part of PRD #N" which resolves for free.
  2. No persistent cross-build disk cache of resolve_dispatch_to_prd(n) results
     → every build re-hammers gh; cold ~130-issue builds have most calls time out
     → 112/134 groups show "(gh unavailable)".

These tests FAIL on current develop (before the fix) and PASS after (commit #2).

Test assertions:
  (a) body-first: a slice whose gh issue view body says "Part of PRD #993" resolves
      to 993 with the sub-issue /parent endpoint NEVER called (gh call count = 1,
      just the issue view; not 3).
  (b) cache-hit: a second resolution of the same issue number makes ZERO additional
      gh calls (disk cache hit via temp cache dir).
  (c) no-cache-on-failure: a _GH_UNAVAILABLE transport failure is NOT persisted to
      disk cache — the next call retries gh (not a permanent cache miss).

NO top-level `import pytest` — stdlib unittest only.

Runner:
  python -m unittest tests.test_firing_resolution_cache_1027 -v
  python -m pytest tests/test_firing_resolution_cache_1027.py -v
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).parent.parent
DASHBOARD_DIR = REPO_ROOT / "dashboard"


def _inject_dashboard() -> None:
    s = str(DASHBOARD_DIR)
    if s not in sys.path:
        sys.path.insert(0, s)


# ---------------------------------------------------------------------------
# Common gh mock helpers
# ---------------------------------------------------------------------------

def _make_gh_run_with_counter(
    issue_labels: dict[int, list[str]],
    issue_bodies: dict[int, str] | None = None,
    sub_issue_parents: dict[int, int | None] | None = None,
) -> tuple:
    """Return (fake_gh_run, call_log) where call_log accumulates every call.

    issue_labels: {issue_number: [label_name, ...]}
    issue_bodies: {issue_number: body_text}
    sub_issue_parents: {issue_number: parent_or_none} — present key means endpoint
        responds (None → rc=0, "null"; int → rc=0, str(int)); MISSING key → rc=1
        (simulates transport failure / endpoint unavailable).
    """
    if issue_bodies is None:
        issue_bodies = {}
    if sub_issue_parents is None:
        sub_issue_parents = {}

    call_log: list[str] = []  # accumulates descriptive call labels

    def fake_gh_run(args: list[str], timeout: int = 15):
        # gh repo view --json nameWithOwner -q .nameWithOwner
        if "repo" in args and "view" in args:
            call_log.append("repo-view")
            return 0, "vojtech-stas/project-claude"

        # gh api repos/.../issues/{n}/parent --jq .number
        if "api" in args:
            num = None
            for a in args:
                if "/issues/" in a and "/parent" in a:
                    parts = a.split("/")
                    try:
                        idx = parts.index("issues")
                        num = int(parts[idx + 1])
                    except (ValueError, IndexError):
                        pass
                    break
            if num is None:
                call_log.append("api-parent-unknown")
                return 1, ""
            call_log.append(f"api-parent-{num}")
            if num not in sub_issue_parents:
                return 1, ""  # transport failure / unavailable
            val = sub_issue_parents[num]
            if val is None:
                return 0, "null"
            return 0, str(val)

        # gh issue view <N> --json number,labels,body
        if "issue" in args and "view" in args:
            num = None
            for a in args:
                try:
                    num = int(a)
                    break
                except (ValueError, TypeError):
                    continue
            if num is None:
                call_log.append("issue-view-unknown")
                return 1, ""
            call_log.append(f"issue-view-{num}")
            if num not in issue_labels:
                return 1, ""
            labels = [{"name": n} for n in issue_labels[num]]
            body = issue_bodies.get(num, "")
            return 0, json.dumps({"number": num, "labels": labels, "body": body})

        call_log.append(f"unknown-{args[:2]}")
        return 1, ""

    return fake_gh_run, call_log


# ---------------------------------------------------------------------------
# Case (a): body-first — sub-issue /parent endpoint must NOT be called when
# the gh issue view body already contains "Part of PRD #N"
# ---------------------------------------------------------------------------

class TestBodyFirstNoParentCall(unittest.TestCase):
    """resolve_dispatch_to_prd(N) must NOT call the /parent endpoint when the
    already-fetched issue body contains 'Part of PRD #N'.

    FAILS before fix: _resolve_slice_to_prd calls _fetch_sub_issue_parent
    (which triggers repo-view + api-parent) BEFORE _parent_prd_from_issue_body,
    so the /parent endpoint IS called even when the body would resolve it.

    PASSES after fix: body is parsed first; /parent is only called when the
    body yields no parent reference — so for 'Part of PRD #993' body, the
    total gh call count is exactly 1 (just the issue view).
    """

    def setUp(self):
        _inject_dashboard()
        import transcript
        self.transcript = transcript
        transcript._prd_cache.clear()
        transcript._prd_cache_ts = 0.0
        transcript._disk_cache_data = {}
        transcript._transcript_repo_slug = None
        self._tmp = tempfile.mkdtemp()
        self._cache_file = Path(self._tmp) / "test-body-first-cache.json"
        self._patcher = patch("transcript._disk_cache_path",
                              return_value=self._cache_file)
        self._patcher.start()

    def tearDown(self):
        import shutil
        self._patcher.stop()
        import transcript
        transcript._prd_cache.clear()
        transcript._prd_cache_ts = 0.0
        transcript._disk_cache_data = None
        transcript._transcript_repo_slug = None
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_body_first_no_parent_endpoint_called(self):
        """Slice #995 body says 'Part of PRD #993' → resolves to 993 with
        exactly 1 gh call (issue view only); /parent endpoint must NOT be called.

        FAILS before fix: call count is 3 (issue-view + repo-view + api-parent).
        PASSES after fix: call count is 1 (issue-view only; body parse finds parent).
        """
        issue_labels = {995: ["slice"]}
        issue_bodies = {
            995: "Part of PRD #993 — walking skeleton of the firing tree feature.",
        }
        # sub_issue_parents intentionally omitted for 995 — if /parent IS called,
        # it would fail (key missing → rc=1), which would surface the call.
        fake_gh, call_log = _make_gh_run_with_counter(
            issue_labels, issue_bodies,
            sub_issue_parents={},  # no entry for 995 → call would fail
        )

        with patch.object(self.transcript, "_gh_run_transcript", side_effect=fake_gh):
            result = self.transcript.resolve_dispatch_to_prd(995)

        self.assertEqual(
            result, 993,
            msg=(
                f"resolve_dispatch_to_prd(995) returned {result!r} — expected 993.\n"
                f"gh calls made: {call_log}\n\n"
                "Body says 'Part of PRD #993'; body-first fix should resolve without "
                "/parent call."
            ),
        )

        parent_calls = [c for c in call_log if "api-parent" in c]
        self.assertEqual(
            parent_calls, [],
            msg=(
                f"Sub-issue /parent endpoint was called: {parent_calls}\n"
                f"All gh calls: {call_log}\n\n"
                "BEFORE FIX: _resolve_slice_to_prd calls _fetch_sub_issue_parent "
                "BEFORE _parent_prd_from_issue_body, so /parent IS called (count=3).\n"
                "AFTER FIX: body is parsed first; /parent is skipped when body has "
                "the parent reference."
            ),
        )

        issue_view_calls = [c for c in call_log if c.startswith("issue-view")]
        self.assertEqual(
            len(issue_view_calls), 1,
            msg=(
                f"Expected exactly 1 issue-view call, got {len(issue_view_calls)}: "
                f"{issue_view_calls}\nAll calls: {call_log}"
            ),
        )


# ---------------------------------------------------------------------------
# Case (b): cache-hit — second resolution of same issue makes ZERO gh calls
# ---------------------------------------------------------------------------

class TestCacheHitZeroGhCalls(unittest.TestCase):
    """A second call to resolve_dispatch_to_prd for the same issue number
    must make ZERO gh calls — the result is served from disk cache.

    This tests that the disk cache (written on first resolution) is actually
    read back on the second call.  Uses a temp dir for the cache file to
    isolate from any pre-existing entries.

    Both calls must also return the same value (993).

    FAILS before fix: the disk cache WAS already present (slice #959) but this
    test is NEW for #1027 and specifically asserts zero gh calls on cache hit
    after an explicit disk-cache load/reload cycle.
    """

    def setUp(self):
        _inject_dashboard()
        import transcript
        self.transcript = transcript
        transcript._prd_cache.clear()
        transcript._prd_cache_ts = 0.0
        transcript._disk_cache_data = None  # force disk-cache reload
        transcript._transcript_repo_slug = None
        self._tmp = tempfile.mkdtemp()
        self._cache_file = Path(self._tmp) / "test-cache-hit.json"
        self._patcher = patch("transcript._disk_cache_path",
                              return_value=self._cache_file)
        self._patcher.start()

    def tearDown(self):
        import shutil
        self._patcher.stop()
        import transcript
        transcript._prd_cache.clear()
        transcript._prd_cache_ts = 0.0
        transcript._disk_cache_data = None
        transcript._transcript_repo_slug = None
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_second_resolution_zero_gh_calls(self):
        """First call resolves via gh; second call hits disk cache (0 gh calls).

        FAILS before fix: the assertion here is new; the specific scenario of
        clearing in-process cache between calls and reloading from disk may not
        have been validated.  This also validates the body-first fix by ensuring
        the first call itself uses only 1 gh call.
        """
        issue_labels = {1005: ["slice"]}
        issue_bodies = {1005: "Part of PRD #993 — second test slice."}
        fake_gh, call_log = _make_gh_run_with_counter(
            issue_labels, issue_bodies,
            sub_issue_parents={},  # not called if body-first fix applied
        )

        with patch.object(self.transcript, "_gh_run_transcript", side_effect=fake_gh):
            r1 = self.transcript.resolve_dispatch_to_prd(1005)

        calls_after_first = list(call_log)

        # Simulate a new process/build: clear in-process cache but keep disk cache
        self.transcript._prd_cache.clear()
        self.transcript._prd_cache_ts = 0.0
        self.transcript._disk_cache_data = None  # force disk re-read

        with patch.object(self.transcript, "_gh_run_transcript", side_effect=fake_gh):
            r2 = self.transcript.resolve_dispatch_to_prd(1005)

        calls_after_second = call_log[len(calls_after_first):]

        self.assertEqual(
            r1, 993,
            msg=f"First resolution returned {r1!r}, expected 993. Calls: {calls_after_first}",
        )
        self.assertEqual(
            r2, 993,
            msg=f"Second resolution returned {r2!r}, expected 993. Calls: {calls_after_second}",
        )
        self.assertEqual(
            calls_after_second, [],
            msg=(
                f"Second resolution made gh calls: {calls_after_second}\n"
                f"All calls: {call_log}\n\n"
                "After in-process cache clear, the disk cache should serve the "
                "result without any gh call.  If gh calls appear here, the disk "
                "cache is not being written or read correctly."
            ),
        )


# ---------------------------------------------------------------------------
# Case (c): no-cache-on-failure — _GH_UNAVAILABLE transport failures must NOT
# be persisted to disk cache so the next call retries
# ---------------------------------------------------------------------------

class TestNoCacheOnGhFailure(unittest.TestCase):
    """When all gh calls fail (_GH_UNAVAILABLE), resolve_dispatch_to_prd must
    NOT write to the disk cache — the next call must retry gh.

    If a transport failure were cached on disk, a temporarily-unavailable gh
    would permanently mark issues as unresolvable across restarts.

    FAILS before fix: the disk cache ALREADY has this guard (written for slice
    #959 — 'Do NOT write None to disk for gh failures'), but this test is NEW
    for #1027 and explicitly validates the behaviour with a round-trip:
    first-call fails → clears in-process cache → second call retries gh
    (not serving from disk).

    Actually: the existing slice #959 code does NOT write to disk on
    _GH_UNAVAILABLE.  This test validates that guarantee still holds and is
    not broken by the body-first refactor.  The test itself is NEW — FAILS if
    the disk-cache write is accidentally added for the failure path.
    """

    def setUp(self):
        _inject_dashboard()
        import transcript
        self.transcript = transcript
        transcript._prd_cache.clear()
        transcript._prd_cache_ts = 0.0
        transcript._disk_cache_data = None
        transcript._transcript_repo_slug = None
        self._tmp = tempfile.mkdtemp()
        self._cache_file = Path(self._tmp) / "test-no-cache-failure.json"
        self._patcher = patch("transcript._disk_cache_path",
                              return_value=self._cache_file)
        self._patcher.start()

    def tearDown(self):
        import shutil
        self._patcher.stop()
        import transcript
        transcript._prd_cache.clear()
        transcript._prd_cache_ts = 0.0
        transcript._disk_cache_data = None
        transcript._transcript_repo_slug = None
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_gh_failure_not_cached_to_disk(self):
        """First call fails (gh unavailable) → returns None.
        Second call (after clearing in-process cache) retries gh — not blocked
        by a stale disk-cache entry.

        FAILS before fix IF: _GH_UNAVAILABLE results were ever written to disk
        (they must not be).  Also validates that the second call DOES retry gh.
        """
        issue_labels = {777: ["slice"]}
        issue_bodies = {777: "Part of PRD #993 — transport-test slice."}

        # Phase 1: always fail — simulates a gh outage
        def always_fail(args, timeout=15):
            return 1, ""

        with patch.object(self.transcript, "_gh_run_transcript",
                          side_effect=always_fail):
            r1 = self.transcript.resolve_dispatch_to_prd(777)

        self.assertIsNone(
            r1,
            msg=(
                f"First call (gh failing) returned {r1!r}, expected None.\n"
                "When gh fails, resolve_dispatch_to_prd should return None."
            ),
        )

        # Disk cache must be empty (no entry for 777) — failure not persisted
        disk_data = {}
        if self._cache_file.exists():
            try:
                disk_data = json.loads(self._cache_file.read_text(encoding="utf-8"))
            except Exception:
                pass

        self.assertNotIn(
            "777", disk_data,
            msg=(
                f"Disk cache has entry for 777: {disk_data.get('777')!r}\n"
                "A _GH_UNAVAILABLE transport failure MUST NOT be written to disk — "
                "the next call must be able to retry gh."
            ),
        )

        # Phase 2: clear in-process cache, retry with gh now available
        self.transcript._prd_cache.clear()
        self.transcript._prd_cache_ts = 0.0
        self.transcript._disk_cache_data = None
        self.transcript._transcript_repo_slug = None

        fake_gh_ok, _ = _make_gh_run_with_counter(
            issue_labels, issue_bodies,
            sub_issue_parents={},  # empty: body-first fix means /parent not called
        )

        with patch.object(self.transcript, "_gh_run_transcript",
                          side_effect=fake_gh_ok):
            r2 = self.transcript.resolve_dispatch_to_prd(777)

        self.assertEqual(
            r2, 993,
            msg=(
                f"Second call (gh now available) returned {r2!r}, expected 993.\n"
                "After clearing in-process cache, a retried resolution should succeed "
                "because the failure was not cached to disk."
            ),
        )


if __name__ == "__main__":
    unittest.main()
