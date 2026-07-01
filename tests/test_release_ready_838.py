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
  (f) guardrail-path batch check — STUB until #840 (returns pass)

Test injection:
  check_release_ready() honours env vars:
    _RELEASE_READY_CI_RESULT           PASS|FAIL
    _RELEASE_READY_TESTS_RESULT        PASS|FAIL
    _RELEASE_READY_PROOF_INTEGRITY_RESULT  PASS|WARN|FAIL
    _RELEASE_READY_STREAK_RESULT       PASS|FAIL
    _RELEASE_READY_NEEDS_HUMAN_COUNT   <int>
    _RELEASE_READY_FORCE_FAIL          1

Tests use direct import (not subprocess) for speed.

Runner: stdlib unittest + pytest compatible.
  python -m pytest tests/test_release_ready_838.py -v
"""

import importlib
import os
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
HEALTH_PY = REPO_ROOT / "dashboard" / "health.py"
PROMOTE_SH = REPO_ROOT / "tools" / "promote.sh"
SHIP_SKILL = REPO_ROOT / ".claude" / "skills" / "ship" / "SKILL.md"

# Ensure dashboard/ is importable.
_DASHBOARD_DIR = str(REPO_ROOT / "dashboard")
if _DASHBOARD_DIR not in sys.path:
    sys.path.insert(0, _DASHBOARD_DIR)


# ---------------------------------------------------------------------------
# Helper: load/reload health module and call check_release_ready() with
# temporary env-var overrides.
# ---------------------------------------------------------------------------

def _call_check(env_overrides: dict | None = None) -> dict:
    """Reload health module and call check_release_ready() with env overrides.

    All conditions are defaulted to PASS (fast-path — avoids real CI/pytest/gh).
    Pass env_overrides to override specific conditions.

    Condition (f) is stubbed via _META_TRIPWIRE_RESULT_OVERRIDE=PASS (added
    per reviewer round-1 finding on PR #1045): without this, condition (f)
    reads LIVE check_meta_tripwire() state — i.e. real unpromoted guardrail
    commits on whatever branch is checked out — instead of the injected
    all-conditions-pass scenario this helper is meant to construct. The live
    (uninjected) check still fires correctly at real promotion time.
    """
    # Default fast-path: all conditions injected as PASS.
    defaults = {
        "_RELEASE_READY_CI_RESULT": "PASS",
        "_RELEASE_READY_TESTS_RESULT": "PASS",
        "_RELEASE_READY_PROOF_INTEGRITY_RESULT": "PASS",
        "_RELEASE_READY_STREAK_RESULT": "PASS",
        "_RELEASE_READY_NEEDS_HUMAN_COUNT": "0",
        "_META_TRIPWIRE_RESULT_OVERRIDE": "PASS",
    }
    env_patch = {**defaults, **(env_overrides or {})}

    # Temporarily set env vars, reload module, call, restore.
    old_vals = {}
    for k, v in env_patch.items():
        old_vals[k] = os.environ.get(k)
        os.environ[k] = v
    try:
        import health as _h
        importlib.reload(_h)
        return _h.check_release_ready()
    finally:
        for k, old_v in old_vals.items():
            if old_v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = old_v


# ---------------------------------------------------------------------------
# Group 1: check is no longer dormant — it emits a real verdict
# ---------------------------------------------------------------------------

class TestReleaseReadyNotDormant(unittest.TestCase):
    """RELEASE-READY must no longer return a dormant detail string (ADR-0071 D4
    applied while two-tier was deferred; now wired per slice #838)."""

    def test_id_is_correct(self):
        """check_release_ready() must return id='RELEASE-READY'."""
        r = _call_check()
        self.assertEqual(
            r.get("id"), "RELEASE-READY",
            f"Expected id='RELEASE-READY', got: {r.get('id')!r}",
        )

    def test_result_field_present(self):
        """check_release_ready() must return a 'result' field."""
        r = _call_check()
        self.assertIn(
            "result", r,
            "check_release_ready() must return a 'result' field",
        )

    def test_detail_not_dormant(self):
        """RELEASE-READY detail must NOT say 'dormant' — the gate is now wired."""
        r = _call_check()
        detail = r.get("detail", "")
        self.assertNotIn(
            "dormant",
            detail.lower(),
            f"RELEASE-READY detail must not say 'dormant' — slice #838 wires the "
            f"six-condition gate (ADR-0070 D2). got: {detail!r}",
        )

    def test_cli_exits_0_when_gate_held(self):
        """--check RELEASE-READY must exit 0 even when gate is held (honest WARN)."""
        env = os.environ.copy()
        # Inject a held condition (needs-human = 1) but bypass all real subprocesses.
        env["_RELEASE_READY_CI_RESULT"] = "PASS"
        env["_RELEASE_READY_TESTS_RESULT"] = "PASS"
        env["_RELEASE_READY_PROOF_INTEGRITY_RESULT"] = "PASS"
        env["_RELEASE_READY_STREAK_RESULT"] = "PASS"
        env["_RELEASE_READY_NEEDS_HUMAN_COUNT"] = "1"
        result = subprocess.run(
            [sys.executable, str(HEALTH_PY), "--check", "RELEASE-READY"],
            capture_output=True, text=True, env=env,
            cwd=str(REPO_ROOT), timeout=30,
        )
        self.assertEqual(
            result.returncode, 0,
            f"--check RELEASE-READY must exit 0 even when gate is held; "
            f"got {result.returncode}. stderr: {result.stderr[:300]!r}",
        )


# ---------------------------------------------------------------------------
# Group 2: condition (e) — zero open needs-human
# ---------------------------------------------------------------------------

class TestConditionE_NeedsHuman(unittest.TestCase):
    """Condition (e): zero open needs-human items must hold for gate to pass."""

    def test_held_when_needs_human_open(self):
        """Gate must report held when needs-human count > 0."""
        r = _call_check({"_RELEASE_READY_NEEDS_HUMAN_COUNT": "3"})
        detail = r.get("detail", "")
        result = r.get("result", "")
        # Result should be WARN (held) not PASS
        self.assertNotEqual(
            result, "PASS",
            f"Gate should not PASS when needs-human count=3; got result={result!r}, "
            f"detail={detail!r}",
        )
        # Detail should mention the condition
        self.assertTrue(
            "needs-human" in detail.lower() or "(e)" in detail.lower(),
            f"Detail should mention needs-human condition; got: {detail!r}",
        )

    def test_first_failing_condition_is_e(self):
        """first_failing_condition must be 'e' when needs-human holds the gate."""
        r = _call_check({"_RELEASE_READY_NEEDS_HUMAN_COUNT": "2"})
        self.assertEqual(
            r.get("first_failing_condition"), "e",
            f"first_failing_condition must be 'e' when needs-human=2; "
            f"got: {r.get('first_failing_condition')!r}",
        )

    def test_passes_condition_e_when_zero(self):
        """Condition (e) must pass when needs-human count is 0."""
        r = _call_check({"_RELEASE_READY_NEEDS_HUMAN_COUNT": "0"})
        # (e) should not be the failing condition
        first_fail = r.get("first_failing_condition", "")
        self.assertNotEqual(
            first_fail, "e",
            f"Condition (e) must pass when needs-human=0; "
            f"first_failing_condition={first_fail!r}",
        )


# ---------------------------------------------------------------------------
# Group 3: condition (f) — guardrail-path stub
# ---------------------------------------------------------------------------

class TestConditionF_GuardrailStub(unittest.TestCase):
    """Condition (f): guardrail-path batch check — wired by slice #840.

    Updated by slice #840: the stub is replaced by check_meta_tripwire().
    The 'stub' / 'deferred to #840' assertions are superseded.
    """

    def test_condition_f_not_blocking_with_pass_injection(self):
        """Condition (f) must not block when meta-tripwire is injected as PASS."""
        # Inject _META_TRIPWIRE_RESULT_OVERRIDE=PASS so (f) does not block.
        old = os.environ.get("_META_TRIPWIRE_RESULT_OVERRIDE")
        os.environ["_META_TRIPWIRE_RESULT_OVERRIDE"] = "PASS"
        try:
            r = _call_check()
        finally:
            if old is None:
                os.environ.pop("_META_TRIPWIRE_RESULT_OVERRIDE", None)
            else:
                os.environ["_META_TRIPWIRE_RESULT_OVERRIDE"] = old
        first_fail = r.get("first_failing_condition", "")
        self.assertNotEqual(
            first_fail, "f",
            f"Condition (f) must not block when meta-tripwire=PASS; "
            f"got first_failing_condition={first_fail!r}",
        )

    def test_condition_f_field_present(self):
        """check_release_ready() must return a condition_f field."""
        old = os.environ.get("_META_TRIPWIRE_RESULT_OVERRIDE")
        os.environ["_META_TRIPWIRE_RESULT_OVERRIDE"] = "PASS"
        try:
            r = _call_check()
        finally:
            if old is None:
                os.environ.pop("_META_TRIPWIRE_RESULT_OVERRIDE", None)
            else:
                os.environ["_META_TRIPWIRE_RESULT_OVERRIDE"] = old
        self.assertIn(
            "condition_f", r,
            "RELEASE-READY must return a 'condition_f' field for (f) detail.",
        )


# ---------------------------------------------------------------------------
# Group 4: condition (c) — PROOF-INTEGRITY wiring
# ---------------------------------------------------------------------------

class TestConditionC_ProofIntegrity(unittest.TestCase):
    """Condition (c): wired to PROOF-INTEGRITY check result."""

    def test_held_when_proof_integrity_fail(self):
        """Gate must report held on condition (c) when PROOF-INTEGRITY=FAIL."""
        r = _call_check({"_RELEASE_READY_PROOF_INTEGRITY_RESULT": "FAIL"})
        result = r.get("result", "")
        self.assertNotEqual(
            result, "PASS",
            f"Gate should not PASS when proof-integrity=FAIL; "
            f"got result={result!r}, detail={r.get('detail')!r}",
        )

    def test_first_failing_is_c_on_fail(self):
        """first_failing_condition must be 'c' when PROOF-INTEGRITY=FAIL."""
        r = _call_check({"_RELEASE_READY_PROOF_INTEGRITY_RESULT": "FAIL"})
        self.assertEqual(
            r.get("first_failing_condition"), "c",
            f"first_failing_condition must be 'c' on PROOF-INTEGRITY FAIL; "
            f"got {r.get('first_failing_condition')!r}",
        )

    def test_warn_does_not_block_condition_c(self):
        """PROOF-INTEGRITY WARN (no data) must not block condition (c)."""
        r = _call_check({"_RELEASE_READY_PROOF_INTEGRITY_RESULT": "WARN"})
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
    """With all conditions injected as pass, gate should PASS with verdict=true."""

    def test_pass_when_all_conditions_pass(self):
        """Gate must PASS when all conditions forced to pass via env injection."""
        r = _call_check()  # defaults inject all as PASS
        result = r.get("result", "")
        self.assertEqual(
            result, "PASS",
            f"Gate must PASS when all conditions forced to pass; "
            f"got result={result!r}, detail={r.get('detail')!r}",
        )

    def test_verdict_true_when_pass(self):
        """verdict field must be 'true' when gate PASSes."""
        r = _call_check()
        if r.get("result") == "PASS":
            self.assertEqual(
                r.get("verdict"), "true",
                f"verdict must be 'true' on PASS; got {r.get('verdict')!r}",
            )

    def test_first_failing_empty_when_pass(self):
        """first_failing_condition must be empty string when gate PASSes."""
        r = _call_check()
        if r.get("result") == "PASS":
            self.assertEqual(
                r.get("first_failing_condition", ""), "",
                f"first_failing_condition must be '' on PASS; "
                f"got {r.get('first_failing_condition')!r}",
            )


# ---------------------------------------------------------------------------
# Group 6: condition (a) — CI check
# ---------------------------------------------------------------------------

class TestConditionA_CI(unittest.TestCase):
    """Condition (a): CI green on develop HEAD."""

    def test_held_when_ci_fail(self):
        """Gate must hold when CI result is forced to FAIL."""
        r = _call_check({"_RELEASE_READY_CI_RESULT": "FAIL"})
        self.assertNotEqual(
            r.get("result"), "PASS",
            f"Gate should not PASS when CI=FAIL; got {r.get('result')!r}",
        )

    def test_first_failing_is_a_on_ci_fail(self):
        """first_failing_condition must be 'a' when CI fails first."""
        r = _call_check({"_RELEASE_READY_CI_RESULT": "FAIL"})
        self.assertEqual(
            r.get("first_failing_condition"), "a",
            f"first_failing_condition must be 'a' when CI=FAIL; "
            f"got {r.get('first_failing_condition')!r}",
        )


# ---------------------------------------------------------------------------
# Group 7: condition (b) — test suite
# ---------------------------------------------------------------------------

class TestConditionB_TestSuite(unittest.TestCase):
    """Condition (b): full test suite passes (ADR-0067 D1)."""

    def test_held_when_tests_fail(self):
        """Gate must hold when test suite result is forced to FAIL."""
        r = _call_check({"_RELEASE_READY_TESTS_RESULT": "FAIL"})
        self.assertNotEqual(
            r.get("result"), "PASS",
            f"Gate should not PASS when tests=FAIL; got {r.get('result')!r}",
        )

    def test_first_failing_is_b_on_tests_fail(self):
        """first_failing_condition must be 'b' when tests fail (CI passes)."""
        r = _call_check({"_RELEASE_READY_TESTS_RESULT": "FAIL"})
        self.assertEqual(
            r.get("first_failing_condition"), "b",
            f"first_failing_condition must be 'b' when tests=FAIL (CI pass); "
            f"got {r.get('first_failing_condition')!r}",
        )


# ---------------------------------------------------------------------------
# Group 8: condition (d) — green-develop streak
# ---------------------------------------------------------------------------

class TestConditionD_Streak(unittest.TestCase):
    """Condition (d): green-develop streak intact."""

    def test_held_when_streak_fail(self):
        """Gate must hold when streak result is forced to FAIL."""
        r = _call_check({"_RELEASE_READY_STREAK_RESULT": "FAIL"})
        self.assertNotEqual(
            r.get("result"), "PASS",
            f"Gate should not PASS when streak=FAIL; got {r.get('result')!r}",
        )

    def test_first_failing_is_d_on_streak_fail(self):
        """first_failing_condition must be 'd' when streak fails (a/b/c pass)."""
        r = _call_check({"_RELEASE_READY_STREAK_RESULT": "FAIL"})
        self.assertEqual(
            r.get("first_failing_condition"), "d",
            f"first_failing_condition must be 'd' when streak=FAIL; "
            f"got {r.get('first_failing_condition')!r}",
        )


# ---------------------------------------------------------------------------
# Group 9: first-fail ordering — a before b before c before d before e
# ---------------------------------------------------------------------------

class TestFirstFailOrdering(unittest.TestCase):
    """The gate reports the FIRST failing condition in order a→b→c→d→e."""

    def test_a_takes_precedence_over_b(self):
        """When both (a) CI and (b) tests fail, first_failing_condition == 'a'."""
        r = _call_check({
            "_RELEASE_READY_CI_RESULT": "FAIL",
            "_RELEASE_READY_TESTS_RESULT": "FAIL",
        })
        self.assertEqual(
            r.get("first_failing_condition"), "a",
            "When both (a) and (b) fail, first_failing must be 'a'",
        )

    def test_b_takes_precedence_over_c(self):
        """When (a) passes and both (b) tests and (c) proof fail, first == 'b'."""
        r = _call_check({
            "_RELEASE_READY_TESTS_RESULT": "FAIL",
            "_RELEASE_READY_PROOF_INTEGRITY_RESULT": "FAIL",
        })
        self.assertEqual(
            r.get("first_failing_condition"), "b",
            "When (a) passes and both (b)/(c) fail, first_failing must be 'b'",
        )


# ---------------------------------------------------------------------------
# Group 10: promote.sh guard
# ---------------------------------------------------------------------------

class TestPromoteShGuard(unittest.TestCase):
    """promote.sh must refuse to promote unless RELEASE-READY is true."""

    def test_promote_sh_contains_release_ready_reference(self):
        """tools/promote.sh must reference RELEASE-READY as a pre-flight guard."""
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

    def test_promote_sh_guard_invokes_health_check(self):
        """promote.sh guard must invoke health.py or the --check flag."""
        content = PROMOTE_SH.read_text(encoding="utf-8")
        has_health = "health.py" in content or "--check" in content
        self.assertTrue(
            has_health,
            "promote.sh RELEASE-READY guard must invoke health.py --check RELEASE-READY",
        )

    def test_promote_sh_refuses_when_force_fail(self):
        """promote.sh must exit non-zero when _RELEASE_READY_FORCE_FAIL=1.

        Uses _PROMOTE_SH_SKIP_PUSH=1 so the test does not actually push to git.
        """
        if not PROMOTE_SH.exists():
            self.skipTest("promote.sh not found")
        env = os.environ.copy()
        env["_PROMOTE_SH_SKIP_PUSH"] = "1"
        env["_RELEASE_READY_FORCE_FAIL"] = "1"
        result = subprocess.run(
            ["bash", str(PROMOTE_SH)],
            capture_output=True, text=True, env=env,
            cwd=str(REPO_ROOT), timeout=30,
        )
        self.assertNotEqual(
            result.returncode, 0,
            f"promote.sh must exit non-zero when RELEASE-READY is not true; "
            f"got exit 0. stdout={result.stdout[:200]!r} stderr={result.stderr[:200]!r}",
        )


# ---------------------------------------------------------------------------
# Group 11: ship/SKILL.md documents green-develop → auto-promote step
# ---------------------------------------------------------------------------

class TestShipSkillDocumentation(unittest.TestCase):
    """ship/SKILL.md must document the RELEASE-READY gate + auto-promote step."""

    def test_ship_skill_mentions_release_ready(self):
        """ship/SKILL.md must mention RELEASE-READY ≥1 time."""
        self.assertTrue(
            SHIP_SKILL.exists(),
            f"ship/SKILL.md must exist at {SHIP_SKILL}",
        )
        content = SHIP_SKILL.read_text(encoding="utf-8")
        self.assertGreaterEqual(
            content.lower().count("release-ready"), 1,
            "ship/SKILL.md must mention RELEASE-READY ≥1 time (gate documented)",
        )

    def test_ship_skill_documents_promote_step(self):
        """ship/SKILL.md must document the auto-promote/fast-forward step."""
        content = SHIP_SKILL.read_text(encoding="utf-8")
        has_promote = (
            "auto-promot" in content.lower()
            or "promote.sh" in content
            or "fast-forward" in content.lower()
        )
        self.assertTrue(
            has_promote,
            "ship/SKILL.md must document the auto-promote (fast-forward) step",
        )


if __name__ == "__main__":
    unittest.main()
