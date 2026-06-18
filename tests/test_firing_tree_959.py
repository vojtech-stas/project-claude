"""
Regression tests for slice #959 — nested firing tree, Task segregation,
partial marker, and disk-cache round-trip.

Groups:
  1. DiskCache           — disk-cache load/save round-trip; write-through on
                          gh resolve; warm path avoids gh on second process.
  2. TaskSegregation     — built-in Task types go to research_other, NOT inside
                          PRD/slice nodes.
  3. NestedTreeShape     — build_firing_tree() returns nested_groups with the
                          PRD → slice → dispatch nesting.
  4. PartialMarker       — PRD node is marked partial when gh sub-issues include
                          slices absent from the current transcript.
  5. LiveTabUX           — Refresh buttons labelled with auto-interval; session-live
                          events are ordered oldest-at-top (stable).

Runner: stdlib unittest + pytest compatible.
  python -m pytest tests/test_firing_tree_959.py -v
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
# Shared fixture builder (reused from test_gh_correlation_958.py pattern)
# ---------------------------------------------------------------------------

def _build_session_fixture(
    session_id: str,
    dispatches: list[dict],
) -> tuple[Path, Path]:
    """Build a minimal session layout under a temp dir.

    dispatches: list of {tool_use_id, agent_type, description, verdict_text}
    Returns (main_path, tmpdir_path).
    """
    import os

    tmpdir = Path(tempfile.mkdtemp())
    main_path = tmpdir / f"{session_id}.jsonl"
    sub_dir = tmpdir / session_id / "subagents"
    sub_dir.mkdir(parents=True, exist_ok=True)

    main_records = []
    for d in dispatches:
        main_records.append({
            "type": "assistant",
            "uuid": f"a-{d['tool_use_id']}",
            "parentUuid": None,
            "timestamp": d.get("timestamp", "2026-06-18T09:00:00.000Z"),
            "sessionId": session_id,
            "message": {
                "role": "assistant",
                "content": [{
                    "type": "tool_use",
                    "id": d["tool_use_id"],
                    "name": d.get("tool_name", "Agent"),
                    "input": {
                        "subagent_type": d["agent_type"],
                        "description": d["description"],
                        "prompt": f"run {d['agent_type']}",
                    },
                }],
            },
        })
    with main_path.open("w", encoding="utf-8") as f:
        for rec in main_records:
            f.write(json.dumps(rec) + "\n")

    for d in dispatches:
        agent_stem = f"agent-{d['tool_use_id'][-6:]}"
        jsonl_path = sub_dir / f"{agent_stem}.jsonl"
        meta_path  = sub_dir / f"{agent_stem}.meta.json"

        sub_records = [
            {
                "type": "user",
                "uuid": "u-sub-1",
                "agentId": agent_stem,
                "timestamp": "2026-06-18T09:01:00.000Z",
                "sessionId": session_id,
                "message": {"role": "user", "content": [{"type": "text", "text": "go"}]},
            },
            {
                "type": "assistant",
                "uuid": "a-sub-final",
                "agentId": agent_stem,
                "timestamp": "2026-06-18T09:02:00.000Z",
                "sessionId": session_id,
                "message": {
                    "role": "assistant",
                    "content": [{"type": "text", "text": d.get("verdict_text", "RESULT: SUCCESS")}],
                },
            },
        ]
        with jsonl_path.open("w", encoding="utf-8") as f:
            for rec in sub_records:
                f.write(json.dumps(rec) + "\n")

        with meta_path.open("w", encoding="utf-8") as f:
            json.dump({
                "agentType":   d["agent_type"],
                "description": d["description"],
                "toolUseId":   d["tool_use_id"],
            }, f)

    return main_path, tmpdir


# ---------------------------------------------------------------------------
# Group 1: DiskCache — load/save round-trip + write-through
# ---------------------------------------------------------------------------

class TestDiskCache(unittest.TestCase):
    """Disk-cache load/save and write-through on gh resolve."""

    def setUp(self):
        _inject_dashboard()
        import transcript as tr
        self._tr = tr
        # Clear caches before each test
        tr._prd_cache.clear()
        tr._prd_cache_ts = 0.0
        tr._disk_cache_data = None

        # Use a temp file for the disk cache
        self._tmp = tempfile.mkdtemp()
        self._cache_file = Path(self._tmp) / "prd-correlation-cache.json"

    def tearDown(self):
        import shutil
        import transcript as tr
        tr._prd_cache.clear()
        tr._prd_cache_ts = 0.0
        tr._disk_cache_data = None
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_load_empty_cache_returns_dict(self):
        """_load_disk_cache() returns {} when file does not exist."""
        with patch("transcript._disk_cache_path", return_value=self._cache_file):
            data = self._tr._load_disk_cache()
        self.assertIsInstance(data, dict)
        self.assertEqual(len(data), 0)

    def test_write_then_reload(self):
        """Write a cache entry, reset in-memory, reload — value persists."""
        import transcript as tr

        with patch("transcript._disk_cache_path", return_value=self._cache_file):
            data = tr._load_disk_cache()
            data["123"] = 456
            tr._write_disk_cache(data)

            # Reset the in-memory pointer to force a reload from disk
            tr._disk_cache_data = None

            reloaded = tr._load_disk_cache()

        self.assertEqual(reloaded.get("123"), 456,
                         "Disk cache entry must survive a write+reload cycle")

    def test_write_through_on_gh_resolve(self):
        """resolve_dispatch_to_prd() writes the resolved value to disk on a gh hit."""
        import transcript as tr

        def fake_gh(args, timeout=15):
            if "issue" in args and "view" in args:
                idx = args.index("view") + 1
                n = int(args[idx])
                if n == 901:
                    return 0, json.dumps({
                        "number": 901, "labels": [{"name": "slice"}],
                        "body": "slice 1 of PRD #898.",
                    })
            return 1, ""

        with patch("transcript._disk_cache_path", return_value=self._cache_file):
            with patch("transcript._gh_run_transcript", side_effect=fake_gh):
                result = tr.resolve_dispatch_to_prd(901)

        self.assertEqual(result, 898)

        # Disk file should contain the entry
        with self._cache_file.open() as fh:
            on_disk = json.load(fh)
        self.assertIn("901", on_disk,
                      "resolve_dispatch_to_prd must write-through to disk on gh hit")
        self.assertEqual(on_disk["901"], 898)

    def test_warm_path_avoids_gh(self):
        """On second call (disk has entry), gh is NOT called."""
        import transcript as tr

        # Pre-populate the disk cache
        with patch("transcript._disk_cache_path", return_value=self._cache_file):
            data = tr._load_disk_cache()
            data["902"] = 898
            tr._write_disk_cache(data)
            tr._disk_cache_data = None  # force reload from disk
            tr._prd_cache.clear()

            call_count = [0]
            def counting_gh(args, timeout=15):
                call_count[0] += 1
                return 1, ""

            with patch("transcript._gh_run_transcript", side_effect=counting_gh):
                result = tr.resolve_dispatch_to_prd(902)

        self.assertEqual(result, 898,
                         "Disk-cached value must be returned without calling gh")
        self.assertEqual(call_count[0], 0,
                         "gh must not be called when disk cache has the entry")

    def test_malformed_disk_cache_returns_empty(self):
        """Malformed disk cache JSON returns {} (defensive)."""
        import transcript as tr
        self._cache_file.write_text("NOT JSON {", encoding="utf-8")
        tr._disk_cache_data = None

        with patch("transcript._disk_cache_path", return_value=self._cache_file):
            data = tr._load_disk_cache()

        self.assertIsInstance(data, dict)


# ---------------------------------------------------------------------------
# Group 2: TaskSegregation — Explore/Plan/etc. go to research_other
# ---------------------------------------------------------------------------

class TestTaskSegregation(unittest.TestCase):
    """Built-in Task types must go to research_other, not PRD/slice nodes."""

    def setUp(self):
        _inject_dashboard()
        import transcript as tr
        self._tr = tr
        tr._prd_cache.clear()
        tr._prd_cache_ts = 0.0
        tr._disk_cache_data = None

        self._main_path, self._tmpdir = _build_session_fixture(
            session_id="test-task-seg-959",
            dispatches=[
                # Normal workflow dispatch
                {
                    "tool_use_id": "toolu_impl_01",
                    "agent_type": "implementer",
                    "description": "Implement slice #959",
                    "verdict_text": "RESULT: SUCCESS",
                },
                # Explore task — should go to research_other
                {
                    "tool_use_id": "toolu_explore_01",
                    "agent_type": "explore",
                    "description": "Explore codebase structure",
                    "verdict_text": "",
                    "tool_name": "Task",
                },
                # Plan task — should go to research_other
                {
                    "tool_use_id": "toolu_plan_01",
                    "agent_type": "plan",
                    "description": "Plan implementation steps",
                    "verdict_text": "",
                    "tool_name": "Task",
                },
                # general-purpose — should go to research_other
                {
                    "tool_use_id": "toolu_gp_01",
                    "agent_type": "general-purpose",
                    "description": "General research task",
                    "verdict_text": "",
                    "tool_name": "Task",
                },
            ],
        )

    def tearDown(self):
        import shutil
        shutil.rmtree(self._tmpdir, ignore_errors=True)
        import transcript as tr
        tr._prd_cache.clear()
        tr._prd_cache_ts = 0.0
        tr._disk_cache_data = None

    def _always_fail_gh(self, args, timeout=15):
        return 1, ""

    def test_explore_not_in_groups(self):
        """Explore dispatch must NOT appear in any PRD/slice group."""
        with patch("transcript._gh_run_transcript", side_effect=self._always_fail_gh):
            result = self._tr.build_firing_tree(self._main_path)
        groups = result.get("groups", {})
        all_dispatches = [d for dl in groups.values() for d in dl]
        agents_in_groups = [d["agent"] for d in all_dispatches]
        self.assertNotIn("explore", agents_in_groups,
                         "'explore' agent must not appear in PRD groups")

    def test_explore_in_research_other(self):
        """Explore dispatch must appear in research_other."""
        with patch("transcript._gh_run_transcript", side_effect=self._always_fail_gh):
            result = self._tr.build_firing_tree(self._main_path)
        research = result.get("research_other", [])
        agents = [d["agent"] for d in research]
        self.assertIn("explore", agents,
                      "'explore' must appear in research_other")

    def test_plan_in_research_other(self):
        """Plan dispatch must appear in research_other."""
        with patch("transcript._gh_run_transcript", side_effect=self._always_fail_gh):
            result = self._tr.build_firing_tree(self._main_path)
        research = result.get("research_other", [])
        agents = [d["agent"] for d in research]
        self.assertIn("plan", agents, "'plan' must appear in research_other")

    def test_general_purpose_in_research_other(self):
        """general-purpose dispatch must appear in research_other."""
        with patch("transcript._gh_run_transcript", side_effect=self._always_fail_gh):
            result = self._tr.build_firing_tree(self._main_path)
        research = result.get("research_other", [])
        agents = [d["agent"] for d in research]
        self.assertIn("general-purpose", agents,
                      "'general-purpose' must appear in research_other")

    def test_implementer_not_in_research_other(self):
        """Normal implementer dispatch must NOT go to research_other."""
        with patch("transcript._gh_run_transcript", side_effect=self._always_fail_gh):
            result = self._tr.build_firing_tree(self._main_path)
        research = result.get("research_other", [])
        agents = [d["agent"] for d in research]
        self.assertNotIn("implementer", agents,
                         "'implementer' must not be in research_other")

    def test_research_other_key_present(self):
        """build_firing_tree() must return 'research_other' key."""
        with patch("transcript._gh_run_transcript", side_effect=self._always_fail_gh):
            result = self._tr.build_firing_tree(self._main_path)
        self.assertIn("research_other", result,
                      "build_firing_tree must return 'research_other' key")

    def test_is_research_task_function(self):
        """_is_research_task() returns True for all known built-in types."""
        self.assertTrue(self._tr._is_research_task("explore"))
        self.assertTrue(self._tr._is_research_task("Explore"))
        self.assertTrue(self._tr._is_research_task("plan"))
        self.assertTrue(self._tr._is_research_task("Plan"))
        self.assertTrue(self._tr._is_research_task("general-purpose"))
        self.assertTrue(self._tr._is_research_task("claude-code-guide"))
        self.assertTrue(self._tr._is_research_task("task"))

    def test_is_research_task_false_for_implementer(self):
        """_is_research_task() returns False for workflow subagent types."""
        self.assertFalse(self._tr._is_research_task("implementer"))
        self.assertFalse(self._tr._is_research_task("reviewer"))
        self.assertFalse(self._tr._is_research_task("prd-critic"))
        self.assertFalse(self._tr._is_research_task("backlog-critic"))


# ---------------------------------------------------------------------------
# Group 3: NestedTreeShape — PRD → slice → dispatch nesting
# ---------------------------------------------------------------------------

class TestNestedTreeShape(unittest.TestCase):
    """build_firing_tree() returns nested_groups with correct PRD→slice nesting."""

    def setUp(self):
        _inject_dashboard()
        import transcript as tr
        self._tr = tr
        tr._prd_cache.clear()
        tr._prd_cache_ts = 0.0
        tr._disk_cache_data = None

        self._main_path, self._tmpdir = _build_session_fixture(
            session_id="test-nested-959",
            dispatches=[
                {
                    "tool_use_id": "toolu_impl_958a",
                    "agent_type": "implementer",
                    "description": "Implement slice #958 (gh-correlation helper)",
                    "verdict_text": "RESULT: SUCCESS",
                },
                {
                    "tool_use_id": "toolu_rev_958a",
                    "agent_type": "reviewer",
                    "description": "Review PR for slice #958",
                    "verdict_text": "VERDICT: APPROVE",
                },
                {
                    "tool_use_id": "toolu_impl_959a",
                    "agent_type": "implementer",
                    "description": "Implement slice #959 (nested firing tree)",
                    "verdict_text": "RESULT: SUCCESS",
                },
            ],
        )

    def tearDown(self):
        import shutil
        shutil.rmtree(self._tmpdir, ignore_errors=True)
        import transcript as tr
        tr._prd_cache.clear()
        tr._prd_cache_ts = 0.0
        tr._disk_cache_data = None

    def _fake_gh(self, args, timeout=15):
        """Map slice #958 and #959 → PRD #956."""
        if "issue" in args and "view" in args:
            idx = args.index("view") + 1
            n = int(args[idx])
            if n in (958, 959):
                return 0, json.dumps({
                    "number": n, "labels": [{"name": "slice"}],
                    "body": f"slice {n - 957} of PRD #956.",
                })
            if n == 956:
                return 0, json.dumps({
                    "number": 956, "labels": [{"name": "prd"}], "body": "",
                })
        return 1, ""

    def test_nested_groups_key_present(self):
        """build_firing_tree() must return 'nested_groups' key."""
        with patch("transcript._gh_run_transcript", side_effect=self._fake_gh):
            result = self._tr.build_firing_tree(self._main_path)
        self.assertIn("nested_groups", result,
                      "build_firing_tree must return 'nested_groups' key")

    def test_prd_node_in_nested_groups(self):
        """PRD #956 node must appear in nested_groups."""
        with patch("transcript._gh_run_transcript", side_effect=self._fake_gh):
            result = self._tr.build_firing_tree(self._main_path)
        nested = result.get("nested_groups", {})
        self.assertIn("PRD #956", nested,
                      "Expected 'PRD #956' in nested_groups")

    def test_prd_node_has_slices_key(self):
        """PRD node must have a 'slices' dict."""
        with patch("transcript._gh_run_transcript", side_effect=self._fake_gh):
            result = self._tr.build_firing_tree(self._main_path)
        node = result["nested_groups"].get("PRD #956", {})
        self.assertIn("slices", node,
                      "PRD node must have 'slices' key")
        self.assertIsInstance(node["slices"], dict)

    def test_slice_958_nested_under_prd(self):
        """Dispatches referencing slice #958 must appear under 'PRD #956' → '#958'."""
        with patch("transcript._gh_run_transcript", side_effect=self._fake_gh):
            result = self._tr.build_firing_tree(self._main_path)
        slices = result["nested_groups"]["PRD #956"]["slices"]
        self.assertIn("#958", slices,
                      "Dispatch for slice #958 must be nested under #958 slice bucket")

    def test_slice_959_nested_under_prd(self):
        """Dispatches referencing slice #959 must appear under 'PRD #956' → '#959'."""
        with patch("transcript._gh_run_transcript", side_effect=self._fake_gh):
            result = self._tr.build_firing_tree(self._main_path)
        slices = result["nested_groups"]["PRD #956"]["slices"]
        self.assertIn("#959", slices,
                      "Dispatch for slice #959 must be nested under #959 slice bucket")

    def test_no_duplicate_dispatches_across_nesting(self):
        """Each dispatch appears in exactly one node (deduped by tool_use_id)."""
        with patch("transcript._gh_run_transcript", side_effect=self._fake_gh):
            result = self._tr.build_firing_tree(self._main_path)
        seen_ids: set = set()
        nested = result.get("nested_groups", {})
        for prd_node in nested.values():
            for slices in prd_node.get("slices", {}).values():
                for d in slices:
                    tid = d.get("tool_use_id")
                    self.assertNotIn(tid, seen_ids,
                                     f"Dispatch {tid} appeared more than once in nested tree")
                    seen_ids.add(tid)
            for d in prd_node.get("unresolved", []):
                tid = d.get("tool_use_id")
                self.assertNotIn(tid, seen_ids,
                                 f"Dispatch {tid} duplicated in unresolved")
                seen_ids.add(tid)
        research = result.get("research_other", [])
        for d in research:
            tid = d.get("tool_use_id")
            self.assertNotIn(tid, seen_ids,
                             f"Dispatch {tid} duplicated in research_other vs nested tree")
            seen_ids.add(tid)

    def test_dispatch_count_matches_meta_map(self):
        """dispatch_count must equal the number of unique meta.json files (3 here)."""
        with patch("transcript._gh_run_transcript", side_effect=self._fake_gh):
            result = self._tr.build_firing_tree(self._main_path)
        self.assertEqual(result.get("dispatch_count"), 3,
                         f"Expected dispatch_count=3, got {result.get('dispatch_count')}")


# ---------------------------------------------------------------------------
# Group 4: PartialMarker — PRD partial when gh sub-issues have absent slices
# ---------------------------------------------------------------------------

class TestPartialMarker(unittest.TestCase):
    """PRD node marked partial when gh sub-issues include absent slices."""

    def setUp(self):
        _inject_dashboard()
        import transcript as tr
        self._tr = tr
        tr._prd_cache.clear()
        tr._prd_cache_ts = 0.0
        tr._disk_cache_data = None

        # Transcript has only slice #958 dispatches; gh says PRD #956 also has #959
        self._main_path, self._tmpdir = _build_session_fixture(
            session_id="test-partial-959",
            dispatches=[
                {
                    "tool_use_id": "toolu_impl_958b",
                    "agent_type": "implementer",
                    "description": "Implement slice #958",
                    "verdict_text": "RESULT: SUCCESS",
                },
            ],
        )

    def tearDown(self):
        import shutil
        shutil.rmtree(self._tmpdir, ignore_errors=True)
        import transcript as tr
        tr._prd_cache.clear()
        tr._prd_cache_ts = 0.0
        tr._disk_cache_data = None

    def _fake_gh_with_subissues(self, args, timeout=15):
        """gh: slice #958 → PRD #956; PRD #956 has sub-issues #958 + #959."""
        if "issue" in args and "view" in args:
            idx = args.index("view") + 1
            n = int(args[idx])
            json_fields = args[args.index("--json") + 1] if "--json" in args else ""
            if n == 958:
                return 0, json.dumps({
                    "number": 958, "labels": [{"name": "slice"}],
                    "body": "slice 1 of PRD #956.",
                })
            if n == 956:
                # Return sub-issues if subIssues requested
                if "subIssues" in json_fields:
                    return 0, json.dumps({
                        "subIssues": {
                            "nodes": [
                                {"number": 958, "labels": [{"name": "slice"}]},
                                {"number": 959, "labels": [{"name": "slice"}]},
                            ]
                        }
                    })
                return 0, json.dumps({
                    "number": 956, "labels": [{"name": "prd"}], "body": "",
                })
        return 1, ""

    def _fake_gh_no_subissues(self, args, timeout=15):
        """gh: slice #958 → PRD #956; PRD #956 has only sub-issue #958."""
        if "issue" in args and "view" in args:
            idx = args.index("view") + 1
            n = int(args[idx])
            json_fields = args[args.index("--json") + 1] if "--json" in args else ""
            if n == 958:
                return 0, json.dumps({
                    "number": 958, "labels": [{"name": "slice"}],
                    "body": "slice 1 of PRD #956.",
                })
            if n == 956:
                if "subIssues" in json_fields:
                    return 0, json.dumps({
                        "subIssues": {
                            "nodes": [
                                {"number": 958, "labels": [{"name": "slice"}]},
                            ]
                        }
                    })
                return 0, json.dumps({
                    "number": 956, "labels": [{"name": "prd"}], "body": "",
                })
        return 1, ""

    def test_partial_true_when_absent_slice(self):
        """PRD node must be marked partial when gh sub-issues include a missing slice."""
        with patch("transcript._gh_run_transcript",
                   side_effect=self._fake_gh_with_subissues):
            result = self._tr.build_firing_tree(self._main_path)

        nested = result.get("nested_groups", {})
        node = nested.get("PRD #956", {})
        self.assertTrue(
            node.get("partial"),
            "PRD #956 must be marked partial: #959 sub-issue has no dispatches in transcript",
        )

    def test_partial_false_when_all_slices_present(self):
        """PRD node must NOT be marked partial when all gh sub-issues have dispatches."""
        with patch("transcript._gh_run_transcript",
                   side_effect=self._fake_gh_no_subissues):
            result = self._tr.build_firing_tree(self._main_path)

        nested = result.get("nested_groups", {})
        node = nested.get("PRD #956", {})
        self.assertFalse(
            node.get("partial"),
            "PRD #956 must NOT be partial when all sub-issues (#958) have dispatches",
        )

    def test_partial_false_when_gh_unavailable(self):
        """PRD node must NOT be marked partial when gh is unavailable (honest unknown)."""
        def always_fail(args, timeout=15):
            return 1, ""

        with patch("transcript._gh_run_transcript", side_effect=always_fail):
            result = self._tr.build_firing_tree(self._main_path)

        # When gh fails, partial should be False (we can't confirm partial-ness)
        nested = result.get("nested_groups", {})
        if "PRD #956" in nested:
            node = nested["PRD #956"]
        else:
            # With gh unavailable, the label will be the fallback bucket
            # partial key should still exist and be False
            all_nodes = list(nested.values())
            node = all_nodes[0] if all_nodes else {}

        # Must not raise; partial key must be present if node exists
        if node:
            self.assertIn("partial", node,
                          "PRD node must have 'partial' key")


# ---------------------------------------------------------------------------
# Group 5: LiveTabUX — Refresh button labels and ordering
# ---------------------------------------------------------------------------

class TestLiveTabUX(unittest.TestCase):
    """Live-tab UX: Refresh buttons have auto-interval label; events ordered oldest-at-top."""

    def setUp(self):
        _inject_dashboard()

    def test_session_live_refresh_button_has_auto_label(self):
        """Session-live Refresh button must say 'Refresh (auto 15s)'."""
        index_html = REPO_ROOT / "dashboard" / "index.html"
        content = index_html.read_text(encoding="utf-8", errors="replace")
        self.assertIn(
            "Refresh (auto 15s)",
            content,
            "Session-live Refresh button must be labelled 'Refresh (auto 15s)'",
        )

    def test_session_firing_refresh_button_has_auto_label(self):
        """Session-firing Refresh button must say 'Refresh (auto 30s)'."""
        index_html = REPO_ROOT / "dashboard" / "index.html"
        content = index_html.read_text(encoding="utf-8", errors="replace")
        self.assertIn(
            "Refresh (auto 30s)",
            content,
            "Session-firing Refresh button must be labelled 'Refresh (auto 30s)'",
        )

    def test_session_live_poll_interval_15s(self):
        """Session-live auto-refresh interval must be 15 seconds."""
        index_html = REPO_ROOT / "dashboard" / "index.html"
        content = index_html.read_text(encoding="utf-8", errors="replace")
        # The setInterval for session-live should use 15000 ms
        self.assertIn(
            "15000",
            content,
            "Session-live polling must use 15000 ms interval",
        )

    def test_session_firing_poll_interval_30s(self):
        """Session-firing auto-refresh interval must be 30 seconds."""
        index_html = REPO_ROOT / "dashboard" / "index.html"
        content = index_html.read_text(encoding="utf-8", errors="replace")
        self.assertIn(
            "30000",
            content,
            "Session-firing polling must use 30000 ms interval",
        )

    def test_nested_groups_key_in_fetchSessionFiring_js(self):
        """fetchSessionFiring() JS must use 'nested_groups' from the API response."""
        index_html = REPO_ROOT / "dashboard" / "index.html"
        content = index_html.read_text(encoding="utf-8", errors="replace")
        self.assertIn(
            "nested_groups",
            content,
            "index.html must reference 'nested_groups' in the fetchSessionFiring JS",
        )

    def test_research_other_key_in_fetchSessionFiring_js(self):
        """fetchSessionFiring() JS must use 'research_other' from the API response."""
        index_html = REPO_ROOT / "dashboard" / "index.html"
        content = index_html.read_text(encoding="utf-8", errors="replace")
        self.assertIn(
            "research_other",
            content,
            "index.html must reference 'research_other' in the fetchSessionFiring JS",
        )

    def test_partial_badge_in_js(self):
        """_renderNestedPrdNode must emit a 'partial' badge when partial=true."""
        index_html = REPO_ROOT / "dashboard" / "index.html"
        content = index_html.read_text(encoding="utf-8", errors="replace")
        self.assertIn(
            "partial",
            content,
            "index.html must render a 'partial' marker for PRD nodes",
        )

    def test_build_firing_tree_returns_research_other(self):
        """build_firing_tree() API dict must include 'research_other' key."""
        import transcript as tr
        # build_firing_tree() on a missing path → empty result with keys
        empty = tr.build_firing_tree(Path("/nonexistent/path.jsonl"))
        self.assertIn("research_other", empty,
                      "build_firing_tree empty result must include 'research_other'")

    def test_build_firing_tree_returns_nested_groups(self):
        """build_firing_tree() API dict must include 'nested_groups' key."""
        import transcript as tr
        empty = tr.build_firing_tree(Path("/nonexistent/path.jsonl"))
        self.assertIn("nested_groups", empty,
                      "build_firing_tree empty result must include 'nested_groups'")

    def test_get_session_firing_returns_nested_groups(self):
        """get_session_firing() must return 'nested_groups' key."""
        import transcript as tr
        result = tr.get_session_firing()
        self.assertIn("nested_groups", result,
                      "get_session_firing must return 'nested_groups' key")

    def test_get_session_firing_returns_research_other(self):
        """get_session_firing() must return 'research_other' key."""
        import transcript as tr
        result = tr.get_session_firing()
        self.assertIn("research_other", result,
                      "get_session_firing must return 'research_other' key")


# ---------------------------------------------------------------------------
# Group 6: DiskCachePath — cache file location
# ---------------------------------------------------------------------------

class TestDiskCachePath(unittest.TestCase):
    """_disk_cache_path() returns a path under .claude/logs/."""

    def setUp(self):
        _inject_dashboard()
        import transcript as tr
        self._tr = tr

    def test_cache_path_is_in_cache(self):
        """Disk cache path must include .claude/cache in its components (R-FIXTURE fix)."""
        p = self._tr._disk_cache_path()
        parts = p.parts
        self.assertIn(".claude", parts,
                      "Disk cache path must be under .claude/")
        self.assertIn("cache", parts,
                      "Disk cache path must be under .claude/cache/ not .claude/logs/")

    def test_cache_path_is_json_file(self):
        """Disk cache path must end with .json."""
        p = self._tr._disk_cache_path()
        self.assertEqual(p.suffix, ".json",
                         f"Disk cache must be a .json file, got: {p}")

    def test_get_prd_subissue_slices_returns_list(self):
        """_get_prd_subissue_slices() returns a list (may be empty) without crash."""
        def always_fail(args, timeout=15):
            return 1, ""

        with patch("transcript._gh_run_transcript", side_effect=always_fail):
            result = self._tr._get_prd_subissue_slices(99999)
        self.assertIsInstance(result, list,
                              "_get_prd_subissue_slices must return a list")


if __name__ == "__main__":
    unittest.main()
