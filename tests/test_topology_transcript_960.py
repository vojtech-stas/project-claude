"""
Regression tests for slice #960 — transcript-sourced runtime edges + capture banner.

PRD #956 §2 AC #5, #6, #7:
  #5: a topology edge response names the transcript as its observation_source field.
  #6: in a hooks-dark session with a live transcript, ≥1 runtime edge that fired
      this session renders runtime-confirmed (not grey / not-observable).
  #7: when NEITHER transcript NOR hook log is live, capture_unavailable=True is
      set in the observe() return dict (comparison.py threads it to the UI banner).

Groups:
  1. TranscriptIndex    — _build_transcript_window_index() produces correct index
                          from a fixture transcript with agent_start events.
  2. ObserveTranscript  — observe() with a fixture transcript promotes ≥1 edge to
                          runtime-confirmed and names "transcript" as source (AC #5/#6).
  3. CaptureUnavailable — observe() with no transcript and no hook log sets
                          capture_unavailable=True (AC #7).
  4. ComparisonThread   — comparison._apply_runtime_observation() threads
                          capture_unavailable=True through to the report dict.
  5. IndexMerge         — _merge_indices() deduplicates events correctly.
  6. HookFallback       — observe() with a hook log but no transcript still works
                          (backward-compat: source=hook-log, no crash).

Runner: stdlib unittest + pytest compatible.
  python -m pytest tests/test_topology_transcript_960.py -v
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
# Fixture builders
# ---------------------------------------------------------------------------

def _make_transcript_fixture(
    session_id: str,
    agent_dispatches: list[dict],
    win_ts: str = "2026-06-01T10:00:00.000Z",
) -> Path:
    """Build a minimal session transcript JSONL with agent_start events.

    agent_dispatches: list of {subagent_type: str, ts: str (optional)}
    win_ts: timestamp to use when dispatch has no ts (falls within the window).

    Returns the path to the created .jsonl file (in a temp dir).
    """
    tmpdir = Path(tempfile.mkdtemp())
    main_path = tmpdir / f"{session_id}.jsonl"

    records = []
    for i, d in enumerate(agent_dispatches):
        ts = d.get("ts", win_ts)
        records.append({
            "type": "assistant",
            "uuid": f"a-{i:04d}",
            "parentUuid": None,
            "timestamp": ts,
            "sessionId": session_id,
            "message": {
                "role": "assistant",
                "content": [{
                    "type": "tool_use",
                    "id": f"toolu_{i:04d}",
                    "name": "Agent",
                    "input": {
                        "subagent_type": d["subagent_type"],
                        "description": d.get("description", f"run {d['subagent_type']}"),
                        "prompt": f"do work for {d['subagent_type']}",
                    },
                }],
            },
        })

    with main_path.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec) + "\n")

    return main_path


def _make_prd_trail(
    created_at: str = "2026-06-01T09:00:00Z",
    closed_at: str | None = None,
) -> dict:
    """Minimal PRD trail dict with timestamps."""
    return {
        "prd_number": 956,
        "prd_title": "PRD: transcript-sourced execution truth",
        "prd_created_at": created_at,
        "prd_closed_at": closed_at or "",
        "slices": [],
        "prs": {},
        "prd_verdicts": [],
    }


# ---------------------------------------------------------------------------
# Group 1: _build_transcript_window_index
# ---------------------------------------------------------------------------

class TestTranscriptIndex(unittest.TestCase):
    """_build_transcript_window_index() produces correct index from agent_start events."""

    def setUp(self):
        _inject_dashboard()
        import runtime_observer as ro
        self._ro = ro

    def test_agent_start_events_indexed(self):
        """agent_start events appear in the agent_start index keyed by subagent_type."""
        path = _make_transcript_fixture(
            session_id="test-idx-960",
            agent_dispatches=[
                {"subagent_type": "implementer", "ts": "2026-06-01T10:05:00.000Z"},
                {"subagent_type": "reviewer",    "ts": "2026-06-01T10:10:00.000Z"},
            ],
        )
        win_start = 1748775600.0  # 2026-06-01T09:00:00Z
        win_end   = 1748779200.0  # 2026-06-01T10:00:00Z + 1h = ~11:00 UTC

        # Use very wide window to catch all events
        import calendar, datetime
        win_start = calendar.timegm(datetime.datetime(2026, 6, 1, 9, 0, 0).timetuple())
        win_end   = calendar.timegm(datetime.datetime(2026, 6, 1, 12, 0, 0).timetuple())

        live, index = self._ro._build_transcript_window_index(win_start, win_end, path)

        self.assertTrue(live, "capture_live must be True when events are in window")
        self.assertIn("implementer", index.get("agent_start", {}),
                      "implementer must appear in agent_start index")
        self.assertIn("reviewer", index.get("agent_start", {}),
                      "reviewer must appear in agent_start index")

    def test_events_outside_window_excluded(self):
        """Events outside the PRD window are not indexed."""
        path = _make_transcript_fixture(
            session_id="test-idx-out-960",
            agent_dispatches=[
                # Way in the past — outside window
                {"subagent_type": "implementer", "ts": "2020-01-01T10:00:00.000Z"},
            ],
        )
        import calendar, datetime
        win_start = calendar.timegm(datetime.datetime(2026, 6, 1, 9, 0, 0).timetuple())
        win_end   = calendar.timegm(datetime.datetime(2026, 6, 1, 12, 0, 0).timetuple())

        live, index = self._ro._build_transcript_window_index(win_start, win_end, path)

        self.assertFalse(live, "capture_live must be False when no events are in window")
        # Index returned when no events in window: all lists/dicts empty
        all_events = index.get("all_events", [])
        agent_starts = index.get("agent_start", {})
        self.assertEqual(all_events, [],
                         "all_events must be empty when no events in window")
        self.assertEqual(agent_starts, {},
                         "agent_start must be empty when no events in window")

    def test_none_path_returns_false_empty(self):
        """None transcript path returns (False, {}) without crash."""
        live, index = self._ro._build_transcript_window_index(0.0, 1e12, None)
        self.assertFalse(live)
        self.assertEqual(index, {})

    def test_events_tagged_with_transcript_source(self):
        """Events from the transcript index are tagged with _observation_source='transcript'."""
        path = _make_transcript_fixture(
            session_id="test-idx-src-960",
            agent_dispatches=[
                {"subagent_type": "slicer", "ts": "2026-06-01T10:05:00.000Z"},
            ],
        )
        import calendar, datetime
        win_start = calendar.timegm(datetime.datetime(2026, 6, 1, 9, 0, 0).timetuple())
        win_end   = calendar.timegm(datetime.datetime(2026, 6, 1, 12, 0, 0).timetuple())

        _, index = self._ro._build_transcript_window_index(win_start, win_end, path)

        events = index.get("agent_start", {}).get("slicer", [])
        self.assertTrue(len(events) > 0, "slicer events must be indexed")
        ev = events[0]
        self.assertEqual(
            ev.get("_observation_source"), "transcript",
            f"Expected _observation_source='transcript', got: {ev.get('_observation_source')!r}",
        )


# ---------------------------------------------------------------------------
# Group 2: observe() with fixture transcript promotes edges (AC #5 and #6)
# ---------------------------------------------------------------------------

class TestObserveTranscript(unittest.TestCase):
    """observe() with a fixture transcript promotes ≥1 edge to runtime-confirmed
    and names 'transcript' as observation_source (AC #5/#6)."""

    def setUp(self):
        _inject_dashboard()
        import runtime_observer as ro
        self._ro = ro

    def _observe_with_transcript(self, agent_dispatches: list[dict]) -> dict:
        """Helper: build a fixture transcript and call observe() pointing at it."""
        path = _make_transcript_fixture(
            session_id="test-obs-960",
            agent_dispatches=agent_dispatches,
            win_ts="2026-06-01T10:05:00.000Z",
        )
        trail = _make_prd_trail(created_at="2026-06-01T09:00:00Z")

        # No hook log — point at a non-existent path
        no_log = Path(tempfile.mkdtemp()) / "nonexistent.jsonl"

        return self._ro.observe(trail, log_path=no_log, transcript_path=path)

    def test_slicer_edge_confirmed_from_transcript(self):
        """E-SLICER-SLICERCRITIC: slicer agent_complete then slicer-critic agent_start
        from transcript → edge becomes runtime-confirmed (not not-observable).

        For simpler coverage: E-MERGE-CODEBASECRITIC requires only
        agent_start(codebase-critic) in the window — simplest edge to assert on.
        """
        result = self._observe_with_transcript([
            {"subagent_type": "codebase-critic",
             "ts": "2026-06-01T10:05:00.000Z"},
        ])
        runtime_edges = result.get("runtime_edges", {})
        edge = runtime_edges.get("E-MERGE-CODEBASECRITIC", {})
        self.assertEqual(
            edge.get("state"), "runtime-confirmed",
            f"Expected runtime-confirmed for E-MERGE-CODEBASECRITIC, got: {edge.get('state')!r}\n"
            f"detail: {edge.get('detail')!r}",
        )

    def test_edge_names_transcript_as_source(self):
        """AC #5: a confirmed edge has observation_source='transcript'."""
        result = self._observe_with_transcript([
            {"subagent_type": "codebase-critic",
             "ts": "2026-06-01T10:05:00.000Z"},
        ])
        runtime_edges = result.get("runtime_edges", {})
        edge = runtime_edges.get("E-MERGE-CODEBASECRITIC", {})

        # Either in observation_source or in event_evidence.observation_source
        direct_src = edge.get("observation_source")
        ev_ev = edge.get("event_evidence", {})
        ev_src = ev_ev.get("observation_source") if isinstance(ev_ev, dict) else None
        source = direct_src or ev_src

        self.assertEqual(
            source, "transcript",
            f"Expected observation_source='transcript' on confirmed edge, "
            f"got direct={direct_src!r}, event_evidence={ev_ev!r}",
        )

    def test_at_least_one_confirmed_edge(self):
        """AC #6: ≥1 runtime edge is runtime-confirmed (not all not-observable)."""
        result = self._observe_with_transcript([
            {"subagent_type": "codebase-critic", "ts": "2026-06-01T10:05:00.000Z"},
            {"subagent_type": "slicer",          "ts": "2026-06-01T10:06:00.000Z"},
            {"subagent_type": "slicer-critic",   "ts": "2026-06-01T10:07:00.000Z"},
        ])
        rc = result.get("runtime_coverage", {})
        confirmed = rc.get("confirmed", 0)
        self.assertGreater(
            confirmed, 0,
            f"Expected ≥1 runtime-confirmed edge (hooks-dark + live transcript), "
            f"got confirmed={confirmed}, coverage={rc}",
        )

    def test_capture_unavailable_false_with_transcript(self):
        """capture_unavailable must be False when transcript has events in window."""
        result = self._observe_with_transcript([
            {"subagent_type": "codebase-critic", "ts": "2026-06-01T10:05:00.000Z"},
        ])
        self.assertFalse(
            result.get("capture_unavailable"),
            "capture_unavailable must be False when transcript is live",
        )


# ---------------------------------------------------------------------------
# Group 3: capture_unavailable=True when no source (AC #7)
# ---------------------------------------------------------------------------

class TestCaptureUnavailable(unittest.TestCase):
    """observe() sets capture_unavailable=True when NEITHER transcript NOR hook log
    has events in the PRD window (AC #7)."""

    def setUp(self):
        _inject_dashboard()
        import runtime_observer as ro
        self._ro = ro

    def test_capture_unavailable_when_no_sources(self):
        """No transcript + no hook log → capture_unavailable=True."""
        trail = _make_prd_trail(created_at="2026-06-01T09:00:00Z")

        no_log = Path(tempfile.mkdtemp()) / "nonexistent.jsonl"
        no_transcript = Path(tempfile.mkdtemp()) / "nonexistent_transcript.jsonl"

        result = self._ro.observe(trail, log_path=no_log, transcript_path=no_transcript)

        self.assertTrue(
            result.get("capture_unavailable"),
            "capture_unavailable must be True when no events found in either source",
        )

    def test_all_edges_not_observable_when_no_sources(self):
        """All runtime edges must be not-observable when no observation source."""
        trail = _make_prd_trail(created_at="2026-06-01T09:00:00Z")

        no_log = Path(tempfile.mkdtemp()) / "nonexistent.jsonl"
        no_transcript = Path(tempfile.mkdtemp()) / "nonexistent_transcript.jsonl"

        result = self._ro.observe(trail, log_path=no_log, transcript_path=no_transcript)
        rc = result.get("runtime_coverage", {})

        self.assertEqual(
            rc.get("confirmed", 0), 0,
            f"Expected 0 confirmed edges when no sources, got {rc.get('confirmed')}",
        )
        # All covered edges must be not-observable (capture dead)
        not_obs = rc.get("not_observable", 0)
        expected = len(self._ro.COVERED_EDGE_IDS)
        self.assertEqual(
            not_obs, expected,
            f"Expected {expected} not-observable edges, got {not_obs} (coverage={rc})",
        )

    def test_empty_transcript_sets_capture_unavailable(self):
        """An empty transcript file (no events in window) → capture_unavailable=True."""
        tmpdir = Path(tempfile.mkdtemp())
        empty_transcript = tmpdir / "empty.jsonl"
        empty_transcript.write_text("", encoding="utf-8")

        trail = _make_prd_trail(created_at="2026-06-01T09:00:00Z")
        no_log = tmpdir / "nonexistent.jsonl"

        result = self._ro.observe(trail, log_path=no_log, transcript_path=empty_transcript)

        self.assertTrue(
            result.get("capture_unavailable"),
            "capture_unavailable must be True when transcript has no events in window",
        )


# ---------------------------------------------------------------------------
# Group 4: comparison._apply_runtime_observation threads capture_unavailable
# ---------------------------------------------------------------------------

class TestComparisonThread(unittest.TestCase):
    """comparison._apply_runtime_observation() threads capture_unavailable=True
    through to the comparison report dict (AC #7).

    _apply_runtime_observation() calls runtime_observer.observe() via a local
    import inside comparison.py.  We test by directly calling observe() with
    controlled paths and then passing the result through _apply_runtime_observation
    via a mock that returns our pre-computed observe() output.
    """

    def setUp(self):
        _inject_dashboard()
        import comparison as cmp
        import runtime_observer as ro
        self._cmp = cmp
        self._ro = ro

    def _build_report_skeleton(self) -> dict:
        """Minimal comparison report skeleton for _apply_runtime_observation."""
        from pipeline_spec import get_spec  # type: ignore[import]
        spec = get_spec()
        return {
            "prd_number": 956,
            "run_pass": False,
            "edges": {
                e["id"]: {
                    "state": "not-evaluated",
                    "detail": "",
                    "evidence": e.get("evidence", "github"),
                    "required": e.get("required", "always"),
                }
                for e in spec.get("edges", [])
            },
            "violations": [],
            "unexpected": [],
        }

    def test_capture_unavailable_in_report_when_no_sources(self):
        """capture_unavailable=True propagates to comparison report."""
        trail = _make_prd_trail(created_at="2026-06-01T09:00:00Z")
        report = self._build_report_skeleton()

        no_log = Path(tempfile.mkdtemp()) / "nonexistent.jsonl"
        no_transcript = Path(tempfile.mkdtemp()) / "nonexistent.jsonl"

        # Get the real observe() result with no sources
        obs_result = self._ro.observe(trail, log_path=no_log, transcript_path=no_transcript)

        # Patch the local import of runtime_observer inside comparison.py
        # by injecting a fake observe into the module directly
        import comparison as cmp_mod
        import importlib
        # comparison.py imports runtime_observer lazily inside the function body.
        # We inject into the runtime_observer module's observe attribute directly.
        orig_observe = self._ro.observe
        self._ro.observe = lambda *a, **kw: obs_result
        try:
            updated = cmp_mod._apply_runtime_observation(report, trail)
        finally:
            self._ro.observe = orig_observe

        self.assertIn("capture_unavailable", updated,
                      "capture_unavailable key must be present in updated report")
        self.assertTrue(
            updated.get("capture_unavailable"),
            f"capture_unavailable must be True in report when no sources, "
            f"got: {updated.get('capture_unavailable')!r}",
        )

    def test_capture_unavailable_false_with_transcript(self):
        """capture_unavailable=False when transcript has events in window."""
        trail = _make_prd_trail(created_at="2026-06-01T09:00:00Z")
        report = self._build_report_skeleton()

        path = _make_transcript_fixture(
            session_id="test-cmp-960",
            agent_dispatches=[
                {"subagent_type": "codebase-critic", "ts": "2026-06-01T10:05:00.000Z"},
            ],
        )
        no_log = Path(tempfile.mkdtemp()) / "nonexistent.jsonl"

        obs_result = self._ro.observe(trail, log_path=no_log, transcript_path=path)

        import comparison as cmp_mod
        orig_observe = self._ro.observe
        self._ro.observe = lambda *a, **kw: obs_result
        try:
            updated = cmp_mod._apply_runtime_observation(report, trail)
        finally:
            self._ro.observe = orig_observe

        self.assertFalse(
            updated.get("capture_unavailable"),
            "capture_unavailable must be False when transcript is live",
        )


# ---------------------------------------------------------------------------
# Group 5: _merge_indices deduplication
# ---------------------------------------------------------------------------

class TestIndexMerge(unittest.TestCase):
    """_merge_indices() merges two event-index dicts without duplicate events."""

    def setUp(self):
        _inject_dashboard()
        import runtime_observer as ro
        self._ro = ro

    def test_unique_events_from_both_sources(self):
        """Unique events from both sources appear in merged index."""
        ev_a = {"ts": "2026-06-01T10:01:00Z", "event": "agent_start",
                "session_id": "s1", "subagent_type": "implementer"}
        ev_b = {"ts": "2026-06-01T10:02:00Z", "event": "agent_start",
                "session_id": "s1", "subagent_type": "reviewer"}

        index_a = {
            "skill_invoke": {}, "user_prompt": [], "bash_complete": [],
            "agent_start": {"implementer": [ev_a], "__all__": [ev_a]},
            "agent_complete": {}, "all_events": [ev_a],
        }
        index_b = {
            "skill_invoke": {}, "user_prompt": [], "bash_complete": [],
            "agent_start": {"reviewer": [ev_b], "__all__": [ev_b]},
            "agent_complete": {}, "all_events": [ev_b],
        }

        merged = self._ro._merge_indices(index_a, index_b)
        all_ev = merged.get("all_events", [])
        self.assertEqual(len(all_ev), 2, f"Expected 2 events, got {len(all_ev)}")

    def test_duplicate_events_deduplicated(self):
        """Identical events (same ts+event+session_id) appear only once."""
        ev = {"ts": "2026-06-01T10:01:00Z", "event": "agent_start",
              "session_id": "s1", "subagent_type": "implementer"}

        index_a = {
            "skill_invoke": {}, "user_prompt": [], "bash_complete": [],
            "agent_start": {"implementer": [ev], "__all__": [ev]},
            "agent_complete": {}, "all_events": [ev],
        }
        index_b = {
            "skill_invoke": {}, "user_prompt": [], "bash_complete": [],
            "agent_start": {"implementer": [ev], "__all__": [ev]},
            "agent_complete": {}, "all_events": [ev],
        }

        merged = self._ro._merge_indices(index_a, index_b)
        all_ev = merged.get("all_events", [])
        self.assertEqual(len(all_ev), 1,
                         f"Duplicate event must be deduplicated, got {len(all_ev)} events")

    def test_empty_primary_returns_secondary(self):
        """Empty primary index: returns secondary."""
        ev = {"ts": "2026-06-01T10:01:00Z", "event": "agent_start",
              "session_id": "s1", "subagent_type": "slicer"}
        index_b = {
            "skill_invoke": {}, "user_prompt": [], "bash_complete": [],
            "agent_start": {"slicer": [ev], "__all__": [ev]},
            "agent_complete": {}, "all_events": [ev],
        }
        merged = self._ro._merge_indices({}, index_b)
        self.assertIn("slicer", merged.get("agent_start", {}))


# ---------------------------------------------------------------------------
# Group 6: hook-log fallback (backward compat — no regression)
# ---------------------------------------------------------------------------

class TestHookFallback(unittest.TestCase):
    """observe() with a hook log but no transcript still works (backward compat)."""

    def setUp(self):
        _inject_dashboard()
        import runtime_observer as ro
        self._ro = ro

    def test_hook_log_still_works_as_source(self):
        """observe() with hook-log events (no transcript) still returns results."""
        trail = _make_prd_trail(created_at="2026-06-01T09:00:00Z")

        # Build a minimal hook log event
        hook_event = {
            "v": 2,
            "ts": "2026-06-01T10:05:00+00:00",
            "session_id": "hook-session-960",
            "event": "agent_start",
            "src": "hook",
            "subagent_type": "codebase-critic",
        }
        tmpdir = Path(tempfile.mkdtemp())
        hook_log = tmpdir / "workflow-events.jsonl"
        hook_log.write_text(json.dumps(hook_event) + "\n", encoding="utf-8")

        no_transcript = tmpdir / "nonexistent.jsonl"

        result = self._ro.observe(trail, log_path=hook_log, transcript_path=no_transcript)

        rc = result.get("runtime_coverage", {})
        self.assertGreater(
            rc.get("confirmed", 0), 0,
            f"Expected ≥1 confirmed edge from hook log, got coverage={rc}",
        )
        self.assertFalse(
            result.get("capture_unavailable"),
            "capture_unavailable must be False when hook log has events",
        )

    def test_no_crash_on_observe_with_neither_source(self):
        """observe() never crashes regardless of source availability."""
        trail = _make_prd_trail(created_at="2026-06-01T09:00:00Z")
        no_log = Path(tempfile.mkdtemp()) / "nonexistent.jsonl"
        no_transcript = Path(tempfile.mkdtemp()) / "nonexistent.jsonl"

        try:
            result = self._ro.observe(trail, log_path=no_log, transcript_path=no_transcript)
        except Exception as exc:
            self.fail(f"observe() raised {type(exc).__name__}: {exc}")

        self.assertIn("runtime_edges", result)
        self.assertIn("capture_unavailable", result)


if __name__ == "__main__":
    unittest.main()
