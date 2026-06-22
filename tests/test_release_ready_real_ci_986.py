"""
tests/test_release_ready_real_ci_986.py

Regression tests for issue #986 — RELEASE-READY condition (a) must reflect
the REAL GitHub-Actions `ci` conclusion for develop's HEAD, not a local run
of tools/ci-checks.sh.

Per ADR-0067 D2/D3: test commit precedes fix commit in branch history.
These tests are WRITTEN TO FAIL before the fix lands and PASS after.

Problem (#986):
  condition (a) previously shelled `tools/ci-checks.sh` locally.  Locally
  pytest is installed so it passes — but the GitHub-Actions `ci` job (which
  runs `python -m unittest discover`) carries no pytest, and can be RED.
  The result: a locally-green / GitHub-red divergence silently reads as
  promotable.  This is the "dishonest measurement" the make-real pivot
  (ADR-0071) targets.

Fix shape (dashboard/health.py only):
  1. A new MODULE-LEVEL function `_fetch_github_ci_conclusion(repo_root)`
     queries GitHub for the `ci` check conclusion on develop's HEAD by:
       a. fetching latest merged PRs to develop
          (`gh pr list --base develop --state merged --limit N`)
       b. matching the one whose `mergeCommit.oid` equals `origin/develop` HEAD
       c. running `gh pr checks <n> --json name,state` and returning
          "pass" / "fail" / "unavailable" based on the `ci` entry.
  2. check_release_ready() condition (a) calls `_fetch_github_ci_conclusion`
     and uses the result.  The env-var override `_RELEASE_READY_CI_RESULT`
     still bypasses everything (existing injection seam preserved).
  3. Honest fallback: if gh is unavailable OR no matching PR found, fall back
     to the local ci-checks.sh run BUT label the detail clearly
     "(local fallback — no GitHub ci run found)".
  4. detail string must name the SOURCE ("GitHub ci=pass/fail" vs
     "local fallback").

Test structure:
  (a) when GitHub ci=pass  → condition (a) passes, detail names GitHub
  (b) when GitHub ci=fail  → condition (a) FAILS, detail names GitHub
  (c) when gh unavailable  → falls back to local, detail names "local fallback"
  (d) _fetch_github_ci_conclusion exists as a module-level function (seam check)

All tests monkeypatch `_fetch_github_ci_conclusion` via the env-var injection
seam or via direct module attribute injection — NO real gh calls.

Runner: stdlib unittest + pytest compatible.
  python -m pytest tests/test_release_ready_real_ci_986.py -v
  python -m unittest tests.test_release_ready_real_ci_986
"""

import importlib
import os
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent

# Ensure dashboard/ is importable.
_DASHBOARD_DIR = str(REPO_ROOT / "dashboard")
if _DASHBOARD_DIR not in sys.path:
    sys.path.insert(0, _DASHBOARD_DIR)


# ---------------------------------------------------------------------------
# Helper: load/reload health module and call check_release_ready() with
# temporary env-var overrides.  All conditions except (a) are defaulted to
# PASS so we can isolate condition (a) behaviour.
# ---------------------------------------------------------------------------

def _call_check_with_gh_mock(fetch_fn, extra_env=None):
    """Reload health, inject fetch_fn as _fetch_github_ci_conclusion, call check_release_ready.

    All conditions except (a) are injected as PASS so they don't interfere.
    fetch_fn replaces the module-level _fetch_github_ci_conclusion attribute.
    """
    env_defaults = {
        "_RELEASE_READY_TESTS_RESULT": "PASS",
        "_RELEASE_READY_PROOF_INTEGRITY_RESULT": "PASS",
        "_RELEASE_READY_STREAK_RESULT": "PASS",
        "_RELEASE_READY_NEEDS_HUMAN_COUNT": "0",
        "_META_TRIPWIRE_RESULT_OVERRIDE": "PASS",
    }
    # Clear the CI override so condition (a) is driven by the function, not env.
    env_clear = {"_RELEASE_READY_CI_RESULT": ""}
    env_patch = {**env_defaults, **env_clear, **(extra_env or {})}

    old_vals = {}
    for k, v in env_patch.items():
        old_vals[k] = os.environ.get(k)
        if v == "":
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
    try:
        import health as _h
        importlib.reload(_h)
        # Inject the mock fetch function at module level.
        _h._fetch_github_ci_conclusion = fetch_fn
        return _h.check_release_ready()
    finally:
        for k, orig in old_vals.items():
            if orig is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = orig


class TestReleaseReadyRealCi986(unittest.TestCase):
    """condition (a) must consult GitHub ci conclusion, not only local ci-checks.sh."""

    # -----------------------------------------------------------------------
    # (d) Seam check: _fetch_github_ci_conclusion must exist at module level
    # -----------------------------------------------------------------------

    def test_fetch_fn_exists_at_module_level(self):
        """dashboard/health.py must expose _fetch_github_ci_conclusion at module level.

        This is the injectable/monkeypatchable seam that allows tests (and future
        callers) to mock the GitHub API call without subprocess patching.
        """
        import health as _h
        importlib.reload(_h)
        self.assertTrue(
            hasattr(_h, "_fetch_github_ci_conclusion"),
            "_fetch_github_ci_conclusion must be a module-level function in "
            "dashboard/health.py (issue #986: needed as injection seam for tests "
            "and to separate the gh-query from check_release_ready logic)",
        )
        self.assertTrue(
            callable(getattr(_h, "_fetch_github_ci_conclusion", None)),
            "_fetch_github_ci_conclusion must be callable",
        )

    # -----------------------------------------------------------------------
    # (a) GitHub ci=pass → condition (a) passes, detail names GitHub source
    # -----------------------------------------------------------------------

    def test_github_ci_pass_makes_condition_a_pass(self):
        """When _fetch_github_ci_conclusion returns 'pass', condition (a) must pass.

        The detail string must mention 'GitHub' or 'github' (case-insensitive)
        to make the measurement source explicit.  A vague 'ci-checks.sh exit=0'
        is insufficient — the caller cannot tell if it was a local run or real CI.
        """
        def mock_gh_pass(repo_root):
            return "pass", "GitHub ci=pass (PR #983)"

        result = _call_check_with_gh_mock(mock_gh_pass)
        # Gate must be open (verdict=true, result=PASS)
        self.assertEqual(
            result.get("result"), "PASS",
            f"When GitHub ci=pass, RELEASE-READY should be PASS; got: {result}",
        )
        self.assertEqual(
            result.get("verdict"), "true",
            f"verdict must be 'true' when all conditions pass; got: {result}",
        )
        # detail must name GitHub as the source
        detail = result.get("detail", "")
        self.assertIn(
            "github", detail.lower(),
            f"condition (a) detail must name 'GitHub' as the source when using real CI; "
            f"got detail={detail!r}. A locally-green result would not satisfy #986.",
        )

    # -----------------------------------------------------------------------
    # (b) GitHub ci=fail → condition (a) FAILS even if local run would pass
    # -----------------------------------------------------------------------

    def test_github_ci_fail_makes_condition_a_fail(self):
        """When _fetch_github_ci_conclusion returns 'fail', condition (a) must FAIL.

        This is the core fix: the gate must be RED when real GitHub CI is red,
        regardless of what a local ci-checks.sh run would return.
        """
        def mock_gh_fail(repo_root):
            return "fail", "GitHub ci=failure (PR #983)"

        result = _call_check_with_gh_mock(mock_gh_fail)
        # Gate must be held (verdict=false, result=WARN)
        self.assertEqual(
            result.get("result"), "WARN",
            f"When GitHub ci=fail, RELEASE-READY must hold the gate (result=WARN); "
            f"got: {result}",
        )
        self.assertEqual(
            result.get("verdict"), "false",
            f"verdict must be 'false' when condition (a) fails; got: {result}",
        )
        self.assertEqual(
            result.get("first_failing_condition"), "a",
            f"first_failing_condition must be 'a'; got: {result}",
        )
        # detail must name GitHub as the source (not just local ci-checks)
        detail = result.get("detail", "")
        self.assertIn(
            "github", detail.lower(),
            f"condition (a) failure detail must name 'GitHub' as the source; "
            f"got detail={detail!r}",
        )

    # -----------------------------------------------------------------------
    # (c) gh unavailable → fallback to local, detail names "local fallback"
    # -----------------------------------------------------------------------

    def test_gh_unavailable_falls_back_to_local_with_label(self):
        """When gh is unavailable, fall back to local ci-checks.sh and label it.

        The fallback is honest: the detail string must contain 'local fallback'
        (case-insensitive) so the operator knows the measurement is not backed
        by real GitHub CI.  A false-green from a stale fallback is better than
        a misleading 'GitHub ci=pass'.
        """
        def mock_gh_unavailable(repo_root):
            return "unavailable", "gh CLI unavailable or no matching PR found"

        # We need check_release_ready to actually run local ci-checks when
        # the fetch returns "unavailable".  To avoid a real 300s ci-checks.sh
        # run, inject _RELEASE_READY_CI_RESULT ONLY if unavailable path hits
        # local fallback — but that would bypass the fallback path too.
        # Instead: mock gh unavailable AND inject the local result via env.
        # The test asserts the LABEL (detail contains "local fallback"), not
        # the pass/fail outcome, so we allow either PASS or WARN here — the
        # key constraint is the source label.
        #
        # Implementation note: the fix must check for "unavailable" return from
        # _fetch_github_ci_conclusion and then run local ci-checks.sh (or use
        # _RELEASE_READY_CI_RESULT env injection for tests).  We patch the env
        # so the local fallback sees a PASS, then verify the label is present.
        import health as _h
        importlib.reload(_h)

        env_defaults = {
            "_RELEASE_READY_TESTS_RESULT": "PASS",
            "_RELEASE_READY_PROOF_INTEGRITY_RESULT": "PASS",
            "_RELEASE_READY_STREAK_RESULT": "PASS",
            "_RELEASE_READY_NEEDS_HUMAN_COUNT": "0",
            "_META_TRIPWIRE_RESULT_OVERRIDE": "PASS",
        }
        old_vals = {}
        for k, v in env_defaults.items():
            old_vals[k] = os.environ.get(k)
            os.environ[k] = v
        # Remove CI override so fallback runs real local path (but we mock the fetch)
        old_ci = os.environ.pop("_RELEASE_READY_CI_RESULT", None)
        try:
            importlib.reload(_h)
            # Inject: gh unavailable
            _h._fetch_github_ci_conclusion = mock_gh_unavailable
            # Also make the local ci-checks.sh succeed instantly via a patch
            # We can't easily run real ci-checks here.  Instead, we verify that
            # the fallback label appears REGARDLESS of the local outcome.
            # Strategy: override the local subprocess to succeed, verify label.
            import unittest.mock as _mock
            completed = type('CP', (), {'returncode': 0, 'stdout': '', 'stderr': ''})()
            with _mock.patch("subprocess.run", return_value=completed):
                result = _h.check_release_ready()
        finally:
            for k, orig in old_vals.items():
                if orig is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = orig
            if old_ci is not None:
                os.environ["_RELEASE_READY_CI_RESULT"] = old_ci

        # The condition_a field (or detail when gate is held) must contain
        # "local fallback" when gh is unavailable, so the operator can see the
        # measurement source explicitly.
        condition_a = (result.get("condition_a", "") or "").lower()
        detail = (result.get("detail", "") or "").lower()
        all_text = condition_a + " " + detail
        self.assertIn(
            "local fallback",
            all_text,
            f"When gh is unavailable, condition (a) source label must contain "
            f"'local fallback' (in condition_a or detail field) to be honest "
            f"about the measurement source; "
            f"got condition_a={result.get('condition_a')!r}, "
            f"detail={result.get('detail')!r}. Issue #986: dishonest "
            f"measurement is the root cause — the fallback must label itself.",
        )

    # -----------------------------------------------------------------------
    # Source-label check: health.py source must reference _fetch_github_ci_conclusion
    # in the check_release_ready function body (not a dead import).
    # -----------------------------------------------------------------------

    def test_fetch_fn_called_in_check_release_ready(self):
        """_fetch_github_ci_conclusion must appear inside check_release_ready body in source.

        Prevents the case where the function is defined but never wired in.
        """
        health_src = (REPO_ROOT / "dashboard" / "health.py").read_text(encoding="utf-8")
        # Find check_release_ready body: everything after its def line.
        fn_marker = "def check_release_ready("
        idx = health_src.find(fn_marker)
        self.assertGreater(
            idx, 0,
            "check_release_ready function not found in health.py",
        )
        fn_body = health_src[idx:]
        self.assertIn(
            "_fetch_github_ci_conclusion",
            fn_body,
            "_fetch_github_ci_conclusion must be called inside check_release_ready "
            "(not a dead helper). Issue #986: the fix must wire the gh-conclusion "
            "fetch into condition (a).",
        )


if __name__ == "__main__":
    unittest.main()
