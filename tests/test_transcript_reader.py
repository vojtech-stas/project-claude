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


if __name__ == "__main__":
    unittest.main()
