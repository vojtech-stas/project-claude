"""
Regression test for slice #1056 — 'auto'-named hook entries read fire_count=0
because of an event-type classification gap in discovery.py.

Root cause (per #1056 body + investigation):
  - .claude/settings.json registers TWO hooks with the literal CLI argument
    "auto" passed to log-tool-event.sh:
      PreToolUse  matcher "Agent|Skill"                       -> auto
      PostToolUse matcher "Agent|Bash|AskUserQuestion|Edit|MultiEdit|Write" -> auto
  - discovery.py::_event_type_from_cmd() extracts that literal CLI argument
    ("auto") and uses it as the telemetry aggregation key.
  - But log-tool-event.sh's AUTO-MODE (see .claude/hooks/log-tool-event.sh)
    derives the REAL event_type at runtime from the payload's
    hook_event_name + tool_name (agent_start, skill_invoke, agent_complete,
    bash_complete, grill_qa, post_tool, ...) and beacons using THAT derived
    name, not the literal "auto" argument. So a beacon line carrying key
    "hook":"auto" is never written for status ok/error — the classifier's
    key ("auto") and the beacon's real key (e.g. "agent_start") never match,
    so discover_hooks() reports fire_count=0 for both auto-registered
    entries even when their beacons are present in hook-fires.jsonl under
    the derived names.

Fix: classification must map an "auto" hook's (event, matcher) pair to the
SAME set of derived keys log-tool-event.sh's auto-mode would produce, and
discover_hooks() must aggregate (sum fire_count/error_count, max last_fired)
across that whole set for that hook entry.

FAILS before the fix: both auto entries report fire_count == 0 even though
matching derived-key beacons exist in the fixture log.
PASSES after the fix: both auto entries report fire_count >= 1, summed from
their respective derived-key beacons.

Runner: stdlib unittest + pytest compatible.
  python -m pytest tests/test_auto_hook_classification_1056.py -q
"""

import importlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).parent.parent
DASHBOARD_DIR = REPO_ROOT / "dashboard"

if str(DASHBOARD_DIR) not in sys.path:
    sys.path.insert(0, str(DASHBOARD_DIR))


def _import_fresh(mod_name: str, filename: str):
    """Import (or re-import) a dashboard module fresh so monkeypatching works cleanly."""
    if mod_name in sys.modules:
        del sys.modules[mod_name]
    spec = importlib.util.spec_from_file_location(mod_name, DASHBOARD_DIR / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# Settings fixture: mirrors the real .claude/settings.json shape for the two
# "auto"-registered hook entries implicated by #1056.
SETTINGS_JSON = json.dumps({
    "hooks": {
        "PreToolUse": [
            {
                "matcher": "Agent|Skill",
                "hooks": [
                    {
                        "type": "command",
                        "command": 'bash ".claude/hooks/log-tool-event.sh" auto',
                    }
                ],
            }
        ],
        "PostToolUse": [
            {
                "matcher": "Agent|Bash|AskUserQuestion|Edit|MultiEdit|Write",
                "hooks": [
                    {
                        "type": "command",
                        "command": 'bash ".claude/hooks/log-tool-event.sh" auto',
                    }
                ],
            }
        ],
    }
})

# Beacon fixture: carries the DERIVED keys log-tool-event.sh's auto-mode
# actually writes (never the literal "auto" key) for status=ok/error.
BEACON_LINES = "\n".join([
    json.dumps({"hook": "agent_start", "status": "attempt", "ts": "2026-07-02T10:00:00Z"}),
    json.dumps({"hook": "agent_start", "status": "ok", "ts": "2026-07-02T10:00:00Z"}),
    json.dumps({"hook": "skill_invoke", "status": "attempt", "ts": "2026-07-02T10:01:00Z"}),
    json.dumps({"hook": "skill_invoke", "status": "ok", "ts": "2026-07-02T10:01:00Z"}),
    json.dumps({"hook": "agent_complete", "status": "attempt", "ts": "2026-07-02T10:02:00Z"}),
    json.dumps({"hook": "agent_complete", "status": "ok", "ts": "2026-07-02T10:02:00Z"}),
    json.dumps({"hook": "bash_complete", "status": "attempt", "ts": "2026-07-02T10:03:00Z"}),
    json.dumps({"hook": "bash_complete", "status": "ok", "ts": "2026-07-02T10:03:00Z"}),
]) + "\n"


class TestAutoHookClassification1056(unittest.TestCase):
    """
    Core regression: both "auto"-registered hook entries must aggregate
    fire_count from the DERIVED event-type keys their beacons actually
    carry, not from the literal "auto" CLI argument.
    """

    def setUp(self):
        self._orig_path = sys.path[:]

    def tearDown(self):
        sys.path[:] = self._orig_path
        sys.modules.pop("discovery", None)
        sys.modules.pop("telemetry_root", None)

    def _build_fixture(self, tmp_path):
        root = tmp_path / "repo"
        (root / ".claude" / "hooks").mkdir(parents=True)
        (root / ".claude" / "logs").mkdir(parents=True)
        (root / ".claude" / "settings.json").write_text(SETTINGS_JSON, encoding="utf-8")
        (root / ".claude" / "logs" / "hook-fires.jsonl").write_text(BEACON_LINES, encoding="utf-8")
        return root

    def test_both_auto_entries_aggregate_their_derived_beacons(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            root = self._build_fixture(tmp_path)

            telemetry_root_mod = _import_fresh("telemetry_root", "telemetry_root.py")
            discovery_mod = _import_fresh("discovery", "discovery.py")

            with patch.object(discovery_mod, "_DISCOVERY_REPO_ROOT", root), \
                 patch.object(telemetry_root_mod, "_telemetry_log_root", lambda: root):
                if hasattr(discovery_mod, "_telemetry_log_root"):
                    with patch.object(discovery_mod, "_telemetry_log_root", lambda: root):
                        hooks = discovery_mod.discover_hooks()
                else:
                    hooks = discovery_mod.discover_hooks()

            self.assertTrue(hooks, "discover_hooks() returned no hooks — settings.json fixture not read")

            pre_auto = [h for h in hooks if h.get("event") == "PreToolUse"]
            post_auto = [h for h in hooks if h.get("event") == "PostToolUse"]
            self.assertTrue(pre_auto, "expected a PreToolUse auto hook entry")
            self.assertTrue(post_auto, "expected a PostToolUse auto hook entry")

            pre_hook = pre_auto[0]
            post_hook = post_auto[0]

            # PreToolUse "Agent|Skill" -> agent_start (1 ok) + skill_invoke (1 ok) = 2 fires
            self.assertGreaterEqual(
                pre_hook["fire_count"], 1,
                msg=(
                    f"Expected PreToolUse auto hook fire_count >= 1 (agent_start + "
                    f"skill_invoke beacons present), got {pre_hook['fire_count']}. "
                    "Classifier is keying on literal 'auto' instead of the derived "
                    "event-type keys the beacons actually carry."
                ),
            )
            self.assertIsNotNone(pre_hook["last_fired"])

            # PostToolUse "Agent|Bash|AskUserQuestion|Edit|MultiEdit|Write" ->
            # agent_complete (1 ok) + bash_complete (1 ok) = 2 fires (grill_qa/
            # post_tool have zero beacons in this fixture — honestly zero-eligible).
            self.assertGreaterEqual(
                post_hook["fire_count"], 1,
                msg=(
                    f"Expected PostToolUse auto hook fire_count >= 1 (agent_complete + "
                    f"bash_complete beacons present), got {post_hook['fire_count']}. "
                    "Classifier is keying on literal 'auto' instead of the derived "
                    "event-type keys the beacons actually carry."
                ),
            )
            self.assertIsNotNone(post_hook["last_fired"])

    def test_sanity_literal_auto_key_never_appears_in_beacon_fixture(self):
        """Documents the exact symptom: no beacon line ever carries hook:"auto"."""
        for line in BEACON_LINES.splitlines():
            obj = json.loads(line)
            self.assertNotEqual(
                obj.get("hook"), "auto",
                msg="Fixture must mirror production: auto-mode beacons carry the "
                    "DERIVED key, never the literal 'auto' argument.",
            )


if __name__ == "__main__":
    unittest.main()
