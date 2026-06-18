"""
Regression tests for slice #958 — gh-correlation dispatch-to-parent-PRD helper.

Groups:
  1. ParentBodyParsing        — _parent_prd_from_issue_body() handles all known
                                slice-body formats.
  2. ResolveDispatchToPrd     — resolve_dispatch_to_prd() with mocked gh returns
                                the correct parent PRD for a known slice number.
  3. FallbackOnGhUnavailable  — when gh fails, resolve_dispatch_to_prd() returns
                                None (not a crash); _derive_prd_label() returns a
                                bucket labeled "#N (gh unavailable)".
  4. FiringTreeGhGrouping     — build_firing_tree() with mocked gh groups a
                                slice-number dispatch under "PRD #<parent>".
  5. FiringTreeFallback       — build_firing_tree() with gh unavailable still
                                returns non-empty groups (fallback buckets).

Runner: stdlib unittest + pytest compatible.
  python -m pytest tests/test_gh_correlation_958.py -v
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


# Minimal fixture meta.json + JSONL builder for build_firing_tree tests
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

    # Main transcript: one Agent tool_use per dispatch
    main_records = []
    for d in dispatches:
        main_records.append({
            "type": "assistant",
            "uuid": f"a-{d['tool_use_id']}",
            "parentUuid": None,
            "timestamp": "2026-06-18T09:00:00.000Z",
            "sessionId": session_id,
            "message": {
                "role": "assistant",
                "content": [{
                    "type": "tool_use",
                    "id": d["tool_use_id"],
                    "name": "Agent",
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

    # Subagent JSONL + meta.json per dispatch
    for d in dispatches:
        agent_stem = f"agent-{d['tool_use_id'][-6:]}"
        jsonl_path = sub_dir / f"{agent_stem}.jsonl"
        meta_path = sub_dir / f"{agent_stem}.meta.json"

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
# Group 1: body parsing
# ---------------------------------------------------------------------------

class TestParentBodyParsing(unittest.TestCase):
    """_parent_prd_from_issue_body() handles all known slice-body formats."""

    def setUp(self):
        _inject_dashboard()
        import transcript as tr
        self._fn = tr._parent_prd_from_issue_body

    def test_walking_skeleton_format(self):
        """'Walking-skeleton slice of PRD #956' extracts 956."""
        result = self._fn(
            "Walking-skeleton slice of PRD #956 (transcript-sourced execution truth)."
        )
        self.assertEqual(result, 956)

    def test_slice_n_of_prd_format(self):
        """'slice 2 of PRD #737' extracts 737."""
        result = self._fn("slice 2 of PRD #737.")
        self.assertEqual(result, 737)

    def test_parent_colon_prd_format(self):
        """'Parent: PRD #123' extracts 123."""
        result = self._fn("Parent: PRD #123 — some description")
        self.assertEqual(result, 123)

    def test_heading_parent_format(self):
        """'## Parent\\n\\nPRD #713' extracts 713 (older slice template)."""
        body = "## Parent\n\nPRD #713 — runtime observation layer."
        result = self._fn(body)
        self.assertEqual(result, 713)

    def test_prd_body_no_parent_returns_none(self):
        """A PRD body with no parent reference returns None."""
        result = self._fn(
            "# PRD: transcript-sourced execution truth\n\n## 1. Problem\n\nSome text."
        )
        self.assertIsNone(result)

    def test_empty_body_returns_none(self):
        """Empty body returns None."""
        self.assertIsNone(self._fn(""))

    def test_none_body_returns_none(self):
        """None body returns None (defensive)."""
        self.assertIsNone(self._fn(None))  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Group 2: resolve_dispatch_to_prd with mocked gh
# ---------------------------------------------------------------------------

class TestResolveDispatchToPrd(unittest.TestCase):
    """resolve_dispatch_to_prd() resolves a known slice → parent PRD via mocked gh."""

    def setUp(self):
        _inject_dashboard()
        import transcript as tr
        self._tr = tr
        # Clear cache before each test
        tr._prd_cache.clear()
        tr._prd_cache_ts = 0.0

    def tearDown(self):
        # Clear cache after each test to avoid cross-test pollution
        import transcript as tr
        tr._prd_cache.clear()
        tr._prd_cache_ts = 0.0

    def _fake_gh_run(self, args, timeout=15):
        """Fake _gh_run_transcript that returns canned responses for known numbers."""
        if "issue" in args and "view" in args:
            # Extract number from args
            idx = args.index("view") + 1
            n = int(args[idx])
            if n == 958:
                # Issue #958 is a slice of PRD #956
                return 0, json.dumps({
                    "number": 958,
                    "labels": [{"name": "slice"}],
                    "body": "Walking-skeleton slice of PRD #956 (transcript-sourced execution truth).",
                })
            elif n == 956:
                # Issue #956 is a PRD
                return 0, json.dumps({
                    "number": 956,
                    "labels": [{"name": "prd"}],
                    "body": "PRD body content",
                })
            elif n == 716:
                # Issue #716 is a slice with ## Parent format
                return 0, json.dumps({
                    "number": 716,
                    "labels": [{"name": "slice"}],
                    "body": "## Parent\n\nPRD #713 — runtime observation layer.",
                })
        return 1, ""

    def test_slice_maps_to_parent_prd(self):
        """resolve_dispatch_to_prd(958) returns 956 (the parent PRD)."""
        with patch("transcript._gh_run_transcript", side_effect=self._fake_gh_run):
            result = self._tr.resolve_dispatch_to_prd(958)
        self.assertEqual(result, 956, f"Expected 956, got {result}")

    def test_prd_maps_to_itself(self):
        """resolve_dispatch_to_prd(956) returns 956 (issue IS a PRD)."""
        with patch("transcript._gh_run_transcript", side_effect=self._fake_gh_run):
            result = self._tr.resolve_dispatch_to_prd(956)
        self.assertEqual(result, 956, f"Expected 956 (self), got {result}")

    def test_slice_with_heading_parent_format(self):
        """resolve_dispatch_to_prd(716) returns 713 (## Parent format)."""
        with patch("transcript._gh_run_transcript", side_effect=self._fake_gh_run):
            result = self._tr.resolve_dispatch_to_prd(716)
        self.assertEqual(result, 713, f"Expected 713, got {result}")

    def test_result_is_cached(self):
        """Second call with same number uses cache (gh is only called once)."""
        call_count = [0]

        def counting_gh(args, timeout=15):
            call_count[0] += 1
            return self._fake_gh_run(args, timeout)

        with patch("transcript._gh_run_transcript", side_effect=counting_gh):
            r1 = self._tr.resolve_dispatch_to_prd(958)
            r2 = self._tr.resolve_dispatch_to_prd(958)

        self.assertEqual(r1, r2)
        # Second call must not trigger gh (cache hit)
        # First call fetches issue #958 only (body has PRD #956 directly)
        self.assertEqual(call_count[0], 1,
                         f"Expected 1 gh call, got {call_count[0]}")


# ---------------------------------------------------------------------------
# Group 3: fallback when gh is unavailable
# ---------------------------------------------------------------------------

class TestFallbackOnGhUnavailable(unittest.TestCase):
    """Graceful fallback when gh CLI is unavailable or errors."""

    def setUp(self):
        _inject_dashboard()
        import transcript as tr
        self._tr = tr
        tr._prd_cache.clear()
        tr._prd_cache_ts = 0.0

    def tearDown(self):
        import transcript as tr
        tr._prd_cache.clear()
        tr._prd_cache_ts = 0.0

    def _always_fail_gh(self, args, timeout=15):
        """Always return a non-zero exit code (gh unavailable)."""
        return 1, ""

    def test_resolve_returns_none_when_gh_fails(self):
        """resolve_dispatch_to_prd() returns None (not a crash) when gh fails."""
        with patch("transcript._gh_run_transcript", side_effect=self._always_fail_gh):
            result = self._tr.resolve_dispatch_to_prd(958)
        self.assertIsNone(result,
                          "Expected None when gh is unavailable, not a crash")

    def test_derive_prd_label_fallback_bucket(self):
        """_derive_prd_label() returns '#N (gh unavailable)' when gh fails."""
        with patch("transcript._gh_run_transcript", side_effect=self._always_fail_gh):
            label = self._tr._derive_prd_label(
                "Run implementer for #958", "implementer", use_gh=True
            )
        self.assertIn("gh unavailable", label,
                      f"Expected '(gh unavailable)' in label, got: {label!r}")
        self.assertIn("958", label,
                      f"Expected issue number in fallback label, got: {label!r}")

    def test_derive_prd_label_no_gh_use_gh_false(self):
        """_derive_prd_label(use_gh=False) returns '#N' without gh calls."""
        label = self._tr._derive_prd_label(
            "Run implementer for #958", "implementer", use_gh=False
        )
        self.assertEqual(label, "#958",
                         f"Expected '#958', got: {label!r}")

    def test_no_crash_on_completely_bad_gh_output(self):
        """resolve_dispatch_to_prd() handles malformed gh output without crash."""
        def bad_json_gh(args, timeout=15):
            return 0, "NOT JSON {"

        with patch("transcript._gh_run_transcript", side_effect=bad_json_gh):
            result = self._tr.resolve_dispatch_to_prd(999)
        # Must return None, not raise
        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# Group 4: build_firing_tree with gh correlation
# ---------------------------------------------------------------------------

class TestFiringTreeGhGrouping(unittest.TestCase):
    """build_firing_tree() groups a slice-number dispatch under its parent PRD."""

    def setUp(self):
        _inject_dashboard()
        import transcript as tr
        self._tr = tr
        tr._prd_cache.clear()
        tr._prd_cache_ts = 0.0

        # Fixture: implementer dispatch for slice #958 (parent PRD #956)
        self._main_path, self._tmpdir = _build_session_fixture(
            session_id="test-gh-corr-958",
            dispatches=[
                {
                    "tool_use_id": "toolu_impl_958",
                    "agent_type": "implementer",
                    "description": "Implement slice #958 (gh-correlation helper)",
                    "verdict_text": "RESULT: SUCCESS\nREASON: PR opened\n",
                },
                {
                    "tool_use_id": "toolu_rev_958",
                    "agent_type": "reviewer",
                    "description": "Review PR #959 (slice #958)",
                    "verdict_text": "VERDICT: APPROVE\nROUND: 1\n",
                },
            ],
        )

    def tearDown(self):
        import shutil
        shutil.rmtree(self._tmpdir, ignore_errors=True)
        import transcript as tr
        tr._prd_cache.clear()
        tr._prd_cache_ts = 0.0

    def _fake_gh_run(self, args, timeout=15):
        """Fake gh that maps slice #958 → PRD #956."""
        if "issue" in args and "view" in args:
            idx = args.index("view") + 1
            n = int(args[idx])
            if n == 958:
                return 0, json.dumps({
                    "number": 958,
                    "labels": [{"name": "slice"}],
                    "body": "Walking-skeleton slice of PRD #956 (transcript-sourced execution truth).",
                })
            elif n == 959:
                # #959 is also a slice (reviewer references a PR, not an issue,
                # but the number ends up in description — use the slice body)
                return 0, json.dumps({
                    "number": 959,
                    "labels": [{"name": "slice"}],
                    "body": "Walking-skeleton slice of PRD #956.",
                })
        elif "pr" in args and "view" in args:
            idx = args.index("view") + 1
            n = int(args[idx])
            # PR #959 → Closes #958
            return 0, json.dumps({
                "number": n,
                "body": f"Closes #958\n\n## Scope\nSome PR body.",
            })
        return 1, ""

    def test_dispatch_bucketed_under_parent_prd(self):
        """Slice #958 implementer dispatch must appear under 'PRD #956' bucket."""
        with patch("transcript._gh_run_transcript", side_effect=self._fake_gh_run):
            result = self._tr.build_firing_tree(self._main_path)

        groups = result.get("groups", {})
        self.assertIn(
            "PRD #956",
            groups,
            f"Expected 'PRD #956' bucket in groups, got: {list(groups.keys())}",
        )

    def test_prd_bucket_contains_implementer(self):
        """The 'PRD #956' bucket must contain an implementer dispatch."""
        with patch("transcript._gh_run_transcript", side_effect=self._fake_gh_run):
            result = self._tr.build_firing_tree(self._main_path)

        groups = result.get("groups", {})
        prd_dispatches = groups.get("PRD #956", [])
        agent_types = [d["agent"] for d in prd_dispatches]
        self.assertIn(
            "implementer",
            agent_types,
            f"Expected implementer in PRD #956 bucket, got: {agent_types}",
        )

    def test_slice_number_not_a_top_level_bucket(self):
        """The raw slice number '#958' must NOT be a top-level bucket key
        (it should be resolved to 'PRD #956')."""
        with patch("transcript._gh_run_transcript", side_effect=self._fake_gh_run):
            result = self._tr.build_firing_tree(self._main_path)

        groups = result.get("groups", {})
        self.assertNotIn(
            "#958",
            groups,
            "Raw slice number '#958' must not be a top-level bucket "
            "(should be under 'PRD #956')",
        )

    def test_dispatch_count(self):
        """dispatch_count must equal 2 (implementer + reviewer)."""
        with patch("transcript._gh_run_transcript", side_effect=self._fake_gh_run):
            result = self._tr.build_firing_tree(self._main_path)
        self.assertEqual(result.get("dispatch_count"), 2)

    def test_no_error(self):
        """build_firing_tree must not return an error field for a valid fixture."""
        with patch("transcript._gh_run_transcript", side_effect=self._fake_gh_run):
            result = self._tr.build_firing_tree(self._main_path)
        self.assertIsNone(result.get("error"))


# ---------------------------------------------------------------------------
# Group 5: build_firing_tree fallback when gh unavailable
# ---------------------------------------------------------------------------

class TestFiringTreeFallback(unittest.TestCase):
    """build_firing_tree() still returns non-empty groups when gh is unavailable."""

    def setUp(self):
        _inject_dashboard()
        import transcript as tr
        self._tr = tr
        tr._prd_cache.clear()
        tr._prd_cache_ts = 0.0

        self._main_path, self._tmpdir = _build_session_fixture(
            session_id="test-gh-fallback-958",
            dispatches=[
                {
                    "tool_use_id": "toolu_impl_xxx",
                    "agent_type": "implementer",
                    "description": "Implement slice #800 (some feature)",
                    "verdict_text": "RESULT: SUCCESS\n",
                },
            ],
        )

    def tearDown(self):
        import shutil
        shutil.rmtree(self._tmpdir, ignore_errors=True)
        import transcript as tr
        tr._prd_cache.clear()
        tr._prd_cache_ts = 0.0

    def test_fallback_returns_non_empty_groups(self):
        """Even with gh unavailable, build_firing_tree() returns ≥1 bucket."""
        def fail_gh(args, timeout=15):
            return 1, ""

        with patch("transcript._gh_run_transcript", side_effect=fail_gh):
            result = self._tr.build_firing_tree(self._main_path)

        groups = result.get("groups", {})
        self.assertGreater(
            len(groups),
            0,
            "build_firing_tree() must return ≥1 group even when gh is unavailable",
        )

    def test_fallback_bucket_label_contains_gh_unavailable(self):
        """Fallback bucket label must contain '(gh unavailable)' to be honest."""
        def fail_gh(args, timeout=15):
            return 1, ""

        with patch("transcript._gh_run_transcript", side_effect=fail_gh):
            result = self._tr.build_firing_tree(self._main_path)

        groups = result.get("groups", {})
        labels = list(groups.keys())
        has_unavailable = any("gh unavailable" in lbl for lbl in labels)
        self.assertTrue(
            has_unavailable,
            f"At least one bucket must have '(gh unavailable)' label, got: {labels}",
        )

    def test_no_crash_when_gh_unavailable(self):
        """build_firing_tree() must not raise when gh fails (never a crash)."""
        def fail_gh(args, timeout=15):
            return 1, ""

        try:
            with patch("transcript._gh_run_transcript", side_effect=fail_gh):
                result = self._tr.build_firing_tree(self._main_path)
        except Exception as exc:
            self.fail(f"build_firing_tree raised {type(exc).__name__}: {exc}")

        self.assertIsInstance(result, dict)


# ---------------------------------------------------------------------------
# Group 6: resolve_dispatch_to_prd public API contract
# ---------------------------------------------------------------------------

class TestResolveDispatchToPrdContract(unittest.TestCase):
    """Public API contract: resolve_dispatch_to_prd exists and is callable."""

    def setUp(self):
        _inject_dashboard()
        import transcript as tr
        self._tr = tr

    def test_function_exists(self):
        """resolve_dispatch_to_prd must be defined in transcript module."""
        self.assertTrue(
            callable(getattr(self._tr, "resolve_dispatch_to_prd", None)),
            "transcript.py must define and export resolve_dispatch_to_prd()",
        )

    def test_signature_accepts_int(self):
        """resolve_dispatch_to_prd must accept an int and return int or None."""
        # Use a mocked gh to avoid real network calls in CI
        def no_gh(args, timeout=15):
            return 1, ""

        with patch("transcript._gh_run_transcript", side_effect=no_gh):
            result = self._tr.resolve_dispatch_to_prd(99999)

        self.assertIsNone(result,
                          "resolve_dispatch_to_prd must return None when gh is unavailable")


if __name__ == "__main__":
    unittest.main()
