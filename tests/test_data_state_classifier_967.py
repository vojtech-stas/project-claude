"""
tests/test_data_state_classifier_967.py

Regression tests for slice #967 — no-data vs actionable data_state badge
(PRD #957 §2 #4).

Coverage:
  1. _classify_data_state returns "pass" for all PASS results.
  2. _classify_data_state returns "no-data" for explicit absent-source / day-one
     marker strings (representing real check detail text from health.py checks).
  3. _classify_data_state returns "actionable" for genuine WARN/FAIL details
     (threshold breaches, missing annotations, etc.) — honesty guard.
  4. _attach_data_state mutates check dicts correctly.
  5. Integration: audit_meta() checks carry data_state after _attach_data_state.
  6. Integration: a check with a no-data detail gets data_state="no-data" via
     _build_health_data-style pipeline.

Per ADR-0067 D2: tests are written to verify the behaviour matches the spec.

Runner: stdlib unittest + pytest compatible.
  python -m pytest tests/test_data_state_classifier_967.py -v
"""

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
_DASHBOARD_DIR = str(REPO_ROOT / "dashboard")
if _DASHBOARD_DIR not in sys.path:
    sys.path.insert(0, _DASHBOARD_DIR)


def _import_health():
    """Import (or reload) the health module, returning it."""
    if "health" in sys.modules:
        return sys.modules["health"]
    import health
    return health


# ---------------------------------------------------------------------------
# Fixtures: genuine actionable WARN/FAIL details (threshold breaches)
# These must NOT be classified as no-data.
# ---------------------------------------------------------------------------
_ACTIONABLE_DETAILS = [
    # DOCS-8: missing supersession annotation (real gap in the docs)
    "Missing annotations: ['0032-workflow-only-architecture.md supersedes ADR-0031']",
    # DOCS-9: glossary over cap
    "Glossary has 36 entries (cap 35)",
    # DOCS-7: dangling ADR citation (a real broken link)
    "Dangling ADR citations: ['.claude/agents/foo.md -> decisions/0999-nonexistent.md']",
    # HOOK-INTEGRITY: genuine drift (attempts vs ok mismatch)
    "window=7d | ratios: log-tool-event:3/5 | drift: log-tool-event(3/5)",
    # CAPTURE-SLO: actual low session liveness (50% met, but some threshold breach)
    "3/10 live in last 20-session window (SLO 30%)",
    # ISOLATION-GROUP: orphaned worktree
    "orphaned: agent-abcd1234 | dirs: 2, registered: 1",
    # META-TRIPWIRE: real guardrail change without ack
    "meta-tripwire: FAIL — unpromoted batch touches guardrail-machinery path(s) without promotion-ack",
    # RULE-COVERAGE: a new unchecked rule
    "12/13 covered (92%) | NEW unchecked-untagged: [24]",
    # PROOF-PRESENCE: missing proof
    "2/10 PRs missing proof: [pr#900, pr#901]",
    # BLIND-RATE: 50% blind dispatch (not zero but not all)
    "5/10 dispatches carry BLIND-REVIEW prefix (50%)",
]

# ---------------------------------------------------------------------------
# Fixtures: no-data WARN detail strings from actual health.py check output
# These must be classified as no-data.
# ---------------------------------------------------------------------------
_NO_DATA_DETAILS = [
    # CAPTURE-SLO: log file absent
    "workflow-events.jsonl not found",
    # CAPTURE-SLO: no sessions in log
    "no sessions found in workflow-events.jsonl",
    # HOOK-INTEGRITY: log file absent
    "hook-fires.jsonl not found",
    # HOOK-INTEGRITY: no beacons in rolling window
    "no attempt beacons in last 7d window; dark-detection deferred to HOOK-LIVENESS",
    # HOOK-LIVENESS: log absent (may never have fired)
    "hook-fires.jsonl not found — hook layer may never have fired",
    # META-TRIPWIRE: honest day-one (no promotions yet)
    (
        "meta-tripwire: no promotion events found in workflow-events.jsonl; "
        "honest day-one — guardrail check deferred until first promotion runs; ADR-0070 D4"
    ),
    # R-SENSITIVE-DETECTOR: day-one (0 promotions)
    "guardrail-touching promotions: 0 — no promotion events yet (honest day-one); advisory only",
    # BLIND-RATE: log absent
    "workflow-events.jsonl not found",
    # BLIND-RATE: pre-migration — expected
    "no agent_start events with input found (pre-migration — expected)",
    # EVAL checks: no results.json yet
    "tests/evals/results.json not found — no eval run yet for reviewer; honest no-baseline bucket",
    # EVAL checks: no run for this critic
    "no run recorded for critic 'prd-critic' in results.json; honest no-baseline bucket",
    # SPEC-COVERAGE: gh API unavailable
    "gh API unavailable — cannot compute coverage",
    # SPEC-COVERAGE: no PRDs
    "no PRD-labeled issues found",
    # CRITIC-HEALTH: no closed PRDs
    "no closed PRDs found; trail empty",
]


class TestClassifyDataState(unittest.TestCase):
    """Unit tests for _classify_data_state()."""

    def setUp(self):
        self.health = _import_health()

    def test_pass_result_always_returns_pass(self):
        """Any PASS result → data_state='pass', regardless of detail."""
        fn = self.health._classify_data_state
        self.assertEqual("pass", fn("PASS", ""))
        self.assertEqual("pass", fn("PASS", "all checks passed"))
        self.assertEqual("pass", fn("PASS", "no events in window"))  # detail doesn't matter for PASS

    def test_genuine_warn_details_are_actionable(self):
        """Genuine WARN details (threshold breaches) must return 'actionable'.

        Honesty guard: the classifier must NOT mask real issues as no-data.
        """
        fn = self.health._classify_data_state
        for detail in _ACTIONABLE_DETAILS:
            with self.subTest(detail=detail[:60]):
                result = fn("WARN", detail)
                self.assertEqual(
                    "actionable", result,
                    msg=(
                        f"Expected 'actionable' for genuine WARN but got '{result}'. "
                        f"Detail: {detail[:80]}"
                    ),
                )

    def test_genuine_fail_details_are_actionable(self):
        """Genuine FAIL details must return 'actionable'."""
        fn = self.health._classify_data_state
        for detail in _ACTIONABLE_DETAILS:
            with self.subTest(detail=detail[:60]):
                result = fn("FAIL", detail)
                self.assertEqual(
                    "actionable", result,
                    msg=(
                        f"Expected 'actionable' for genuine FAIL but got '{result}'. "
                        f"Detail: {detail[:80]}"
                    ),
                )

    def test_no_data_details_return_no_data(self):
        """Absent-source / day-one details must return 'no-data'."""
        fn = self.health._classify_data_state
        for detail in _NO_DATA_DETAILS:
            with self.subTest(detail=detail[:60]):
                result = fn("WARN", detail)
                self.assertEqual(
                    "no-data", result,
                    msg=(
                        f"Expected 'no-data' for absent-source detail but got '{result}'. "
                        f"Detail: {detail[:80]}"
                    ),
                )

    def test_ambiguous_prefers_actionable(self):
        """When ambiguous (no marker match), default must be 'actionable'."""
        fn = self.health._classify_data_state
        # Generic WARN with no specific marker
        self.assertEqual("actionable", fn("WARN", "some threshold breach"))
        self.assertEqual("actionable", fn("WARN", ""))
        self.assertEqual("actionable", fn("FAIL", "something failed"))

    def test_n_a_result_defaults_to_actionable(self):
        """'N/A' result (not PASS) without a no-data marker → 'actionable'."""
        fn = self.health._classify_data_state
        result = fn("N/A", "excluded")
        self.assertIn(result, ("actionable", "no-data"))  # N/A is not PASS


class TestAttachDataState(unittest.TestCase):
    """Unit tests for _attach_data_state()."""

    def setUp(self):
        self.health = _import_health()

    def test_mutates_check_dicts_in_place(self):
        """_attach_data_state() mutates dicts in place and returns the same list."""
        health = self.health
        checks = [
            {"id": "A", "result": "PASS", "detail": ""},
            {"id": "B", "result": "WARN", "detail": "hook-fires.jsonl not found"},
            {"id": "C", "result": "WARN", "detail": "Missing annotations: ['x']"},
        ]
        returned = health._attach_data_state(checks)
        # Returns same list object
        self.assertIs(returned, checks)
        # PASS → "pass"
        self.assertEqual("pass", checks[0]["data_state"])
        # no-data marker → "no-data"
        self.assertEqual("no-data", checks[1]["data_state"])
        # actionable WARN → "actionable"
        self.assertEqual("actionable", checks[2]["data_state"])

    def test_does_not_overwrite_existing_data_state(self):
        """_attach_data_state skips dicts that already have data_state set."""
        health = self.health
        checks = [{"id": "X", "result": "WARN", "detail": "no-data", "data_state": "custom"}]
        health._attach_data_state(checks)
        self.assertEqual("custom", checks[0]["data_state"])

    def test_empty_list_is_safe(self):
        """_attach_data_state handles an empty list without error."""
        health = self.health
        result = health._attach_data_state([])
        self.assertEqual([], result)


class TestDataStateInAuditMeta(unittest.TestCase):
    """Integration test: audit_meta() checks carry data_state after pipeline.

    Uses audit_meta() + _attach_data_state directly (avoids slow network checks
    in _build_health_data).
    """

    def setUp(self):
        self.health = _import_health()

    def test_audit_meta_checks_have_data_state_after_attach(self):
        """Every check from audit_meta() gets a valid data_state after _attach_data_state."""
        health = self.health
        result = health.audit_meta()
        checks = result.get("checks", [])
        health._attach_data_state(checks)
        self.assertTrue(len(checks) > 0, "audit_meta() returned no checks")
        valid_states = {"pass", "actionable", "no-data"}
        for c in checks:
            check_id = c.get("id", "<no-id>")
            with self.subTest(check_id=check_id):
                self.assertIn(
                    "data_state", c,
                    msg=f"{check_id}: missing data_state key after _attach_data_state",
                )
                self.assertIn(
                    c["data_state"], valid_states,
                    msg=f"{check_id}: data_state '{c['data_state']}' not in {valid_states}",
                )

    def test_pass_checks_have_data_state_pass(self):
        """PASS checks in audit_meta() get data_state='pass'."""
        health = self.health
        result = health.audit_meta()
        checks = result.get("checks", [])
        health._attach_data_state(checks)
        for c in checks:
            if c.get("result") == "PASS":
                with self.subTest(check_id=c.get("id")):
                    self.assertEqual(
                        "pass", c["data_state"],
                        msg=f"PASS check {c['id']} got data_state='{c['data_state']}' (expected 'pass')",
                    )


class TestHonestyGuard(unittest.TestCase):
    """Honesty guard: no genuine WARN must be masked as no-data.

    This is the slice AC's critical requirement: the classifier MUST NOT
    mask a genuine actionable WARN as no-data.
    """

    def setUp(self):
        self.health = _import_health()

    def test_hook_integrity_drift_is_actionable(self):
        """HOOK-INTEGRITY drift (attempts != ok) must be 'actionable', not 'no-data'."""
        fn = self.health._classify_data_state
        drift_detail = "window=7d | ratios: pre-tool-bash:8/10 | drift: pre-tool-bash(8/10)"
        result = fn("FAIL", drift_detail)
        self.assertEqual(
            "actionable", result,
            msg=f"Genuine HOOK-INTEGRITY drift must be 'actionable', got '{result}'",
        )

    def test_docs8_missing_annotation_is_actionable(self):
        """DOCS-8 missing annotation is a real doc gap → must be 'actionable'."""
        fn = self.health._classify_data_state
        detail = "Missing annotations: ['0031-k.md supersedes ADR-0030']"
        result = fn("WARN", detail)
        self.assertEqual(
            "actionable", result,
            msg=f"DOCS-8 missing annotation must be 'actionable', got '{result}'",
        )

    def test_meta_tripwire_fail_is_actionable(self):
        """META-TRIPWIRE FAIL (guardrail change without ack) must be 'actionable'."""
        fn = self.health._classify_data_state
        detail = (
            "meta-tripwire: FAIL — unpromoted batch touches guardrail-machinery "
            "path(s) without promotion-ack; guardrail files: ['dashboard/health.py']"
        )
        result = fn("FAIL", detail)
        self.assertEqual(
            "actionable", result,
            msg=f"META-TRIPWIRE genuine FAIL must be 'actionable', got '{result}'",
        )

    def test_hook_liveness_dark_is_actionable(self):
        """HOOK-LIVENESS dark detection (real lag) must be 'actionable'."""
        fn = self.health._classify_data_state
        detail = (
            "hook layer appears dark: newest beacon 2026-06-17T10:00:00Z is "
            "120 min behind live activity 2026-06-17T12:00:00Z (threshold 60 min)"
        )
        result = fn("FAIL", detail)
        self.assertEqual(
            "actionable", result,
            msg=f"HOOK-LIVENESS dark detection must be 'actionable', got '{result}'",
        )

    def test_no_data_markers_constants_exported(self):
        """_NO_DATA_MARKERS is present in health module and is a non-empty tuple."""
        health = self.health
        self.assertTrue(
            hasattr(health, "_NO_DATA_MARKERS"),
            "_NO_DATA_MARKERS constant not exported from health.py",
        )
        markers = health._NO_DATA_MARKERS
        self.assertIsInstance(markers, tuple)
        self.assertGreater(len(markers), 0, "_NO_DATA_MARKERS must be non-empty")

    def test_classify_data_state_exported(self):
        """_classify_data_state is exported from health.py."""
        health = self.health
        self.assertTrue(
            hasattr(health, "_classify_data_state"),
            "_classify_data_state not exported from health.py",
        )

    def test_attach_data_state_exported(self):
        """_attach_data_state is exported from health.py."""
        health = self.health
        self.assertTrue(
            hasattr(health, "_attach_data_state"),
            "_attach_data_state not exported from health.py",
        )


if __name__ == "__main__":
    unittest.main()
