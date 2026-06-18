"""
Tests for slice #929 — firing timeline WHO + tool_target + outcome + completeness.

Groups:
  1. FiringWhoFields     — build_firing_tree() adds non-empty actor/tool_target/outcome
                           to every dispatch in a fixture session.
  2. CompletenessCount   — completeness_count equals deduped agent_start count from
                           the full transcript parse; subagent copies do not inflate it.
  3. OutcomeFallback     — outcome == "dispatched" when no verdict has been recorded yet.
  4. ActorDerivation     — actor == "orchestrator" when dispatch is from main transcript;
                           actor == parent agent type when dispatch is from a subagent.
  5. ServerRouteFields   — /api/session-firing response includes completeness_count key
                           (static grep on server.py + index.html — no live bind).

Runner: stdlib unittest + pytest compatible.
  python -m pytest tests/test_firing_who_929.py -v
"""

import json
import shutil
import sys
import tempfile
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
# Fixture builder — reusable across test groups
# ---------------------------------------------------------------------------

def _build_fixture_session(tmpdir: Path) -> tuple[Path, str]:
    """Build a minimal but representative session layout in tmpdir.

    Layout:
      <tmpdir>/<session-id>.jsonl           — main transcript (2 Agent dispatches)
      <tmpdir>/<session-id>/subagents/      — subagent files + meta.json
        agent-impl-hex.jsonl + .meta.json   — implementer (SUCCESS)
        agent-rev-hex.jsonl  + .meta.json   — reviewer    (APPROVE)

    Returns (main_path, session_id).
    """
    session_id = "test-929-who-session"
    main_path = tmpdir / f"{session_id}.jsonl"
    sub_dir = tmpdir / session_id / "subagents"
    sub_dir.mkdir(parents=True, exist_ok=True)

    # Main transcript: two Agent dispatches from the orchestrator (no agentId)
    main_records = [
        {
            "type": "assistant",
            "uuid": "a-dispatch-impl",
            "parentUuid": None,
            "timestamp": "2026-06-18T09:00:00.000Z",
            "sessionId": session_id,
            "message": {
                "role": "assistant",
                "content": [
                    {
                        "type": "tool_use",
                        "id": "toolu_impl_929",
                        "name": "Agent",
                        "input": {
                            "subagent_type": "implementer",
                            "description": "Run implementer for #929",
                            "prompt": "Implement slice #929",
                        },
                    }
                ],
            },
        },
        {
            "type": "assistant",
            "uuid": "a-dispatch-rev",
            "parentUuid": None,
            "timestamp": "2026-06-18T09:10:00.000Z",
            "sessionId": session_id,
            "message": {
                "role": "assistant",
                "content": [
                    {
                        "type": "tool_use",
                        "id": "toolu_rev_929",
                        "name": "Agent",
                        "input": {
                            "subagent_type": "reviewer",
                            "description": "review PR #930 (slice #929)",
                            "prompt": "Review PR #930",
                        },
                    }
                ],
            },
        },
    ]
    with main_path.open("w", encoding="utf-8") as f:
        for rec in main_records:
            f.write(json.dumps(rec) + "\n")

    # Implementer subagent: SUCCESS trailer
    impl_records = [
        {
            "type": "user",
            "uuid": "u-impl-1",
            "agentId": "agent-impl-hex",
            "timestamp": "2026-06-18T09:01:00.000Z",
            "sessionId": session_id,
            "message": {"role": "user", "content": [{"type": "text", "text": "Implement slice #929"}]},
        },
        {
            "type": "assistant",
            "uuid": "a-impl-final",
            "agentId": "agent-impl-hex",
            "timestamp": "2026-06-18T09:08:00.000Z",
            "sessionId": session_id,
            "message": {
                "role": "assistant",
                "content": [{"type": "text", "text": (
                    "Done!\n\n"
                    "RESULT: SUCCESS\n"
                    "REASON: PR opened\n"
                    "PR_URL: https://github.com/x/y/pull/930\n"
                    "BRANCH_NAME: feat/929-firing-who-verbose\n"
                    "SLICE_ISSUE: #929\n"
                )}],
            },
        },
    ]
    impl_jsonl = sub_dir / "agent-impl-hex.jsonl"
    with impl_jsonl.open("w", encoding="utf-8") as f:
        for rec in impl_records:
            f.write(json.dumps(rec) + "\n")
    with (sub_dir / "agent-impl-hex.meta.json").open("w", encoding="utf-8") as f:
        json.dump({
            "agentType": "implementer",
            "description": "Run implementer for #929",
            "toolUseId": "toolu_impl_929",
        }, f)

    # Reviewer subagent: APPROVE trailer
    rev_records = [
        {
            "type": "user",
            "uuid": "u-rev-1",
            "agentId": "agent-rev-hex",
            "timestamp": "2026-06-18T09:11:00.000Z",
            "sessionId": session_id,
            "message": {"role": "user", "content": [{"type": "text", "text": "Review PR #930"}]},
        },
        {
            "type": "assistant",
            "uuid": "a-rev-final",
            "agentId": "agent-rev-hex",
            "timestamp": "2026-06-18T09:15:00.000Z",
            "sessionId": session_id,
            "message": {
                "role": "assistant",
                "content": [{"type": "text", "text": (
                    "All checks pass.\n\n"
                    "VERDICT: APPROVE\n"
                    "REASON: All rules pass\n"
                    "ROUND: 1\n"
                    "CRITIC: reviewer\n"
                )}],
            },
        },
    ]
    rev_jsonl = sub_dir / "agent-rev-hex.jsonl"
    with rev_jsonl.open("w", encoding="utf-8") as f:
        for rec in rev_records:
            f.write(json.dumps(rec) + "\n")
    with (sub_dir / "agent-rev-hex.meta.json").open("w", encoding="utf-8") as f:
        json.dump({
            "agentType": "reviewer",
            "description": "review PR #930 (slice #929)",
            "toolUseId": "toolu_rev_929",
        }, f)

    return main_path, session_id


# ---------------------------------------------------------------------------
# Group 1: FiringWhoFields — new fields present and non-empty on every dispatch
# ---------------------------------------------------------------------------

class TestFiringWhoFields(unittest.TestCase):
    """Every dispatch in build_firing_tree() must carry actor, tool_target, outcome."""

    def setUp(self):
        _inject_dashboard()
        import transcript as tr
        self._tr = tr
        self._tmpdir = Path(tempfile.mkdtemp())
        self._main_path, _ = _build_fixture_session(self._tmpdir)
        self._result = tr.build_firing_tree(self._main_path)

    def tearDown(self):
        shutil.rmtree(str(self._tmpdir), ignore_errors=True)

    def _all_dispatches(self):
        groups = self._result.get("groups", {})
        return [d for disps in groups.values() for d in disps]

    def test_result_is_dict(self):
        self.assertIsInstance(self._result, dict)

    def test_no_error(self):
        self.assertIsNone(self._result.get("error"),
                          f"Expected no error, got: {self._result.get('error')}")

    def test_dispatch_count_two(self):
        self.assertEqual(self._result.get("dispatch_count"), 2,
                         f"Expected 2 dispatches, got {self._result.get('dispatch_count')}")

    def test_actor_field_present_on_all(self):
        """AC #3: every firing row must expose a non-empty actor field."""
        for d in self._all_dispatches():
            self.assertIn("actor", d,
                          f"Dispatch missing 'actor' field: {d}")
            self.assertTrue(d["actor"],
                            f"Dispatch 'actor' must be non-empty: {d}")

    def test_tool_target_field_present_on_all(self):
        """AC #4: every firing row must expose a non-empty tool_target field."""
        for d in self._all_dispatches():
            self.assertIn("tool_target", d,
                          f"Dispatch missing 'tool_target' field: {d}")
            self.assertTrue(d["tool_target"],
                            f"Dispatch 'tool_target' must be non-empty: {d}")

    def test_outcome_field_present_on_all(self):
        """AC #5: every firing row must expose a non-empty outcome field."""
        for d in self._all_dispatches():
            self.assertIn("outcome", d,
                          f"Dispatch missing 'outcome' field: {d}")
            self.assertTrue(d["outcome"],
                            f"Dispatch 'outcome' must be non-empty: {d}")

    def test_implementer_outcome_is_success(self):
        """Implementer outcome must be SUCCESS (from RESULT trailer)."""
        disps = self._all_dispatches()
        impl = [d for d in disps if d.get("agent") == "implementer"]
        self.assertGreater(len(impl), 0, "Expected at least one implementer dispatch")
        self.assertEqual(impl[0]["outcome"], "SUCCESS",
                         f"Implementer outcome must be SUCCESS, got: {impl[0]['outcome']}")

    def test_reviewer_outcome_is_approve(self):
        """Reviewer outcome must be APPROVE (from VERDICT trailer)."""
        disps = self._all_dispatches()
        rev = [d for d in disps if d.get("agent") == "reviewer"]
        self.assertGreater(len(rev), 0, "Expected at least one reviewer dispatch")
        self.assertEqual(rev[0]["outcome"], "APPROVE",
                         f"Reviewer outcome must be APPROVE, got: {rev[0]['outcome']}")

    def test_tool_target_contains_issue_ref(self):
        """tool_target must contain an issue/PR reference (#N or PR #N)."""
        for d in self._all_dispatches():
            target = d.get("tool_target", "")
            has_ref = "#" in target
            self.assertTrue(has_ref,
                            f"tool_target should contain '#N' ref, got: '{target}'")


# ---------------------------------------------------------------------------
# Group 2: CompletenessCount — deduped count matches rendered rows
# ---------------------------------------------------------------------------

class TestCompletenessCount(unittest.TestCase):
    """completeness_count == deduped agent_start events from full transcript parse."""

    def setUp(self):
        _inject_dashboard()
        import transcript as tr
        self._tr = tr
        self._tmpdir = Path(tempfile.mkdtemp())
        self._main_path, _ = _build_fixture_session(self._tmpdir)
        self._result = tr.build_firing_tree(self._main_path)

    def tearDown(self):
        shutil.rmtree(str(self._tmpdir), ignore_errors=True)

    def test_completeness_count_key_present(self):
        """Result must include completeness_count key."""
        self.assertIn("completeness_count", self._result,
                      "build_firing_tree() result must have 'completeness_count' key")

    def test_completeness_count_is_int(self):
        """completeness_count must be an integer."""
        self.assertIsInstance(self._result["completeness_count"], int,
                              "'completeness_count' must be an int")

    def test_completeness_count_equals_dispatch_count(self):
        """AC #6: completeness_count (deduped transcript events) == dispatch_count (rendered rows).

        The fixture has exactly 2 Agent dispatches in the main transcript,
        both with distinct tool_use_ids.  The subagent transcripts do NOT
        repeat Agent dispatches, so deduped count == 2 == dispatch_count.
        """
        dispatch_count = self._result.get("dispatch_count", -1)
        completeness_count = self._result.get("completeness_count", -2)
        self.assertEqual(
            dispatch_count, completeness_count,
            f"AC #6: dispatch_count ({dispatch_count}) != completeness_count ({completeness_count})"
        )

    def test_completeness_no_double_count_from_subagents(self):
        """Subagent transcripts must not inflate completeness_count.

        The subagent JSONL files in the fixture have no Agent tool_use calls
        (only user+assistant records with text content).  The completeness_count
        must therefore equal 2 (one per main-transcript dispatch), not higher.
        """
        completeness_count = self._result.get("completeness_count", -1)
        self.assertEqual(completeness_count, 2,
                         f"Completeness count must be 2 (no inflation from subagents), got {completeness_count}")


# ---------------------------------------------------------------------------
# Group 3: OutcomeFallback — "dispatched" when no verdict recorded
# ---------------------------------------------------------------------------

class TestOutcomeFallback(unittest.TestCase):
    """When a subagent has no verdict yet, outcome must default to 'dispatched'."""

    def setUp(self):
        _inject_dashboard()
        import transcript as tr
        self._tr = tr

    def test_empty_subagent_gives_dispatched_outcome(self):
        """A subagent JSONL with no trailer text must yield outcome='dispatched'."""
        tmpdir = Path(tempfile.mkdtemp())
        try:
            session_id = "test-929-fallback"
            main_path = tmpdir / f"{session_id}.jsonl"
            sub_dir = tmpdir / session_id / "subagents"
            sub_dir.mkdir(parents=True, exist_ok=True)

            # Main transcript: one Agent dispatch
            with main_path.open("w", encoding="utf-8") as f:
                f.write(json.dumps({
                    "type": "assistant",
                    "uuid": "a-dispatch-1",
                    "parentUuid": None,
                    "timestamp": "2026-06-18T10:00:00.000Z",
                    "sessionId": session_id,
                    "message": {
                        "role": "assistant",
                        "content": [{
                            "type": "tool_use",
                            "id": "toolu_running_001",
                            "name": "Agent",
                            "input": {
                                "subagent_type": "implementer",
                                "description": "implementer for #999",
                                "prompt": "Implement slice #999",
                            },
                        }],
                    },
                }) + "\n")

            # Subagent JSONL: only a user prompt, no trailer (still running)
            sub_jsonl = sub_dir / "agent-running-hex.jsonl"
            with sub_jsonl.open("w", encoding="utf-8") as f:
                f.write(json.dumps({
                    "type": "user",
                    "uuid": "u-1",
                    "agentId": "agent-running-hex",
                    "timestamp": "2026-06-18T10:01:00.000Z",
                    "sessionId": session_id,
                    "message": {"role": "user", "content": [{"type": "text", "text": "start"}]},
                }) + "\n")

            with (sub_dir / "agent-running-hex.meta.json").open("w", encoding="utf-8") as f:
                json.dump({
                    "agentType": "implementer",
                    "description": "implementer for #999",
                    "toolUseId": "toolu_running_001",
                }, f)

            result = self._tr.build_firing_tree(main_path)
            groups = result.get("groups", {})
            all_disps = [d for disps in groups.values() for d in disps]
            self.assertGreater(len(all_disps), 0, "Expected at least one dispatch")
            d = all_disps[0]
            self.assertEqual(d.get("outcome"), "dispatched",
                             f"Expected outcome='dispatched' for no-verdict subagent, got: {d.get('outcome')}")
        finally:
            shutil.rmtree(str(tmpdir), ignore_errors=True)


# ---------------------------------------------------------------------------
# Group 4: ActorDerivation — orchestrator vs subagent-dispatched
# ---------------------------------------------------------------------------

class TestActorDerivation(unittest.TestCase):
    """actor == 'orchestrator' for main-transcript dispatches (no agentId)."""

    def setUp(self):
        _inject_dashboard()
        import transcript as tr
        self._tr = tr
        self._tmpdir = Path(tempfile.mkdtemp())
        self._main_path, _ = _build_fixture_session(self._tmpdir)
        self._result = tr.build_firing_tree(self._main_path)

    def tearDown(self):
        shutil.rmtree(str(self._tmpdir), ignore_errors=True)

    def _all_dispatches(self):
        groups = self._result.get("groups", {})
        return [d for disps in groups.values() for d in disps]

    def test_all_actors_non_empty(self):
        """Every dispatch must have a non-empty actor."""
        for d in self._all_dispatches():
            self.assertTrue(d.get("actor"),
                            f"actor must be non-empty for dispatch: {d}")

    def test_orchestrator_dispatches_have_orchestrator_actor(self):
        """Main-transcript dispatches (no agentId on the assistant record) must have actor='orchestrator'."""
        # The fixture's main transcript has no agentId on any record,
        # so all dispatches must be attributed to orchestrator.
        for d in self._all_dispatches():
            self.assertEqual(d.get("actor"), "orchestrator",
                             f"Expected actor='orchestrator', got: {d.get('actor')}")

    def test_helper_functions_exist(self):
        """transcript module must export _build_actor_map and _derive_tool_target."""
        import transcript as tr
        self.assertTrue(callable(getattr(tr, "_build_actor_map", None)),
                        "transcript must export _build_actor_map()")
        self.assertTrue(callable(getattr(tr, "_derive_tool_target", None)),
                        "transcript must export _derive_tool_target()")

    def test_count_transcript_firing_events_exists(self):
        """transcript module must export _count_transcript_firing_events()."""
        import transcript as tr
        self.assertTrue(callable(getattr(tr, "_count_transcript_firing_events", None)),
                        "transcript must export _count_transcript_firing_events()")


# ---------------------------------------------------------------------------
# Group 5: ServerRouteFields — static checks (no live bind)
# ---------------------------------------------------------------------------

class TestServerRouteFields(unittest.TestCase):
    """server.py and index.html wire up the new fields correctly."""

    def _server_src(self):
        return SERVER_PY.read_text(encoding="utf-8")

    def _index_src(self):
        return INDEX_HTML.read_text(encoding="utf-8")

    def test_server_has_session_firing_route(self):
        """server.py must still have /api/session-firing route."""
        self.assertIn('"/api/session-firing"', self._server_src(),
                      "server.py must have /api/session-firing route")

    def test_index_has_completeness_badge_class(self):
        """index.html must contain the firing-completeness-badge CSS class."""
        self.assertIn("firing-completeness-badge", self._index_src(),
                      "index.html must define firing-completeness-badge CSS class")

    def test_index_renders_actor_field(self):
        """index.html must reference 'actor' in the firing group renderer."""
        self.assertIn("firing-event-actor", self._index_src(),
                      "index.html must reference firing-event-actor CSS class")

    def test_index_renders_tool_target_field(self):
        """index.html must reference 'tool_target' in the firing group renderer."""
        self.assertIn("tool_target", self._index_src(),
                      "index.html must reference tool_target field in firing renderer")

    def test_index_renders_outcome_field(self):
        """index.html must reference 'outcome' in the firing group renderer."""
        self.assertIn("firing-event-outcome", self._index_src(),
                      "index.html must reference firing-event-outcome CSS class")

    def test_index_renders_completeness_count(self):
        """index.html must reference 'completeness_count' in the session-firing renderer."""
        self.assertIn("completeness_count", self._index_src(),
                      "index.html must reference completeness_count from API response")

    def test_transcript_module_exports_new_functions(self):
        """transcript.py must export _build_actor_map and _count_transcript_firing_events."""
        _inject_dashboard()
        import transcript as tr
        for fn in ("_build_actor_map", "_derive_tool_target", "_count_transcript_firing_events"):
            self.assertTrue(
                callable(getattr(tr, fn, None)),
                f"transcript.py must export {fn}()"
            )

    def test_build_firing_tree_returns_completeness_count(self):
        """build_firing_tree() must include completeness_count key in result."""
        _inject_dashboard()
        import transcript as tr
        # Use a path that doesn't exist — defensive path returns the key with 0
        from pathlib import Path as P
        import tempfile as _tmp
        ghost = P(_tmp.mktemp(suffix=".jsonl"))
        result = tr.build_firing_tree(ghost)
        self.assertIn("completeness_count", result,
                      "build_firing_tree() must include 'completeness_count' key even on error path")


if __name__ == "__main__":
    unittest.main()
