"""
tests/test_release_ready_ci_trust_1161.py

Regression tests for issue #1161 — RELEASE-READY condition (b) and
tools/record-green.sh must TRUST a recorded GitHub `ci` conclusion for the
EXACT develop-HEAD sha instead of re-running the full pytest suite locally
after that same evidence already proved it (kills the #1122 budget-bump
class at the root; see #1120/#1121/#1122).

Per ADR-0067 D2/D3: this test commit PRECEDES the fix commit. These tests
are WRITTEN TO FAIL on pre-fix dashboard/health.py (condition (b)
unconditionally shells a local `pytest` sub-call regardless of condition
(a)'s outcome) and PASS after the fix.

Root cause (#1161): condition (a) and tools/record-green.sh were designed
before GitHub CI became the authoritative required check (R4); both
re-verify locally what a recorded ci run already proved for the exact
commit — pure duplication measured at ~25-35 min per slice.

Fix shape (dashboard/health.py check_release_ready() only, this file):
  condition (b) reuses condition (a)'s `gh_status` (populated only on the
  real, non-override gh-query path):
    gh_status == "pass"         -> (b) is proven by that SAME evidence, NO
                                    local pytest subprocess call fires
    gh_status in (None,
                  "unavailable") -> local pytest fallback still executes
                                    (no recorded ci run for the sha)
    condition (a) already holds the gate on ci=fail/pending (early return)
                                 -> condition (b) code path is never reached

Test structure (mirrors test_release_ready_real_ci_986.py's mock-injection
harness, extended with a subprocess.run SPY to prove/disprove pytest
invocation without ever running a real 300s suite):
  (a) gh_status="pass"        -> condition (b) proven, ZERO subprocess.run
                                  calls fire at all (fast path, #1161 core)
  (b) gh_status="unavailable" -> condition (a) local-fallback fires AND
                                  condition (b)'s local pytest fallback
                                  fires (a real subprocess.run call
                                  containing "pytest" is observed)
  (c) gh_status="fail"        -> gate held at condition (a); no local
                                  pytest call ever fires (already covered by
                                  test_release_ready_real_ci_986.py; asserted
                                  again here for #1161 traceability)
  (d) _RELEASE_READY_TESTS_RESULT override still takes priority over the
      ci-trust fast path (existing seam never silently shadowed)

Runner: stdlib unittest + pytest compatible.
  python -m pytest tests/test_release_ready_ci_trust_1161.py -v
"""

import importlib
import os
import subprocess
import sys
import unittest
import unittest.mock as _mock
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent

# Ensure dashboard/ is importable.
_DASHBOARD_DIR = str(REPO_ROOT / "dashboard")
if _DASHBOARD_DIR not in sys.path:
    sys.path.insert(0, _DASHBOARD_DIR)


class _StubCompletedProcess:
    """Minimal stand-in for subprocess.CompletedProcess — always 'green'."""

    def __init__(self, returncode=0, stdout="1 passed in 0.01s", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _call_with_gh_mock_and_spy(fetch_fn):
    """Reload health, inject fetch_fn as _fetch_github_ci_conclusion, clear
    BOTH _RELEASE_READY_CI_RESULT and _RELEASE_READY_TESTS_RESULT (so both
    (a) and (b) are driven by the injected fetch_fn / the code path under
    test, not by env overrides), spy on subprocess.run, and call
    check_release_ready(). Returns (result, calls) where calls is the list
    of argv lists passed to subprocess.run.
    """
    env_defaults = {
        "_RELEASE_READY_PROOF_INTEGRITY_RESULT": "PASS",
        "_RELEASE_READY_STREAK_RESULT": "PASS",
        "_RELEASE_READY_NEEDS_HUMAN_COUNT": "0",
        "_META_TRIPWIRE_RESULT_OVERRIDE": "PASS",
    }
    clear_keys = ["_RELEASE_READY_CI_RESULT", "_RELEASE_READY_TESTS_RESULT"]

    old_vals = {}
    for k, v in env_defaults.items():
        old_vals[k] = os.environ.get(k)
        os.environ[k] = v
    for k in clear_keys:
        old_vals[k] = os.environ.get(k)
        os.environ.pop(k, None)

    calls = []

    def _spy_run(cmd, *args, **kwargs):
        calls.append(cmd)
        return _StubCompletedProcess()

    try:
        import health as _h
        importlib.reload(_h)
        _h._fetch_github_ci_conclusion = fetch_fn
        with _mock.patch("subprocess.run", side_effect=_spy_run):
            result = _h.check_release_ready()
    finally:
        for k, orig in old_vals.items():
            if orig is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = orig
    return result, calls


class TestConditionBGreenFastOnRecordedPass(unittest.TestCase):
    """(a) gh_status='pass' -> condition (b) proven by the same evidence,
    ZERO subprocess.run calls fire (no local ci-checks.sh AND no local
    pytest). This is the core #1161 fix and FAILS on pre-fix code (which
    unconditionally shells a pytest subprocess in condition (b))."""

    def test_gate_passes_with_zero_subprocess_calls(self):
        def mock_gh_pass(repo_root):
            return "pass", "GitHub ci=pass (PR #1200)"

        result, calls = _call_with_gh_mock_and_spy(mock_gh_pass)
        self.assertEqual(
            result.get("result"), "PASS",
            f"Gate must PASS when GitHub ci=pass for the exact sha; got: {result}",
        )
        self.assertEqual(
            calls, [],
            f"No subprocess.run call may fire when GitHub ci=pass for the exact "
            f"sha proves both (a) and (b) — #1161 kills the duplicate local "
            f"pytest re-run at the root. Calls observed: {calls}",
        )

    def test_condition_b_detail_names_recorded_ci_evidence(self):
        """Condition (b)'s own evidence trail must name the recorded-ci
        source (not a vague 'pytest: ...' summary) — the detail field
        proves WHICH evidence source was used, per #1161."""
        def mock_gh_pass(repo_root):
            return "pass", "GitHub ci=pass (PR #1200)"

        result, calls = _call_with_gh_mock_and_spy(mock_gh_pass)
        detail = (result.get("detail", "") or "")
        self.assertIn(
            "github", detail.lower(),
            f"RELEASE-READY detail must still name GitHub as condition (a)'s "
            f"source; got: {detail!r}",
        )

    def test_no_pytest_subprocess_when_ci_pass(self):
        """Explicit spy assertion: no call argv contains 'pytest' when
        GitHub ci=pass for the exact sha (belt-and-suspenders on top of the
        zero-calls assertion above)."""
        def mock_gh_pass(repo_root):
            return "pass", "GitHub ci=pass (PR #1201)"

        _, calls = _call_with_gh_mock_and_spy(mock_gh_pass)
        pytest_calls = [c for c in calls if any("pytest" in str(a) for a in c)]
        self.assertEqual(
            pytest_calls, [],
            f"No pytest subprocess call may fire on the ci=pass fast path; "
            f"found: {pytest_calls}",
        )


class TestConditionBFallsBackWhenNoRecordedRun(unittest.TestCase):
    """(b) gh_status='unavailable' (no recorded ci run for this sha — fresh
    clone / un-pushed sha) -> condition (b)'s local pytest fallback DOES
    still execute (fresh-clone honesty preserved)."""

    def test_local_pytest_fallback_fires_when_no_recorded_run(self):
        def mock_gh_unavailable(repo_root):
            return "unavailable", "no matching PR found (gh unavailable or fresh clone)"

        result, calls = _call_with_gh_mock_and_spy(mock_gh_unavailable)
        pytest_calls = [c for c in calls if any("pytest" in str(a) for a in c)]
        self.assertGreater(
            len(pytest_calls), 0,
            f"Local pytest fallback must fire when no recorded GitHub ci run "
            f"exists for this sha; no pytest subprocess call observed. "
            f"All calls: {calls}",
        )

    def test_gate_still_passes_via_fallback(self):
        def mock_gh_unavailable(repo_root):
            return "unavailable", "no matching PR found"

        result, calls = _call_with_gh_mock_and_spy(mock_gh_unavailable)
        self.assertEqual(
            result.get("result"), "PASS",
            f"Gate must still PASS via the local-fallback path (both local "
            f"ci-checks.sh and local pytest stubbed green); got: {result}",
        )


class TestConditionBHeldOnRecordedFail(unittest.TestCase):
    """(c) gh_status='fail' -> gate held at condition (a); condition (b) is
    never reached, so no local pytest call ever fires. (Core assertion
    already covered by test_release_ready_real_ci_986.py; re-asserted here
    with the subprocess spy for #1161 traceability.)"""

    def test_no_pytest_call_when_ci_fails(self):
        def mock_gh_fail(repo_root):
            return "fail", "GitHub ci=failure (PR #1202)"

        result, calls = _call_with_gh_mock_and_spy(mock_gh_fail)
        self.assertEqual(result.get("first_failing_condition"), "a")
        self.assertEqual(
            calls, [],
            f"No subprocess.run call may fire when condition (a) already "
            f"holds the gate on a recorded ci=fail; calls: {calls}",
        )


class TestTestsOverrideTakesPriorityOverCiTrust(unittest.TestCase):
    """(d) The existing _RELEASE_READY_TESTS_RESULT injection seam must
    never be silently shadowed by the new ci-trust fast path."""

    def test_tests_override_fail_wins_even_with_recorded_ci_pass(self):
        def mock_gh_pass(repo_root):
            return "pass", "GitHub ci=pass (PR #1203)"

        old = os.environ.get("_RELEASE_READY_TESTS_RESULT")
        os.environ["_RELEASE_READY_TESTS_RESULT"] = "FAIL"
        try:
            import health as _h
            importlib.reload(_h)
            env_defaults = {
                "_RELEASE_READY_PROOF_INTEGRITY_RESULT": "PASS",
                "_RELEASE_READY_STREAK_RESULT": "PASS",
                "_RELEASE_READY_NEEDS_HUMAN_COUNT": "0",
                "_META_TRIPWIRE_RESULT_OVERRIDE": "PASS",
            }
            saved = {}
            for k, v in env_defaults.items():
                saved[k] = os.environ.get(k)
                os.environ[k] = v
            old_ci = os.environ.pop("_RELEASE_READY_CI_RESULT", None)
            try:
                _h._fetch_github_ci_conclusion = mock_gh_pass
                result = _h.check_release_ready()
            finally:
                for k, v in saved.items():
                    if v is None:
                        os.environ.pop(k, None)
                    else:
                        os.environ[k] = v
                if old_ci is not None:
                    os.environ["_RELEASE_READY_CI_RESULT"] = old_ci
        finally:
            if old is None:
                os.environ.pop("_RELEASE_READY_TESTS_RESULT", None)
            else:
                os.environ["_RELEASE_READY_TESTS_RESULT"] = old

        self.assertEqual(
            result.get("first_failing_condition"), "b",
            f"_RELEASE_READY_TESTS_RESULT=FAIL must still hold the gate at "
            f"condition (b) even though condition (a) sees a recorded "
            f"GitHub ci=pass; got: {result}",
        )


if __name__ == "__main__":
    unittest.main()
