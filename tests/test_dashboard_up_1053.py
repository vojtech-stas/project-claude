"""
tests/test_dashboard_up_1053.py

Regression tests for slice #1053 — dashboard-up.ps1 managed lifecycle helper:
  1. tools/dashboard-up.ps1 exists and parses under PowerShell 5.1
     (Get-Command -Syntax succeeds with no parse error).
  2. -CheckOnly mode against a free port (nothing listening) prints a
     "would launch" decision and touches nothing (exit 0).
  3. -CheckOnly mode against a stub /api/meta HTTP server whose sha matches
     origin/develop HEAD prints an "already up + fresh" decision (exit 0).
  4. .claude/hooks/dashboard-autostart.sh references dashboard-up.ps1 (wiring
     acceptance criterion).

Per ADR-0067 D2: this test file is committed BEFORE the implementation.
These tests FAIL before tools/dashboard-up.ps1 exists and PASS after.

Runner: stdlib unittest + pytest compatible.
  python -m pytest tests/test_dashboard_up_1053.py -v
"""

import http.server
import json
import shutil
import socket
import socketserver
import subprocess
import threading
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
SCRIPT_PATH = REPO_ROOT / "tools" / "dashboard-up.ps1"
HOOK_PATH = REPO_ROOT / ".claude" / "hooks" / "dashboard-autostart.sh"

POWERSHELL = shutil.which("powershell") or shutil.which("pwsh")


def _free_port() -> int:
    """Find a free TCP port on 127.0.0.1 (test doesn't fight real listeners)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _git_develop_sha() -> str:
    out = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "rev-parse", "origin/develop"],
        capture_output=True, text=True, check=True,
    )
    return out.stdout.strip()


class _MetaStubHandler(http.server.BaseHTTPRequestHandler):
    """Tiny /api/meta stub serving a fixed sha for -CheckOnly freshness tests."""

    sha = "0000000000000000000000000000000000000000"

    def do_GET(self):  # noqa: N802 (stdlib method name)
        if self.path == "/api/meta":
            body = json.dumps(
                {"sha": self.sha, "started_at": "test", "stale": False}
            ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, *args):  # silence stdlib default logging
        pass


def _run_checkonly(port: int) -> subprocess.CompletedProcess:
    """Invoke dashboard-up.ps1 -CheckOnly with DASH_PORT=<port>."""
    import os

    env = dict(os.environ)
    env["DASH_PORT"] = str(port)
    return subprocess.run(
        [POWERSHELL, "-NoProfile", "-File", str(SCRIPT_PATH), "-CheckOnly"],
        capture_output=True, text=True, env=env, timeout=30,
    )


@unittest.skipUnless(POWERSHELL, "powershell/pwsh not available on this system")
class TestDashboardUpScript(unittest.TestCase):

    def test_script_exists(self):
        """tools/dashboard-up.ps1 must exist."""
        self.assertTrue(
            SCRIPT_PATH.exists(),
            f"tools/dashboard-up.ps1 not found at {SCRIPT_PATH}",
        )

    def test_script_parses(self):
        """Script must parse under PowerShell (Get-Command -Syntax succeeds)."""
        result = subprocess.run(
            [
                POWERSHELL, "-NoProfile", "-Command",
                f"Get-Command -Syntax '{SCRIPT_PATH}'",
            ],
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(
            result.returncode, 0,
            f"script failed to parse: stdout={result.stdout!r} stderr={result.stderr!r}",
        )

    def test_checkonly_nothing_listening_would_launch(self):
        """-CheckOnly against a free port (nothing listening) -> 'would launch'."""
        port = _free_port()
        result = _run_checkonly(port)
        self.assertEqual(
            result.returncode, 0,
            f"exit={result.returncode} stdout={result.stdout!r} stderr={result.stderr!r}",
        )
        self.assertIn(
            "would launch", result.stdout.lower(),
            f"expected 'would launch' decision in stdout: {result.stdout!r}",
        )

    def test_checkonly_stub_matching_sha_already_fresh(self):
        """-CheckOnly against a stub /api/meta serving matching sha -> 'already up + fresh'."""
        dev_sha = _git_develop_sha()
        port = _free_port()

        handler_cls = type("_Handler", (_MetaStubHandler,), {"sha": dev_sha})
        httpd = socketserver.TCPServer(("127.0.0.1", port), handler_cls)
        httpd.timeout = 10

        def _serve_one():
            httpd.handle_request()

        t = threading.Thread(target=_serve_one, daemon=True)
        t.start()

        try:
            result = _run_checkonly(port)
        finally:
            httpd.server_close()
            t.join(timeout=5)

        self.assertEqual(
            result.returncode, 0,
            f"exit={result.returncode} stdout={result.stdout!r} stderr={result.stderr!r}",
        )
        self.assertIn(
            "already up", result.stdout.lower(),
            f"expected 'already up + fresh' decision in stdout: {result.stdout!r}",
        )
        self.assertIn(
            "fresh", result.stdout.lower(),
            f"expected 'fresh' in decision output: {result.stdout!r}",
        )

    def test_hook_wires_dashboard_up_ps1(self):
        """dashboard-autostart.sh must reference dashboard-up.ps1 (delegation wiring)."""
        text = HOOK_PATH.read_text(encoding="utf-8")
        self.assertIn(
            "dashboard-up.ps1", text,
            "dashboard-autostart.sh must delegate to tools/dashboard-up.ps1 "
            "on Windows/PowerShell-available per slice #1053.",
        )


if __name__ == "__main__":
    unittest.main()
