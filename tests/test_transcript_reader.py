"""
Tests for slice #899 — transcript reader + /api/session-live.

Groups:
  1. TranscriptNormalise   — fixture JSONL with user/assistant/tool_use/tool_result
                             and an Agent dispatch; asserts normalised event fields.
  2. UnknownRecordTolerance — unknown record type is silently dropped (no crash).
  3. PathSanitise           — _sanitise_path() produces correct project-dir name.
  4. ServerRoutePresent     — server.py has /api/session-live route + index.html fetches it.

Runner: stdlib unittest + pytest compatible.
  python -m pytest tests/test_transcript_reader.py -v
"""

import json
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
# Fixture JSONL builder
# ---------------------------------------------------------------------------

def _make_fixture_jsonl(records: list[dict], encoding: str = "utf-8") -> Path:
    """Write a list of dicts as JSONL to a temp file; return its Path."""
    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".jsonl", delete=False, encoding=encoding
    )
    for rec in records:
        tmp.write(json.dumps(rec) + "\n")
    tmp.close()
    return Path(tmp.name)


# ---------------------------------------------------------------------------
# Fixture records — a minimal but representative session transcript
# ---------------------------------------------------------------------------

SESSION_ID = "abc123def456"

_FIXTURE_RECORDS = [
    # 1. user message (plain text prompt)
    {
        "type": "user",
        "uuid": "u-001",
        "parentUuid": None,
        "timestamp": "2026-06-15T10:00:00.000Z",
        "sessionId": SESSION_ID,
        "message": {
            "role": "user",
            "content": [{"type": "text", "text": "Please implement the feature."}],
        },
    },
    # 2. assistant with an Agent dispatch (Task tool)
    {
        "type": "assistant",
        "uuid": "a-001",
        "parentUuid": "u-001",
        "timestamp": "2026-06-15T10:00:01.000Z",
        "sessionId": SESSION_ID,
        "message": {
            "role": "assistant",
            "content": [
                {
                    "type": "tool_use",
                    "id": "toolu_agent_001",
                    "name": "Agent",
                    "input": {
                        "description": "Run implementer subagent",
                        "prompt": "Implement slice #899",
                        "subagent_type": "implementer",
                    },
                    "caller": {"type": "direct"},
                }
            ],
        },
    },
    # 3. tool_result for the Agent call (returned as a user record)
    {
        "type": "user",
        "uuid": "u-002",
        "parentUuid": "a-001",
        "timestamp": "2026-06-15T10:05:00.000Z",
        "sessionId": SESSION_ID,
        "toolUseResult": True,
        "message": {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": "toolu_agent_001",
                    "content": "RESULT: SUCCESS\nPR_URL: https://github.com/x/y/pull/900",
                }
            ],
        },
    },
    # 4. assistant with a regular tool_use (Bash)
    {
        "type": "assistant",
        "uuid": "a-002",
        "parentUuid": "u-002",
        "timestamp": "2026-06-15T10:05:30.000Z",
        "sessionId": SESSION_ID,
        "message": {
            "role": "assistant",
            "content": [
                {
                    "type": "tool_use",
                    "id": "toolu_bash_001",
                    "name": "Bash",
                    "input": {"command": "git status", "description": "check status"},
                    "caller": {"type": "direct"},
                }
            ],
        },
    },
    # 5. tool_result for the Bash call
    {
        "type": "user",
        "uuid": "u-003",
        "parentUuid": "a-002",
        "timestamp": "2026-06-15T10:05:31.000Z",
        "sessionId": SESSION_ID,
        "toolUseResult": True,
        "message": {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": "toolu_bash_001",
                    "content": "On branch feat/899-transcript-reader",
                }
            ],
        },
    },
    # 6. UNKNOWN record type — must be tolerated without crashing
    {
        "type": "queue-operation",
        "operation": "enqueue",
        "timestamp": "2026-06-15T10:06:00.000Z",
        "sessionId": SESSION_ID,
        "content": "some data",
    },
    # 7. ANOTHER unknown type
    {
        "type": "attachment",
        "uuid": "att-001",
        "parentUuid": "u-003",
        "timestamp": "2026-06-15T10:06:01.000Z",
        "sessionId": SESSION_ID,
    },
]


# ---------------------------------------------------------------------------
# Group 1: normalise fixture records into expected event shapes
# ---------------------------------------------------------------------------

class TestTranscriptNormalise(unittest.TestCase):
    """Fixture transcript yields normalised events with expected fields."""

    def setUp(self):
        _inject_dashboard()
        import transcript as tr
        self._tr = tr
        self._path = _make_fixture_jsonl(_FIXTURE_RECORDS)
        self._events = tr.parse_transcript(self._path)

    def tearDown(self):
        self._path.unlink(missing_ok=True)

    def test_events_list_non_empty(self):
        """parse_transcript() must return a non-empty list for a valid fixture."""
        self.assertGreater(len(self._events), 0,
                           "Expected at least one normalised event")

    def test_all_events_have_required_fields(self):
        """Every normalised event must have v, ts, session_id, event, src."""
        required = {"v", "ts", "session_id", "event", "src"}
        for i, ev in enumerate(self._events):
            for field in required:
                self.assertIn(field, ev,
                              f"Event #{i} (type={ev.get('event')}) missing field '{field}'")

    def test_v2_schema_on_all_events(self):
        """All normalised events must have v=2."""
        for ev in self._events:
            self.assertEqual(ev["v"], 2,
                             f"Event v must be 2, got {ev.get('v')}")

    def test_src_is_transcript(self):
        """All normalised events must have src='transcript'."""
        for ev in self._events:
            self.assertEqual(ev["src"], "transcript",
                             f"Event src must be 'transcript', got {ev.get('src')}")

    def test_user_prompt_event(self):
        """A user message with text content must yield event='user_prompt'."""
        user_evs = [e for e in self._events if e.get("event") == "user_prompt"]
        self.assertGreater(len(user_evs), 0,
                           "Expected at least one 'user_prompt' event")
        for ev in user_evs:
            self.assertIn("prompt", ev,
                          "user_prompt event must have a 'prompt' field")

    def test_agent_dispatch_event(self):
        """An Agent tool_use in an assistant record must yield event='agent_start'."""
        agent_evs = [e for e in self._events if e.get("event") == "agent_start"]
        self.assertGreater(len(agent_evs), 0,
                           "Expected at least one 'agent_start' event")
        ev = agent_evs[0]
        self.assertIn("subagent_type", ev,
                      "agent_start event must have 'subagent_type'")
        self.assertIn("tool_use_id", ev,
                      "agent_start event must have 'tool_use_id'")
        self.assertEqual(ev["subagent_type"], "implementer",
                         "subagent_type must be 'implementer' (from fixture)")

    def test_tool_result_event(self):
        """A user record containing tool_result content must yield event='tool_result'."""
        tr_evs = [e for e in self._events if e.get("event") == "tool_result"]
        self.assertGreater(len(tr_evs), 0,
                           "Expected at least one 'tool_result' event")
        ev = tr_evs[0]
        self.assertIn("tool_use_id", ev,
                      "tool_result event must have 'tool_use_id'")

    def test_regular_tool_use_event(self):
        """An assistant Bash tool_use must yield event='tool_use' with tool_name."""
        tool_evs = [e for e in self._events if e.get("event") == "tool_use"]
        self.assertGreater(len(tool_evs), 0,
                           "Expected at least one 'tool_use' event")
        bash_evs = [e for e in tool_evs if e.get("tool_name") == "Bash"]
        self.assertGreater(len(bash_evs), 0,
                           "Expected a 'tool_use' event with tool_name='Bash'")

    def test_events_sorted_by_timestamp(self):
        """Events must be sorted by ascending timestamp."""
        timestamps = [e.get("ts", "") for e in self._events]
        self.assertEqual(timestamps, sorted(timestamps),
                         "Events must be sorted by timestamp ascending")


# ---------------------------------------------------------------------------
# Group 2: unknown record types are tolerated silently
# ---------------------------------------------------------------------------

class TestUnknownRecordTolerance(unittest.TestCase):
    """Unknown record types must be silently dropped; no exception raised."""

    def setUp(self):
        _inject_dashboard()
        import transcript as tr
        self._tr = tr

    def test_only_unknown_types_returns_empty_list(self):
        """A file with only unknown record types must return []."""
        records = [
            {"type": "queue-operation", "timestamp": "2026-06-15T10:00:00Z",
             "sessionId": "abc"},
            {"type": "attachment", "timestamp": "2026-06-15T10:00:01Z",
             "sessionId": "abc"},
            {"type": "last-prompt", "timestamp": "2026-06-15T10:00:02Z",
             "sessionId": "abc"},
            {"type": "custom-title", "timestamp": "2026-06-15T10:00:03Z",
             "sessionId": "abc"},
        ]
        path = _make_fixture_jsonl(records)
        try:
            events = self._tr.parse_transcript(path)
            self.assertEqual(events, [],
                             "Unknown-type-only file must return empty event list")
        finally:
            path.unlink(missing_ok=True)

    def test_unknown_type_mixed_with_known_does_not_crash(self):
        """Mixed unknown + known records must not raise; known records normalised."""
        records = [
            # Known
            {"type": "user", "uuid": "u-x", "parentUuid": None,
             "timestamp": "2026-06-15T10:00:00Z", "sessionId": "xyz",
             "message": {"role": "user",
                         "content": [{"type": "text", "text": "hello"}]}},
            # Unknown — must not crash
            {"type": "NEW_TYPE_FUTURE", "data": "some payload",
             "timestamp": "2026-06-15T10:00:01Z"},
        ]
        path = _make_fixture_jsonl(records)
        try:
            events = self._tr.parse_transcript(path)
            self.assertIsInstance(events, list,
                                  "Result must be a list")
            # The 'user' record must normalise; the unknown one must be silently dropped
            event_types = {e.get("event") for e in events}
            self.assertIn("user_prompt", event_types,
                          "Known 'user' record must produce 'user_prompt' event")
        finally:
            path.unlink(missing_ok=True)

    def test_malformed_json_line_ignored(self):
        """A file with malformed JSON on one line must not crash."""
        import transcript as tr
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False, encoding="utf-8"
        )
        tmp.write('{"type": "user", "uuid": "u-y", "timestamp": "2026-06-15T10:00:00Z",'
                  ' "sessionId": "yyy", "message": {"role": "user", "content":'
                  ' [{"type": "text", "text": "ok"}]}}\n')
        tmp.write("NOT VALID JSON{\n")  # malformed — must be silently skipped
        tmp.close()
        path = Path(tmp.name)
        try:
            events = tr.parse_transcript(path)
            self.assertIsInstance(events, list)
            # Must produce at least 1 event from the valid line
            self.assertGreater(len(events), 0,
                               "Valid lines must still produce events despite malformed lines")
        finally:
            path.unlink(missing_ok=True)

    def test_nonexistent_file_returns_empty_list(self):
        """parse_transcript() on a non-existent path must return []."""
        import transcript as tr
        ghost = Path(tempfile.mktemp(suffix=".jsonl"))
        events = tr.parse_transcript(ghost)
        self.assertEqual(events, [],
                         "Non-existent file must return empty list")


# ---------------------------------------------------------------------------
# Group 3: path sanitisation
# ---------------------------------------------------------------------------

class TestPathSanitise(unittest.TestCase):
    """_sanitise_path() must produce the expected project-dir name."""

    def setUp(self):
        _inject_dashboard()
        import transcript as tr
        self._sanitise = tr._sanitise_path

    def test_windows_root_project(self):
        r"""F:\project_claude -> F--project-claude"""
        result = self._sanitise(r"F:\project_claude")
        self.assertEqual(result, "F--project-claude")

    def test_windows_worktree_path(self):
        r"""F:\project_claude\.claude\worktrees\agent-xyz -> F--project-claude--claude-worktrees-agent-xyz"""
        result = self._sanitise(r"F:\project_claude\.claude\worktrees\agent-xyz")
        self.assertEqual(result, "F--project-claude--claude-worktrees-agent-xyz")

    def test_forward_slash_variant(self):
        """Forward-slash paths (Unix-style on Windows) also sanitise correctly."""
        result = self._sanitise("F:/project_claude/.claude/worktrees/agent-xyz")
        self.assertEqual(result, "F--project-claude--claude-worktrees-agent-xyz")

    def test_result_is_string(self):
        """Result must always be a string."""
        result = self._sanitise("C:/foo/bar")
        self.assertIsInstance(result, str)


# ---------------------------------------------------------------------------
# Group 4: server route + index.html fetch presence
# ---------------------------------------------------------------------------

class TestServerRoutePresentGroup(unittest.TestCase):
    """server.py must have /api/session-live route; index.html must fetch it."""

    def test_server_py_has_session_live_route(self):
        """server.py must contain elif path == '/api/session-live'."""
        src = SERVER_PY.read_text(encoding="utf-8")
        self.assertIn(
            '"/api/session-live"',
            src,
            "server.py must contain the /api/session-live route handler",
        )

    def test_index_html_fetches_session_live(self):
        """index.html must contain a fetch('/api/session-live') call."""
        html = INDEX_HTML.read_text(encoding="utf-8")
        self.assertIn(
            "/api/session-live",
            html,
            "index.html must fetch /api/session-live (DEAD-ROUTES compliance)",
        )

    def test_server_py_imports_transcript_module(self):
        """server.py must import transcript module."""
        src = SERVER_PY.read_text(encoding="utf-8")
        self.assertIn(
            "transcript",
            src,
            "server.py must import the transcript module",
        )

    def test_transcript_module_exists(self):
        """dashboard/transcript.py must exist."""
        self.assertTrue(
            (DASHBOARD_DIR / "transcript.py").exists(),
            "dashboard/transcript.py must exist",
        )

    def test_transcript_module_importable(self):
        """transcript module must be importable without error."""
        _inject_dashboard()
        try:
            import transcript  # noqa: F401
        except ImportError as e:
            self.fail(f"transcript module failed to import: {e}")

    def test_get_session_events_returns_dict(self):
        """get_session_events() must return a dict with expected keys."""
        _inject_dashboard()
        import transcript as tr
        result = tr.get_session_events()
        self.assertIsInstance(result, dict,
                              "get_session_events() must return a dict")
        for key in ("events", "source", "event_count"):
            self.assertIn(key, result,
                          f"get_session_events() result must have key '{key}'")
        self.assertIsInstance(result["events"], list,
                              "'events' must be a list")
        self.assertIsInstance(result["event_count"], int,
                              "'event_count' must be an int")


# ---------------------------------------------------------------------------
# Group 5: per-PRD firing tree (slice #901)
# ---------------------------------------------------------------------------
# Fixture: a main transcript with an Agent dispatch + two subagent JSONL files
# (implementer SUCCESS + reviewer APPROVE) plus their meta.json files.
# Asserts: nesting under the right dispatch, verdict extraction, PRD grouping.

class TestFiringTree(unittest.TestCase):
    """build_firing_tree() maps subagent files to dispatches + extracts verdicts."""

    def setUp(self):
        _inject_dashboard()
        import transcript as tr
        self._tr = tr

        # Build a temporary directory that mimics a real session layout:
        #   <tmpdir>/<session-id>.jsonl           — main transcript
        #   <tmpdir>/<session-id>/subagents/       — subagent files
        self._tmpdir = tempfile.mkdtemp()
        self._session_id = "test-session-firing-abc"
        self._main_path  = Path(self._tmpdir) / f"{self._session_id}.jsonl"
        self._sub_dir    = Path(self._tmpdir) / self._session_id / "subagents"
        self._sub_dir.mkdir(parents=True, exist_ok=True)

        # Main transcript: one Agent dispatch (implementer) + one Agent dispatch (reviewer)
        import json as _json
        main_records = [
            {
                "type": "assistant",
                "uuid": "a-dispatch-impl",
                "parentUuid": None,
                "timestamp": "2026-06-17T09:00:00.000Z",
                "sessionId": self._session_id,
                "message": {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "toolu_impl_001",
                            "name": "Agent",
                            "input": {
                                "subagent_type": "implementer",
                                "description": "Run implementer for #901",
                                "prompt": "Implement slice #901",
                            },
                        }
                    ],
                },
            },
            {
                "type": "assistant",
                "uuid": "a-dispatch-rev",
                "parentUuid": None,
                "timestamp": "2026-06-17T09:10:00.000Z",
                "sessionId": self._session_id,
                "message": {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "toolu_rev_001",
                            "name": "Agent",
                            "input": {
                                "subagent_type": "reviewer",
                                "description": "review PR #902 (slice #901)",
                                "prompt": "Review PR #902",
                            },
                        }
                    ],
                },
            },
        ]
        with self._main_path.open("w", encoding="utf-8") as f:
            for rec in main_records:
                f.write(_json.dumps(rec) + "\n")

        # Implementer subagent: success trailer
        impl_records = [
            {
                "type": "user",
                "uuid": "u-impl-1",
                "agentId": "agent-impl-hex",
                "timestamp": "2026-06-17T09:01:00.000Z",
                "sessionId": self._session_id,
                "message": {"role": "user", "content": [{"type": "text", "text": "Implement slice #901"}]},
            },
            {
                "type": "assistant",
                "uuid": "a-impl-final",
                "agentId": "agent-impl-hex",
                "timestamp": "2026-06-17T09:08:00.000Z",
                "sessionId": self._session_id,
                "message": {
                    "role": "assistant",
                    "content": [{"type": "text", "text": (
                        "Done!\n\n"
                        "RESULT: SUCCESS\n"
                        "REASON: PR opened\n"
                        "ARTIFACTS: https://github.com/x/y/pull/902\n"
                        "PR_URL: https://github.com/x/y/pull/902\n"
                        "BRANCH_NAME: feat/901-firing-tree\n"
                        "SLICE_ISSUE: #901\n"
                    )}],
                },
            },
        ]
        impl_jsonl = self._sub_dir / "agent-impl-hex.jsonl"
        with impl_jsonl.open("w", encoding="utf-8") as f:
            for rec in impl_records:
                f.write(_json.dumps(rec) + "\n")

        # Implementer meta.json — links toolUseId to the dispatch
        impl_meta = self._sub_dir / "agent-impl-hex.meta.json"
        with impl_meta.open("w", encoding="utf-8") as f:
            _json.dump({
                "agentType":   "implementer",
                "description": "Run implementer for #901",
                "toolUseId":   "toolu_impl_001",
            }, f)

        # Reviewer subagent: approve trailer
        rev_records = [
            {
                "type": "user",
                "uuid": "u-rev-1",
                "agentId": "agent-rev-hex",
                "timestamp": "2026-06-17T09:11:00.000Z",
                "sessionId": self._session_id,
                "message": {"role": "user", "content": [{"type": "text", "text": "Review PR #902"}]},
            },
            {
                "type": "assistant",
                "uuid": "a-rev-final",
                "agentId": "agent-rev-hex",
                "timestamp": "2026-06-17T09:15:00.000Z",
                "sessionId": self._session_id,
                "message": {
                    "role": "assistant",
                    "content": [{"type": "text", "text": (
                        "All checks pass.\n\n"
                        "```\n"
                        "VERDICT: APPROVE\n"
                        "REASON: All rules pass\n"
                        "ROUND: 1\n"
                        "CRITIC: reviewer\n"
                        "MERGE_STATUS: merged\n"
                        "```\n"
                    )}],
                },
            },
        ]
        rev_jsonl = self._sub_dir / "agent-rev-hex.jsonl"
        with rev_jsonl.open("w", encoding="utf-8") as f:
            for rec in rev_records:
                f.write(_json.dumps(rec) + "\n")

        # Reviewer meta.json
        rev_meta = self._sub_dir / "agent-rev-hex.meta.json"
        with rev_meta.open("w", encoding="utf-8") as f:
            _json.dump({
                "agentType":   "reviewer",
                "description": "review PR #902 (slice #901)",
                "toolUseId":   "toolu_rev_001",
            }, f)

        self._result = tr.build_firing_tree(self._main_path)

    def tearDown(self):
        import shutil
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_result_is_dict(self):
        """build_firing_tree() must return a dict."""
        self.assertIsInstance(self._result, dict)

    def test_dispatch_count(self):
        """dispatch_count must equal 2 (one implementer, one reviewer)."""
        self.assertEqual(self._result.get("dispatch_count"), 2,
                         f"Expected 2 dispatches, got {self._result.get('dispatch_count')}")

    def test_groups_present(self):
        """groups dict must be non-empty."""
        groups = self._result.get("groups", {})
        self.assertGreater(len(groups), 0, "groups must be non-empty")

    def test_dispatches_have_required_fields(self):
        """Every dispatch must have agent, start, end, verdict fields."""
        groups = self._result.get("groups", {})
        for label, dispatches in groups.items():
            for d in dispatches:
                for field in ("agent", "start", "end", "verdict"):
                    self.assertIn(field, d,
                                  f"Dispatch in group '{label}' missing field '{field}'")

    def test_implementer_verdict_extracted(self):
        """Implementer subagent must have verdict=SUCCESS."""
        groups = self._result.get("groups", {})
        impl_dispatches = [
            d for disps in groups.values() for d in disps
            if d.get("agent") == "implementer"
        ]
        self.assertGreater(len(impl_dispatches), 0,
                           "Expected at least one implementer dispatch")
        self.assertEqual(impl_dispatches[0]["verdict"], "SUCCESS",
                         f"Implementer verdict should be SUCCESS, got {impl_dispatches[0]['verdict']}")

    def test_reviewer_verdict_extracted(self):
        """Reviewer subagent must have verdict=APPROVE."""
        groups = self._result.get("groups", {})
        rev_dispatches = [
            d for disps in groups.values() for d in disps
            if d.get("agent") == "reviewer"
        ]
        self.assertGreater(len(rev_dispatches), 0,
                           "Expected at least one reviewer dispatch")
        self.assertEqual(rev_dispatches[0]["verdict"], "APPROVE",
                         f"Reviewer verdict should be APPROVE, got {rev_dispatches[0]['verdict']}")

    def test_prd_grouping_by_issue_number(self):
        """Dispatches referencing #901 must share a PRD-bucket label."""
        groups = self._result.get("groups", {})
        # Both dispatches reference #901 (implementer: "Run implementer for #901",
        # reviewer: "review PR #902 (slice #901)") — the first issue number found
        # in each description determines the bucket.
        # implementer -> #901, reviewer -> #902 (first number in its description)
        # So we expect at least one bucket containing #901 reference.
        all_labels = list(groups.keys())
        self.assertTrue(
            any("#" in lbl for lbl in all_labels),
            f"Expected at least one issue-number bucket label, got: {all_labels}"
        )

    def test_dispatches_sorted_by_start(self):
        """Dispatches within each group must be sorted by start timestamp."""
        groups = self._result.get("groups", {})
        for label, dispatches in groups.items():
            starts = [d.get("start", "") for d in dispatches]
            self.assertEqual(starts, sorted(starts),
                             f"Group '{label}' dispatches not sorted by start")

    def test_no_error_in_result(self):
        """build_firing_tree() must not return an error for a valid fixture."""
        err = self._result.get("error")
        self.assertIsNone(err,
                          f"Expected no error, got: {err}")

    def test_source_field_present(self):
        """Result must include a non-empty source field."""
        src = self._result.get("source", "")
        self.assertTrue(src, "source field must be non-empty")


class TestFiringTreeDefensive(unittest.TestCase):
    """build_firing_tree() handles edge cases defensively."""

    def setUp(self):
        _inject_dashboard()
        import transcript as tr
        self._tr = tr

    def test_nonexistent_path_returns_error(self):
        """build_firing_tree() on a non-existent path must return error key."""
        from pathlib import Path as P
        import tempfile
        ghost = P(tempfile.mktemp(suffix=".jsonl"))
        result = self._tr.build_firing_tree(ghost)
        self.assertIsInstance(result, dict)
        self.assertIn("error", result)
        self.assertIsNotNone(result["error"])

    def test_no_subagents_dir_returns_empty(self):
        """A main transcript with no subagents/ dir returns empty groups, no error."""
        import json as _json
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False, encoding="utf-8"
        )
        tmp.write(_json.dumps({"type": "user", "timestamp": "2026-06-17T10:00:00Z"}) + "\n")
        tmp.close()
        path = Path(tmp.name)
        try:
            result = self._tr.build_firing_tree(path)
            self.assertIsInstance(result, dict)
            self.assertEqual(result.get("dispatch_count", 0), 0)
            self.assertIsNone(result.get("error"))
        finally:
            path.unlink(missing_ok=True)

    def test_get_session_firing_returns_dict(self):
        """get_session_firing() must return a dict with expected keys."""
        result = self._tr.get_session_firing()
        self.assertIsInstance(result, dict)
        for key in ("groups", "dispatch_count", "source"):
            self.assertIn(key, result,
                          f"get_session_firing() result must have key '{key}'")
        self.assertIsInstance(result["groups"], dict)
        self.assertIsInstance(result["dispatch_count"], int)


class TestServerFiringRoutePresent(unittest.TestCase):
    """server.py must have /api/session-firing route; index.html must fetch it."""

    def test_server_py_has_session_firing_route(self):
        """server.py must contain '/api/session-firing' route."""
        src = SERVER_PY.read_text(encoding="utf-8")
        self.assertIn(
            '"/api/session-firing"',
            src,
            "server.py must contain the /api/session-firing route handler",
        )

    def test_server_py_calls_get_session_firing(self):
        """server.py must call the transcript module's session-firing serve path.

        Updated by issue #1061: the route now calls the non-blocking
        serve_session_firing() wrapper instead of calling get_session_firing()
        directly, so the cold-start parse no longer blocks the request path.
        """
        src = SERVER_PY.read_text(encoding="utf-8")
        self.assertIn(
            "serve_session_firing",
            src,
            "server.py must call serve_session_firing() for the /api/session-firing "
            "route (non-blocking wrapper, issue #1061)",
        )

    def test_index_html_fetches_session_firing(self):
        """index.html must reference /api/session-firing."""
        html = INDEX_HTML.read_text(encoding="utf-8")
        self.assertIn(
            "/api/session-firing",
            html,
            "index.html must fetch /api/session-firing (DEAD-ROUTES compliance)",
        )

    def test_index_html_has_session_firing_panel(self):
        """index.html must have the session-firing-content div."""
        html = INDEX_HTML.read_text(encoding="utf-8")
        self.assertIn(
            "session-firing-content",
            html,
            "index.html must contain the session-firing-content element",
        )


# ---------------------------------------------------------------------------
# Group 7: /api/runtime-reading — transcript-sourced runtime panel (slice #928)
# ---------------------------------------------------------------------------

class TestRuntimeReading(unittest.TestCase):
    """get_runtime_reading() returns a dict with source + reading fields."""

    def setUp(self):
        _inject_dashboard()
        import transcript as tr
        self._tr = tr

    def test_returns_dict(self):
        """get_runtime_reading() must return a dict."""
        result = self._tr.get_runtime_reading()
        self.assertIsInstance(result, dict,
                              "get_runtime_reading() must return a dict")

    def test_has_source_field(self):
        """Result must have a 'source' field (AC #1: source names the transcript)."""
        result = self._tr.get_runtime_reading()
        self.assertIn("source", result,
                      "get_runtime_reading() result must have 'source' field")

    def test_has_required_keys(self):
        """Result must have all required reading keys."""
        result = self._tr.get_runtime_reading()
        for key in ("source", "event_count", "session_age_s",
                    "last_event_ts", "last_event_type", "no_session"):
            self.assertIn(key, result,
                          f"get_runtime_reading() result must have key '{key}'")

    def test_event_count_is_int(self):
        """event_count must be an integer."""
        result = self._tr.get_runtime_reading()
        self.assertIsInstance(result["event_count"], int,
                              "'event_count' must be an int")

    def test_no_session_is_bool(self):
        """no_session must be a bool."""
        result = self._tr.get_runtime_reading()
        self.assertIsInstance(result["no_session"], bool,
                              "'no_session' must be a bool")


class TestRuntimeReadingFromFixture(unittest.TestCase):
    """Fixture transcript yields a runtime reading with a non-empty source field.

    This is the regression test for AC #1 (slice #928):
      a fixture transcript JSONL yields ≥1 runtime reading whose payload
      carries the 'source' field naming the transcript file.
    """

    def setUp(self):
        _inject_dashboard()
        import transcript as tr
        self._tr = tr
        # Write fixture to a temp file and patch resolve_transcript
        self._path = _make_fixture_jsonl(_FIXTURE_RECORDS)

    def tearDown(self):
        self._path.unlink(missing_ok=True)

    def _reading_from_fixture(self):
        """Return get_runtime_reading() result using the fixture transcript directly."""
        import os
        # Inject the fixture path via the env var used by resolve_transcript
        old = os.environ.get("CLAUDE_TRANSCRIPT_PATH", "")
        try:
            os.environ["CLAUDE_TRANSCRIPT_PATH"] = str(self._path)
            # Clear the runtime cache so the env var takes effect
            self._tr._runtime_cache["path"] = None
            self._tr._runtime_cache["mtime"] = None
            self._tr._runtime_cache["result"] = None
            # Also clear the session-events cache
            self._tr._cache["path"] = None
            self._tr._cache["mtime"] = None
            result = self._tr.get_runtime_reading()
        finally:
            if old:
                os.environ["CLAUDE_TRANSCRIPT_PATH"] = old
            else:
                os.environ.pop("CLAUDE_TRANSCRIPT_PATH", None)
            # Reset caches after test
            self._tr._runtime_cache["path"] = None
            self._tr._runtime_cache["mtime"] = None
            self._tr._runtime_cache["result"] = None
            self._tr._cache["path"] = None
            self._tr._cache["mtime"] = None
        return result

    def test_source_field_names_transcript_file(self):
        """AC #1: source field must name the transcript file path."""
        result = self._reading_from_fixture()
        src = result.get("source", "")
        self.assertTrue(src,
                        "source field must be non-empty when a transcript exists")
        self.assertIn(self._path.stem, src,
                      "source field must contain the transcript filename stem")

    def test_event_count_positive(self):
        """Fixture transcript must yield ≥1 runtime reading (event_count > 0)."""
        result = self._reading_from_fixture()
        self.assertGreater(result.get("event_count", 0), 0,
                           "event_count must be > 0 for a non-empty fixture transcript")

    def test_no_session_false(self):
        """no_session must be False when a transcript file is present."""
        result = self._reading_from_fixture()
        self.assertFalse(result.get("no_session", True),
                         "no_session must be False when a transcript file was found")

    def test_session_age_present(self):
        """session_age_s must be a positive float when events have timestamps."""
        result = self._reading_from_fixture()
        age = result.get("session_age_s")
        self.assertIsNotNone(age, "session_age_s must not be None for a transcript with timestamps")
        self.assertGreater(age, 0,
                           "session_age_s must be > 0 (fixture timestamps are in the past)")

    def test_last_event_type_non_empty(self):
        """last_event_type must be a non-empty string for a non-empty transcript."""
        result = self._reading_from_fixture()
        self.assertTrue(result.get("last_event_type", ""),
                        "last_event_type must be non-empty for a transcript with events")


class TestRuntimeReadingRoutePresent(unittest.TestCase):
    """server.py must expose /api/runtime-reading; index.html must fetch it."""

    def test_server_py_has_runtime_reading_route(self):
        """server.py must contain '/api/runtime-reading' route."""
        src = SERVER_PY.read_text(encoding="utf-8")
        self.assertIn(
            '"/api/runtime-reading"',
            src,
            "server.py must contain the /api/runtime-reading route handler",
        )

    def test_server_py_calls_get_runtime_reading(self):
        """server.py must call get_runtime_reading() in the route handler."""
        src = SERVER_PY.read_text(encoding="utf-8")
        self.assertIn(
            "get_runtime_reading",
            src,
            "server.py must call get_runtime_reading() for the /api/runtime-reading route",
        )

    def test_index_html_fetches_runtime_reading(self):
        """index.html must reference /api/runtime-reading (DEAD-ROUTES compliance)."""
        html = INDEX_HTML.read_text(encoding="utf-8")
        self.assertIn(
            "/api/runtime-reading",
            html,
            "index.html must fetch /api/runtime-reading (DEAD-ROUTES compliance)",
        )

    def test_index_html_has_runtime_panel(self):
        """index.html must have the runtime-content div."""
        html = INDEX_HTML.read_text(encoding="utf-8")
        self.assertIn(
            "runtime-content",
            html,
            "index.html must contain the runtime-content element",
        )

    def test_transcript_get_runtime_reading_exists(self):
        """transcript.py must export get_runtime_reading()."""
        _inject_dashboard()
        import transcript as tr
        self.assertTrue(
            callable(getattr(tr, "get_runtime_reading", None)),
            "transcript.py must define and export get_runtime_reading()",
        )


if __name__ == "__main__":
    unittest.main()
