"""
tests/test_release_ready_838.py

Regression tests for slice #838 — RELEASE-READY six-condition gate (ADR-0070 D2).

Per ADR-0067 D2: test commit precedes implementation commit in branch history.
These tests are written to FAIL before the impl lands and PASS after.

Six conditions (ADR-0070 D2):
  (a) CI green on develop HEAD
  (b) full test suite passes (ADR-0067 D1)
  (c) latest production-verify PASS — wired to PROOF-INTEGRITY check
  (d) green-develop streak intact (no failing checkpoint since last promotion)
  (e) zero open needs-human items
  (f) guardrail-path batch check — STUB until #840 (returns pass/"deferred to #840")

Implementation contract:
- check_release_ready() exits 0 (check ran; PASS/WARN/FAIL result)
- When all conditions pass: result="PASS", verdict="true"
- When any condition fails: result="WARN" (gate held), detail names the first failing condition
- The check does NOT hard-FAIL (exit 1) — it always exits 0 when it ran; honest held state
- promote.sh gains a RELEASE-READY pre-flight guard: refuses to promote when not ready

Test injection:
  Each condition is injectable via env vars so tests run offline and deterministically.
  See check_release_ready() docstring for env var names.

Runner: stdlib unittest + pytest compatible.
  python -m pytest tests/test_release_ready_838.py -v
"""

import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
HEALTH_PY = REPO_ROOT / "dashboard" / "health.py"
PROMOTE_SH = REPO_ROOT / "tools" / "promote.sh"

# ---------------------------------------------------------------------------
# Helper: run check_release_ready() via subprocess with env-var injection.
# ---------------------------------------------------------------------------

def _run_release_ready_check(env_overrides: dict | None = None) -> dict:
    """Invoke check_release_ready() via subprocess with optional env overrides.

    Returns the parsed JSON result dict (id, result, detail, ...).
    On parse failure returns {"id": "RELEASE-READY", "result": "ERROR",
                              "detail": <raw output>}.
    """
    env = os.environ.copy()
    env.pop("PYTHONDONTWRITEBYTECODE", None)
    if env_overrides:
        for k, v in env_overrides.items():
            env[k] = v

    result = subprocess.run(
        [sys.executable, str(HEALTH_PY), "--check", "RELEASE-READY"],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(REPO_ROOT),
        timeout=30,
    )
    raw = (result.stdout or "").strip()
    # The CLI prints the check result as JSON on stdout.
    # Try to extract the JSON blob (the last non-empty line starting with '{').
    json_line = ""
    for line in raw.splitlines():
        line = line.strip()
        if line.startswith("{"):
            json_line = line
    if not json_line:
        return {"id": "RELEASE-READY", "result": "ERROR", "detail": raw}
    try:
        return json.loads(json_line)
    except json.JSONDecodeError:
        return {"id": "RELEASE-READY", "result": "ERROR", "detail": raw}


# ---------------------------------------------------------------------------
# Group 1: check is no longer dormant — it emits a real verdict
# ---------------------------------------------------------------------------

class TestReleaseReadyNotDormant(unittest.TestCase):
    """RELEASE-READY must no longer return a dormant detail string (ADR-0071 D4
    applied while two-tier was deferred; now wired per slice #838)."""

    def test_id_is_correct(self):
        """check_release_ready() must return id='RELEASE-READY'."""
        r = _run_release_ready_check()
        self.assertEqual(
            r.get("id"), "RELEASE-READY",
            f"Expected id='RELEASE-READY', got: {r.get('id')!r}",
        )

    def test_exits_0(self):
        """check_release_ready() CLI must exit 0 (check ran, gate may be held)."""
        result = subprocess.run(
            [sys.executable, str(HEALTH_PY), "--check", "RELEASE-READY"],
            capture_output=True, text=True, cwd=str(REPO_ROOT), timeout=30,
        )
        self.assertEqual(
            result.returncode, 0,
            f"--check RELEASE-READY must exit 0; got {result.returncode}. "
            f"stderr: {result.stderr[:300]!r}",
        )

    def test_detail_not_dormant(self):
        """RELEASE-READY detail must NOT say 'dormant' — the gate is now wired."""
        r = _run_release_ready_check()
        detail = r.get("detail", "")
        self.assertNotIn(
            "dormant",
            detail.lower(),
            f"RELEASE-READY detail must not say 'dormant' — slice #838 wires the "
            f"six-condition gate (ADR-0070 D2). got: {detail!r}",
        )


# ---------------------------------------------------------------------------
# Group 2: condition (e) — zero open needs-human
# ---------------------------------------------------------------------------

class TestConditionE_NeedsHuman(unittest.TestCase):
    """Condition (e): zero open needs-human items must hold for gate to pass."""

    def test_held_when_needs_human_open(self):
        """Gate must report held when _RELEASE_READY_NEEDS_HUMAN_COUNT > 0."""
        r = _run_release_ready_check({
            "_RELEASE_READY_NEEDS_HUMAN_COUNT": "3",
        })
        detail = r.get("detail", "")
        result = r.get("result", "")
        # Result should be WARN (held) or FAIL but NOT PASS
        self.assertNotEqual(
            result, "PASS",
            f"Gate should not PASS when needs-human count=3; got result={result!r}, "
            f"detail={detail!r}",
        )
        # Detail should mention the condition (e) or needs-human
        self.assertTrue(
            "needs-human" in detail.lower() or "(e)" in detail.lower(),
            f"Detail should mention needs-human condition; got: {detail!r}",
        )

    def test_not_held_when_needs_human_zero(self):
        """Gate must not hold on condition (e) when needs-human count=0.

        NOTE: Other conditions may still hold the gate; we just verify (e) doesn't.
        The detail should NOT name (e)/needs-human as the blocking condition when
        count=0.
        """
        r = _run_release_ready_check({
            "_RELEASE_READY_NEEDS_HUMAN_COUNT": "0",
        })
        detail = r.get("detail", "")
        # If the gate is held, it should not be because of condition (e)
        # (other conditions may still hold it — that's ok)
        if r.get("result") != "PASS":
            # Verify the blocking condition is NOT (e)
            first_fail = r.get("first_failing_condition", "")
            self.assertNotEqual(
                first_fail, "e",
                f"Condition (e) should pass when needs-human=0; "
                f"first_failing_condition={first_fail!r}, detail={detail!r}",
            )


# ---------------------------------------------------------------------------
# Group 3: condition (f) — guardrail-path stub
# ---------------------------------------------------------------------------

class TestConditionF_GuardrailStub(unittest.TestCase):
    """Condition (f): guardrail-path batch check is STUBBED until #840.

    The stub must pass (return pass or skip, not block the gate).
    """

    def test_condition_f_not_blocking(self):
        """Condition (f) stub must not block the gate (deferred to #840)."""
        r = _run_release_ready_check({
            "_RELEASE_READY_NEEDS_HUMAN_COUNT": "0",
        })
        first_fail = r.get("first_failing_condition", "")
        self.assertNotEqual(
            first_fail, "f",
            f"Condition (f) is a stub until #840 and must not block; "
            f"got first_failing_condition={first_fail!r}, detail={r.get('detail')!r}",
        )

    def test_detail_mentions_f_stub(self):
        """check_release_ready() detail or a sub-key must note (f) is deferred/stub."""
        r = _run_release_ready_check()
        detail = r.get("detail", "")
        condition_f_note = r.get("condition_f", "")
        # Either the detail or condition_f field should acknowledge the stub
        combined = (detail + " " + condition_f_note).lower()
        self.assertTrue(
            "#840" in combined or "stub" in combined or "deferred" in combined,
            f"RELEASE-READY must note (f) is deferred/stub until #840; "
            f"detail={detail!r}, condition_f={condition_f_note!r}",
        )


# ---------------------------------------------------------------------------
# Group 4: condition (c) — PROOF-INTEGRITY wiring
# ---------------------------------------------------------------------------

class TestConditionC_ProofIntegrity(unittest.TestCase):
    """Condition (c): wired to PROOF-INTEGRITY check result."""

    def test_held_when_proof_integrity_fail(self):
        """Gate must report held (c) when _RELEASE_READY_PROOF_INTEGRITY_RESULT=FAIL."""
        r = _run_release_ready_check({
            "_RELEASE_READY_PROOF_INTEGRITY_RESULT": "FAIL",
            "_RELEASE_READY_NEEDS_HUMAN_COUNT": "0",
        })
        result = r.get("result", "")
        self.assertNotEqual(
            result, "PASS",
            f"Gate should not PASS when proof-integrity=FAIL; "
            f"got result={result!r}, detail={r.get('detail')!r}",
        )

    def test_not_blocked_when_proof_integrity_warn(self):
        """Gate should not block on WARN from proof-integrity (WARN = no data yet).

        WARN means no qualifying PRs found — honest no-data is not a blocker.
        (Other conditions may still hold the gate.)
        """
        r = _run_release_ready_check({
            "_RELEASE_READY_PROOF_INTEGRITY_RESULT": "WARN",
            "_RELEASE_READY_NEEDS_HUMAN_COUNT": "0",
        })
        first_fail = r.get("first_failing_condition", "")
        self.assertNotEqual(
            first_fail, "c",
            f"Condition (c) should not block on PROOF-INTEGRITY WARN (no data); "
            f"got first_failing={first_fail!r}",
        )


# ---------------------------------------------------------------------------
# Group 5: all-pass scenario
# ---------------------------------------------------------------------------

class TestAllPassScenario(unittest.TestCase):
    """With all injectable conditions forced to pass, gate should PASS."""

    def test_pass_when_all_injectable_conditions_pass(self):
        """Gate must PASS when all injectable conditions are forced to pass."""
        r = _run_release_ready_check({
            "_RELEASE_READY_NEEDS_HUMAN_COUNT": "0",
            "_RELEASE_READY_PROOF_INTEGRITY_RESULT": "PASS",
            "_RELEASE_READY_CI_RESULT": "PASS",
            "_RELEASE_READY_TESTS_RESULT": "PASS",
            "_RELEASE_READY_STREAK_RESULT": "PASS",
        })
        result = r.get("result", "")
        self.assertEqual(
            result, "PASS",
            f"Gate must PASS when all injectable conditions forced to pass; "
            f"got result={result!r}, detail={r.get('detail')!r}",
        )

    def test_verdict_true_when_pass(self):
        """When gate PASSes, verdict field (or detail) must say 'true'."""
        r = _run_release_ready_check({
            "_RELEASE_READY_NEEDS_HUMAN_COUNT": "0",
            "_RELEASE_READY_PROOF_INTEGRITY_RESULT": "PASS",
            "_RELEASE_READY_CI_RESULT": "PASS",
            "_RELEASE_READY_TESTS_RESULT": "PASS",
            "_RELEASE_READY_STREAK_RESULT": "PASS",
        })
        if r.get("result") == "PASS":
            combined = (r.get("detail", "") + " " + str(r.get("verdict", ""))).lower()
            self.assertTrue(
                "true" in combined or "ready" in combined,
                f"PASS result should indicate gate is true/ready; "
                f"detail={r.get('detail')!r}, verdict={r.get('verdict')!r}",
            )


# ---------------------------------------------------------------------------
# Group 6: condition (a) — CI check
# ---------------------------------------------------------------------------

class TestConditionA_CI(unittest.TestCase):
    """Condition (a): CI green on develop HEAD."""

    def test_held_when_ci_fail(self):
        """Gate must hold when CI result is forced to FAIL."""
        r = _run_release_ready_check({
            "_RELEASE_READY_CI_RESULT": "FAIL",
            "_RELEASE_READY_NEEDS_HUMAN_COUNT": "0",
        })
        self.assertNotEqual(
            r.get("result"), "PASS",
            f"Gate should not PASS when CI=FAIL; got {r.get('result')!r}",
        )


# ---------------------------------------------------------------------------
# Group 7: condition (b) — test suite
# ---------------------------------------------------------------------------

class TestConditionB_TestSuite(unittest.TestCase):
    """Condition (b): full test suite passes (ADR-0067 D1)."""

    def test_held_when_tests_fail(self):
        """Gate must hold when test suite result is forced to FAIL."""
        r = _run_release_ready_check({
            "_RELEASE_READY_TESTS_RESULT": "FAIL",
            "_RELEASE_READY_NEEDS_HUMAN_COUNT": "0",
        })
        self.assertNotEqual(
            r.get("result"), "PASS",
            f"Gate should not PASS when tests=FAIL; got {r.get('result')!r}",
        )


# ---------------------------------------------------------------------------
# Group 8: condition (d) — green-develop streak
# ---------------------------------------------------------------------------

class TestConditionD_Streak(unittest.TestCase):
    """Condition (d): green-develop streak intact."""

    def test_held_when_streak_fail(self):
        """Gate must hold when streak result is forced to FAIL."""
        r = _run_release_ready_check({
            "_RELEASE_READY_STREAK_RESULT": "FAIL",
            "_RELEASE_READY_NEEDS_HUMAN_COUNT": "0",
        })
        self.assertNotEqual(
            r.get("result"), "PASS",
            f"Gate should not PASS when streak=FAIL; got {r.get('result')!r}",
        )


# ---------------------------------------------------------------------------
# Group 9: promote.sh guard
# ---------------------------------------------------------------------------

class TestPromoteShGuard(unittest.TestCase):
    """promote.sh must refuse to promote unless RELEASE-READY is true."""

    def test_promote_sh_contains_release_ready_guard(self):
        """tools/promote.sh must contain a RELEASE-READY pre-flight guard."""
        self.assertTrue(
            PROMOTE_SH.exists(),
            f"tools/promote.sh must exist; not found at {PROMOTE_SH}",
        )
        content = PROMOTE_SH.read_text(encoding="utf-8")
        self.assertIn(
            "RELEASE-READY",
            content,
            "tools/promote.sh must reference RELEASE-READY as a pre-flight guard",
        )

    def test_promote_sh_guard_checks_health(self):
        """promote.sh guard must invoke health.py or a gate check."""
        content = PROMOTE_SH.read_text(encoding="utf-8")
        # Either health.py or the --check flag should appear in the guard
        has_health = "health.py" in content or "--check" in content
        self.assertTrue(
            has_health,
            "promote.sh RELEASE-READY guard must invoke health.py --check RELEASE-READY",
        )

    def test_promote_sh_refuses_when_not_ready(self):
        """promote.sh must exit non-zero when RELEASE-READY is not 'true'.

        We use _PROMOTE_SH_SKIP_PUSH=1 + _RELEASE_READY_FORCE_FAIL=1 to run
        the guard logic without actually pushing.
        """
        if not PROMOTE_SH.exists():
            self.skipTest("promote.sh not found")
        env = os.environ.copy()
        env["_PROMOTE_SH_SKIP_PUSH"] = "1"
        env["_RELEASE_READY_FORCE_FAIL"] = "1"
        result = subprocess.run(
            ["bash", str(PROMOTE_SH)],
            capture_output=True, text=True, env=env,
            cwd=str(REPO_ROOT), timeout=20,
        )
        self.assertNotEqual(
            result.returncode, 0,
            f"promote.sh must exit non-zero when RELEASE-READY is not true; "
            f"got exit 0. stdout={result.stdout[:200]!r} stderr={result.stderr[:200]!r}",
        )


# ---------------------------------------------------------------------------
# Group 10: ship/SKILL.md documents green-develop → auto-promote step
# ---------------------------------------------------------------------------

class TestShipSkillDocumentation(unittest.TestCase):
    """ship/SKILL.md must document the RELEASE-READY gate + auto-promote step."""

    SHIP_SKILL = REPO_ROOT / ".claude" / "skills" / "ship" / "SKILL.md"

    def test_ship_skill_mentions_release_ready(self):
        """ship/SKILL.md must mention RELEASE-READY (gate documented)."""
        self.assertTrue(
            self.SHIP_SKILL.exists(),
            f"ship/SKILL.md must exist at {self.SHIP_SKILL}",
        )
        content = self.SHIP_SKILL.read_text(encoding="utf-8")
        self.assertGreaterEqual(
            content.lower().count("release-ready"), 1,
            "ship/SKILL.md must mention RELEASE-READY ≥1 time (gate documented)",
        )

    def test_ship_skill_documents_auto_promote(self):
        """ship/SKILL.md must document the auto-promote step."""
        content = self.SHIP_SKILL.read_text(encoding="utf-8")
        has_promote = (
            "auto-promot" in content.lower()
            or "promote.sh" in content
            or "fast-forward" in content.lower()
        )
        self.assertTrue(
            has_promote,
            "ship/SKILL.md must document the auto-promote (fast-forward) step; "
            "expected 'auto-promot' or 'promote.sh' or 'fast-forward'",
        )


if __name__ == "__main__":
    unittest.main()
