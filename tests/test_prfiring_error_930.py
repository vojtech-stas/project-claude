"""
Regression tests for slice #930 — PR-firing HTTP 500 on Windows cp1252 decode.

Root cause (#934): _gh_run() called subprocess.run(..., text=True) without
encoding="utf-8".  On Windows the default cp1252 codec raises UnicodeDecodeError
in a subprocess background reader thread when a PR body/comment contains bytes
outside cp1252 (emoji, Unicode arrows).  The decode failure sets r.stdout=None;
fetch_prd_firing() then calls None.strip() → AttributeError → HTTP 500.

Test groups:
  1. NullStdoutSafety — fetch_prd_firing() must NOT raise AttributeError when
     _gh_run() returns (0, None) for a PR detail fetch.
  2. EncodingParam    — _gh_run() must pass encoding="utf-8" + errors="replace"
     to subprocess.run() so non-UTF-8 bytes are replaced, not crash.
  3. ServerEndpoint   — /api/prd-firing route returns HTTP 200 (static route
     check, no live bind).

Runner: stdlib unittest + pytest compatible.
  python -m pytest tests/test_prfiring_error_930.py -v
"""

import ast
import json
import sys
import unittest
import unittest.mock
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
# Group 1: NullStdoutSafety — null stdout must NOT crash fetch_prd_firing()
# ---------------------------------------------------------------------------

class TestNullStdoutSafety(unittest.TestCase):
    """fetch_prd_firing() must survive _gh_run() returning (0, None) for PR detail.

    This is the exact failure mode: subprocess.run returns rc=0 but stdout=None
    because the Windows cp1252 decoder raised UnicodeDecodeError in a reader
    thread.  Before the fix, fetch_prd_firing() called None.strip() -> crash.
    After the fix, it must treat None as empty and fall back gracefully.
    """

    def setUp(self):
        _inject_dashboard()
        import prd_firing as _pf
        self._pf = _pf

    def _make_pr_list_json(self, pr_numbers):
        """Build gh pr list JSON output for given PR numbers."""
        return json.dumps([
            {"number": n, "title": f"feat(test): pr {n}",
             "createdAt": "2026-06-18T00:00:00Z", "mergedAt": None}
            for n in pr_numbers
        ])

    def test_null_stdout_does_not_raise(self):
        """When _gh_run returns (0, None) for PR detail, no AttributeError raised."""
        pf = self._pf
        # _gh_run returns: (0, valid list JSON) for pr list, then (0, None) for PR detail
        call_count = [0]
        pr_list_json = self._make_pr_list_json([893])

        def fake_gh_run(args, timeout=30):
            call_count[0] += 1
            if call_count[0] == 1:
                # First call: pr list — returns valid JSON
                return 0, pr_list_json
            else:
                # Subsequent calls: PR detail — returns None (UnicodeDecodeError scenario)
                return 0, None

        # Clear any existing cache for this limit
        with pf._cache_lock:
            pf._cache.pop(5, None)

        with unittest.mock.patch.object(pf, "_gh_run", side_effect=fake_gh_run):
            try:
                result = pf.fetch_prd_firing(limit=5)
            except AttributeError as e:
                self.fail(
                    f"fetch_prd_firing() must NOT raise AttributeError when "
                    f"_gh_run returns (0, None): {e}"
                )

        self.assertIsInstance(result, dict,
                              "fetch_prd_firing() must return a dict")
        self.assertIn("prs", result,
                      "result must have 'prs' key")
        self.assertIn("pr_count", result,
                      "result must have 'pr_count' key")

    def test_null_stdout_returns_dict_not_raises(self):
        """Result with null-stdout PR is still a valid payload (graceful fallback)."""
        pf = self._pf
        pr_list_json = self._make_pr_list_json([893, 870])
        calls = [0]

        def fake_gh_run(args, timeout=30):
            calls[0] += 1
            if calls[0] == 1:
                return 0, pr_list_json
            # All detail calls return None
            return 0, None

        with pf._cache_lock:
            pf._cache.pop(5, None)

        with unittest.mock.patch.object(pf, "_gh_run", side_effect=fake_gh_run):
            result = pf.fetch_prd_firing(limit=5)

        # Must be a valid payload with at least the required keys
        self.assertIsInstance(result.get("prs"), list)
        self.assertIsInstance(result.get("pr_count"), int)
        self.assertIn("fetched_at", result)

    def test_mixed_null_and_valid_returns_correct_count(self):
        """PRs with valid stdout are included; null-stdout PRs fall back to stub."""
        pf = self._pf
        pr_list_json = self._make_pr_list_json([893, 933])
        calls = [0]

        valid_detail = json.dumps({
            "number": 933,
            "title": "feat(dash): firing who",
            "createdAt": "2026-06-18T04:58:22Z",
            "mergedAt": "2026-06-18T05:07:11Z",
            "body": "Closes #929",
            "comments": [],
        })

        def fake_gh_run(args, timeout=30):
            calls[0] += 1
            if calls[0] == 1:
                # pr list
                return 0, pr_list_json
            # Detail: first PR gets None, second gets valid JSON
            if calls[0] == 2:
                return 0, None
            return 0, valid_detail

        with pf._cache_lock:
            pf._cache.pop(5, None)

        with unittest.mock.patch.object(pf, "_gh_run", side_effect=fake_gh_run):
            result = pf.fetch_prd_firing(limit=5)

        # Both PRs should produce timeline entries (null-stdout falls back to stub)
        self.assertEqual(result.get("pr_count"), 2,
                         f"Both PRs must produce timelines; got pr_count={result.get('pr_count')}")


# ---------------------------------------------------------------------------
# Group 2: EncodingParam — _gh_run must use UTF-8 with error replacement
# ---------------------------------------------------------------------------

class TestEncodingParam(unittest.TestCase):
    """_gh_run() must call subprocess.run with encoding='utf-8' + errors='replace'.

    This ensures bytes outside cp1252 (e.g. emoji, 0x90 byte) are silently
    replaced rather than raising UnicodeDecodeError in the reader thread.
    """

    def setUp(self):
        _inject_dashboard()
        import prd_firing as _pf
        self._pf = _pf

    def test_gh_run_passes_utf8_encoding(self):
        """_gh_run must pass encoding='utf-8' to subprocess.run (source text check)."""
        src = (DASHBOARD_DIR / "prd_firing.py").read_text(encoding="utf-8")
        # After the fix, the source must contain encoding="utf-8"
        self.assertIn(
            'encoding="utf-8"',
            src,
            "_gh_run() in prd_firing.py must pass encoding='utf-8' to subprocess.run",
        )

    def test_gh_run_passes_errors_replace(self):
        """_gh_run must pass errors='replace' to handle non-UTF-8 bytes gracefully."""
        src = (DASHBOARD_DIR / "prd_firing.py").read_text(encoding="utf-8")
        self.assertIn(
            'errors="replace"',
            src,
            "_gh_run() in prd_firing.py must pass errors='replace' to subprocess.run",
        )

    def test_null_guard_in_fetch_prd_firing(self):
        """fetch_prd_firing must have a null guard for out2 before calling .strip()."""
        src = (DASHBOARD_DIR / "prd_firing.py").read_text(encoding="utf-8")
        # The fix must guard: out2 is None  (or equivalent)
        self.assertIn(
            "out2 is None",
            src,
            "prd_firing.py must have a null guard 'if out2 is None' before .strip()",
        )

    def test_prd_firing_parses_as_valid_python(self):
        """prd_firing.py must be valid Python after the fix."""
        src = (DASHBOARD_DIR / "prd_firing.py").read_text(encoding="utf-8")
        try:
            ast.parse(src)
        except SyntaxError as e:
            self.fail(f"prd_firing.py has syntax error after fix: {e}")


# ---------------------------------------------------------------------------
# Group 3: ServerEndpoint — route exists and returns 200 (static checks)
# ---------------------------------------------------------------------------

class TestServerEndpointRoute(unittest.TestCase):
    """Static checks: server.py has /api/prd-firing route and catches exceptions."""

    def _server_src(self):
        return SERVER_PY.read_text(encoding="utf-8")

    def test_server_has_prd_firing_route(self):
        """server.py must contain elif path == '/api/prd-firing' route."""
        src = self._server_src()
        self.assertIn(
            '"/api/prd-firing"',
            src,
            "server.py must contain /api/prd-firing route",
        )

    def test_server_catches_prd_firing_exception(self):
        """server.py prd-firing route must have try/except guard."""
        src = self._server_src()
        # The route block must contain try and except to return 500 rather than crash
        # Both keywords appear in the prd-firing handler block
        prd_firing_block_start = src.find('"/api/prd-firing"')
        self.assertGreater(prd_firing_block_start, 0)
        # Find the try keyword after the prd-firing elif
        block_slice = src[prd_firing_block_start:prd_firing_block_start + 500]
        self.assertIn("try:", block_slice,
                      "prd-firing route block must contain try/except guard")

    def test_server_py_parses(self):
        """server.py must remain valid Python."""
        src = self._server_src()
        try:
            ast.parse(src)
        except SyntaxError as e:
            self.fail(f"server.py syntax error: {e}")


if __name__ == "__main__":
    unittest.main()
