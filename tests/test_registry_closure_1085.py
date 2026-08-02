"""
Regression tests for PRD #1075 criteria 10c/10d / slice #1085 — registry
closure + integrity fixes:

  10c. STREAM-LIVENESS + DEPLOY-HANDSHAKE (+ RECORD-VS-GH, already landed by
       slice #1081) are all present in CHECK_REGISTRY.
  10d. CRITIC-HEALTH (function existed since slice #779, key was never added
       to CHECK_REGISTRY) is now registered.

This test file FAILS on develop before slice #1085 (STREAM-LIVENESS and
DEPLOY-HANDSHAKE do not exist at all; CRITIC-HEALTH is absent from
CHECK_REGISTRY even though check_critic_health() is defined) and PASSES after.

Runner: stdlib unittest + pytest compatible.
  python -m pytest tests/test_registry_closure_1085.py -v
"""

import importlib
import os
import subprocess
import sys
import unittest

_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_TESTS_DIR)
_DASHBOARD_DIR = os.path.join(_REPO_ROOT, "dashboard")
if _DASHBOARD_DIR not in sys.path:
    sys.path.insert(0, _DASHBOARD_DIR)


def _reimport(module_name: str):
    if module_name in sys.modules:
        del sys.modules[module_name]
    return importlib.import_module(module_name)


class TestRegistryClosure(unittest.TestCase):
    """CHECK_REGISTRY must contain the three new/newly-registered rows."""

    def test_stream_liveness_registered(self):
        health = _reimport("health")
        self.assertIn("STREAM-LIVENESS", health.CHECK_REGISTRY)
        self.assertTrue(callable(health.CHECK_REGISTRY["STREAM-LIVENESS"]))

    def test_deploy_handshake_registered(self):
        health = _reimport("health")
        self.assertIn("DEPLOY-HANDSHAKE", health.CHECK_REGISTRY)
        self.assertTrue(callable(health.CHECK_REGISTRY["DEPLOY-HANDSHAKE"]))

    def test_critic_health_registered(self):
        """Root-cause fix (audit-found defect #1 of 2): the function existed
        since slice #779 but was never added to CHECK_REGISTRY."""
        health = _reimport("health")
        self.assertIn("CRITIC-HEALTH", health.CHECK_REGISTRY)
        self.assertIs(health.CHECK_REGISTRY["CRITIC-HEALTH"], health.check_critic_health)

    def test_record_vs_gh_still_registered(self):
        """Sibling check from slice #1081 must not have regressed."""
        health = _reimport("health")
        self.assertIn("RECORD-VS-GH", health.CHECK_REGISTRY)

    def test_grep_count_at_least_three(self):
        """Mirrors the PRD's own acceptance grep:
        grep -cE 'STREAM-LIVENESS|DEPLOY-HANDSHAKE|RECORD-VS-GH' dashboard/health.py >= 3
        """
        health_py = os.path.join(_DASHBOARD_DIR, "health.py")
        text = open(health_py, encoding="utf-8").read()
        count = sum(
            1 for line in text.splitlines()
            if "STREAM-LIVENESS" in line or "DEPLOY-HANDSHAKE" in line or "RECORD-VS-GH" in line
        )
        self.assertGreaterEqual(count, 3, f"expected >=3 matching lines, got {count}")


class TestCliSurface(unittest.TestCase):
    """python dashboard/health.py --list / --check <id> CLI surface."""

    def test_list_shows_all_three_new_ids(self):
        result = subprocess.run(
            [sys.executable, os.path.join(_DASHBOARD_DIR, "health.py"), "--list"],
            capture_output=True, text=True,
        )
        self.assertEqual(0, result.returncode, msg=result.stderr)
        for expected in ("STREAM-LIVENESS", "DEPLOY-HANDSHAKE", "CRITIC-HEALTH"):
            self.assertIn(expected, result.stdout, msg=f"--list missing {expected}")

    def test_check_stream_liveness_runs(self):
        result = subprocess.run(
            [sys.executable, os.path.join(_DASHBOARD_DIR, "health.py"),
             "--check", "STREAM-LIVENESS"],
            capture_output=True, text=True, timeout=30,
        )
        self.assertIn(result.returncode, (0, 1), msg=result.stderr)
        self.assertIn("STREAM-LIVENESS", result.stdout)

    def test_check_deploy_handshake_runs(self):
        result = subprocess.run(
            [sys.executable, os.path.join(_DASHBOARD_DIR, "health.py"),
             "--check", "DEPLOY-HANDSHAKE"],
            capture_output=True, text=True, timeout=30,
        )
        self.assertIn(result.returncode, (0, 1), msg=result.stderr)
        self.assertIn("DEPLOY-HANDSHAKE", result.stdout)


class TestCheckDeployHandshakeWrapper(unittest.TestCase):
    """dashboard/health.py's check_deploy_handshake() python-level wrapper."""

    def test_returns_well_formed_dict_against_real_repo(self):
        """Real (non-fixture) invocation: --check-only is read-only, safe to
        run against the actual repo. Result must be a well-formed dict."""
        health = _reimport("health")
        result = health.check_deploy_handshake()
        self.assertEqual("DEPLOY-HANDSHAKE", result["id"])
        self.assertIn(result["result"], ("PASS", "WARN", "FAIL"))
        self.assertIn("detail", result)

    def test_parses_fail_status_from_script_output(self):
        """Monkeypatch subprocess.run to simulate a FAIL --check-only response
        and confirm the wrapper parses STATUS/detail correctly."""
        health = _reimport("health")

        class _FakeResult:
            returncode = 0
            stdout = "STATUS: FAIL\ndetail: .claude/hooks/ content-hash MISMATCH\n"
            stderr = ""

        orig_run = health.subprocess.run
        try:
            health.subprocess.run = lambda *a, **k: _FakeResult()
            result = health.check_deploy_handshake()
        finally:
            health.subprocess.run = orig_run

        self.assertEqual("FAIL", result["result"])
        self.assertIn("MISMATCH", result["detail"])

    def test_parses_pass_status_from_script_output(self):
        health = _reimport("health")

        class _FakeResult:
            returncode = 0
            stdout = "STATUS: PASS\ndetail: branch=develop hooksPath=.githooks root=/x\n"
            stderr = ""

        orig_run = health.subprocess.run
        try:
            health.subprocess.run = lambda *a, **k: _FakeResult()
            result = health.check_deploy_handshake()
        finally:
            health.subprocess.run = orig_run

        self.assertEqual("PASS", result["result"])
        self.assertIn("branch=develop", result["detail"])

    def test_unparsable_output_warns_not_crashes(self):
        health = _reimport("health")

        class _FakeResult:
            returncode = 1
            stdout = "some garbage that doesn't match the contract\n"
            stderr = "boom"

        orig_run = health.subprocess.run
        try:
            health.subprocess.run = lambda *a, **k: _FakeResult()
            result = health.check_deploy_handshake()
        finally:
            health.subprocess.run = orig_run

        self.assertEqual("WARN", result["result"])


if __name__ == "__main__":
    unittest.main()
