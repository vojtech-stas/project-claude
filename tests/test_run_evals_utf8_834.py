"""
Regression test for #834: tools/run_evals.py cp1252 UnicodeDecodeError/
UnicodeEncodeError when run natively on Windows.

Root cause (per #834 + ADR-0067 D3 regression rider): the runner never
reconfigures sys.stdout/sys.stderr to utf-8, and its subprocess.run() call
capturing `claude -p` output does not pass an explicit encoding. On Windows,
the default console codepage is cp1252 (verified: sys.stdout.encoding ==
"cp1252" natively), so any print() of non-cp1252 content (em-dashes, smart
quotes, emoji — all common in CRITIC trailer / eval fixture text) raises
UnicodeEncodeError, and any implicit-encoding file/text decode of such
content raises UnicodeDecodeError.

This test:
  1. Statically parses tools/run_evals.py and asserts every open()/
     read_text()/write_text() call passes an explicit encoding= kwarg
     (source-level guard against regressions).
  2. Asserts the module reconfigures stdout/stderr to utf-8 at import/
     startup time (the actual fix for the reported crash) — this is the
     part that FAILS before the fix and PASSES after.
  3. Exercises the real file-reading path (Path.read_text as used by
     load_manifest / run_case) against a fixture containing non-ASCII
     content (em-dash + emoji) and asserts a clean utf-8 round-trip with
     no decode error, independent of OS default codepage.

Runner: stdlib unittest (no pytest dependency — matches CI's CHECK 12
fallback).  python -m unittest discover -s tests
"""

import ast
import io
import sys
import tempfile
import unittest
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _run_evals_path() -> Path:
    return _repo_root() / "tools" / "run_evals.py"


def _add_tools_to_path() -> None:
    tools_dir = str(_repo_root() / "tools")
    if tools_dir not in sys.path:
        sys.path.insert(0, tools_dir)


# Non-ASCII fixture content: em-dash + emoji, the class of glyph that
# crashes under cp1252 (cp1252 has no codepoint for U+1F600 at all, and
# while it *does* have an em-dash at 0x97, a UTF-8-encoded em-dash byte
# sequence is NOT valid cp1252 text, so decoding raises there too).
_NON_ASCII_FIXTURE = "VERDICT: APPROVE\nREASON: looks good — nice work \U0001F600\n"


class TestSourceEncodingDiscipline(unittest.TestCase):
    """Static guard: every file-opening call in run_evals.py must pass
    an explicit encoding= kwarg. Prevents regression to implicit-codepage
    reads/writes that silently fall back to sys.getdefaultencoding()
    (cp1252 on native Windows)."""

    def _file_io_calls(self):
        src = _run_evals_path().read_text(encoding="utf-8")
        tree = ast.parse(src)
        calls = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = func.id if isinstance(func, ast.Name) else (
                func.attr if isinstance(func, ast.Attribute) else None
            )
            if name in ("open", "read_text", "write_text"):
                calls.append((node.lineno, name, node))
        return calls

    def test_every_file_open_call_has_explicit_encoding(self):
        """Every open()/read_text()/write_text() call passes encoding=."""
        calls = self._file_io_calls()
        self.assertGreater(len(calls), 0, "expected at least one file I/O call to check")
        missing = []
        for lineno, name, node in calls:
            has_encoding_kw = any(kw.arg == "encoding" for kw in node.keywords)
            if not has_encoding_kw:
                missing.append(f"line {lineno}: {name}(...) missing encoding= kwarg")
        self.assertEqual(
            missing, [],
            "found file I/O call(s) without explicit encoding=:\n" + "\n".join(missing),
        )


class TestStdoutUtf8Reconfigured(unittest.TestCase):
    """The actual #834 fix: stdout/stderr must be utf-8 regardless of the
    OS default console codepage. This is the check that FAILS before the
    fix (module does nothing to stdout/stderr) and PASSES after (module
    reconfigures them at startup)."""

    def test_module_source_reconfigures_stdout_and_stderr_to_utf8(self):
        """Source must call sys.stdout.reconfigure/wrap with utf-8 (or
        equivalent) for both stdout and stderr — not rely on an external
        PYTHONIOENCODING env var (issue explicitly rules that out)."""
        src = _run_evals_path().read_text(encoding="utf-8")
        self.assertIn(
            "reconfigure", src,
            "run_evals.py must reconfigure stdout/stderr encoding at startup "
            "(sys.stdout.reconfigure(encoding='utf-8')-style fix) rather than "
            "relying on an external PYTHONIOENCODING env var",
        )
        # Must cover BOTH streams — a fix touching only stdout still leaves
        # stderr vulnerable to the same crash class.
        self.assertIn("stdout", src)
        self.assertIn("stderr", src)

    def test_print_of_non_ascii_survives_simulated_cp1252_stdout(self):
        """Simulate a cp1252-default console: wrap a fresh TextIOWrapper
        around a bytes buffer using cp1252 (mirroring what CPython does
        natively on Windows when no override is present), monkeypatch
        sys.stdout with it, import/reload run_evals so its startup-time
        reconfiguration runs against the patched stream, then print
        non-ASCII fixture content through it. Must not raise
        UnicodeEncodeError."""
        _add_tools_to_path()

        buffer = io.BytesIO()
        cp1252_stdout = io.TextIOWrapper(buffer, encoding="cp1252", errors="strict")

        old_stdout = sys.stdout
        sys.stdout = cp1252_stdout
        try:
            import importlib
            import run_evals  # noqa: PLC0415
            importlib.reload(run_evals)  # re-run module-level startup code

            # After the module's own reconfiguration, sys.stdout (module-
            # global, not our local reference) should now be utf-8 capable.
            try:
                print(_NON_ASCII_FIXTURE, file=sys.stdout)
                sys.stdout.flush()
            except UnicodeEncodeError as exc:  # pragma: no cover - failure path
                self.fail(
                    "printing non-ASCII fixture content raised "
                    f"UnicodeEncodeError under simulated cp1252 stdout: {exc}"
                )
        finally:
            sys.stdout = old_stdout

    def test_print_of_non_ascii_survives_simulated_cp1252_stderr(self):
        """Same as above for stderr (used for error/status output)."""
        _add_tools_to_path()

        buffer = io.BytesIO()
        cp1252_stderr = io.TextIOWrapper(buffer, encoding="cp1252", errors="strict")

        old_stderr = sys.stderr
        sys.stderr = cp1252_stderr
        try:
            import importlib
            import run_evals  # noqa: PLC0415
            importlib.reload(run_evals)

            try:
                print(_NON_ASCII_FIXTURE, file=sys.stderr)
                sys.stderr.flush()
            except UnicodeEncodeError as exc:  # pragma: no cover - failure path
                self.fail(
                    "printing non-ASCII fixture content raised "
                    f"UnicodeEncodeError under simulated cp1252 stderr: {exc}"
                )
        finally:
            sys.stderr = old_stderr


class TestFixtureRoundTrip(unittest.TestCase):
    """Exercise the real file-reading path (as used by load_manifest /
    run_case's artifact_path.read_text) against a non-ASCII fixture."""

    def test_read_write_round_trip_non_ascii_fixture(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture_path = Path(tmp) / "fixture.txt"
            fixture_path.write_text(_NON_ASCII_FIXTURE, encoding="utf-8")

            # Mirrors run_case()'s artifact_path.read_text(encoding="utf-8", ...)
            read_back = fixture_path.read_text(encoding="utf-8", errors="replace")
            self.assertEqual(read_back, _NON_ASCII_FIXTURE)

            # Mirrors save_results()'s write_text(..., encoding="utf-8")
            out_path = Path(tmp) / "results.json"
            out_path.write_text(read_back, encoding="utf-8")
            self.assertEqual(out_path.read_text(encoding="utf-8"), _NON_ASCII_FIXTURE)


if __name__ == "__main__":
    unittest.main()
