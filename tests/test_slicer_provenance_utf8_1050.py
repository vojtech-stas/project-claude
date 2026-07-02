"""
Regression test for #1050: tools/check-slicer-provenance.py cp1252
UnicodeDecodeError/AttributeError when run natively on Windows.

Root cause (per #1050 + ADR-0067 D3 regression rider): the script never
reconfigures sys.stdout/sys.stderr to utf-8, and its subprocess.run() call
capturing `gh issue list ... --json number,body` output does not pass an
explicit encoding= kwarg. On Windows, the default console codepage is
cp1252 (not utf-8), so:
  - decoding non-ASCII bytes emitted by `gh` (issue bodies routinely contain
    em-dashes, curly quotes, emoji) via the platform-default codec raises
    UnicodeDecodeError, and
  - printing that same non-ASCII content back out via a cp1252-default
    sys.stdout raises UnicodeEncodeError,
before any check result is produced. This is the sibling of #834 (fixed in
tools/run_evals.py, PR #1049) — same bug class, same fix shape.

This test:
  1. Statically parses tools/check-slicer-provenance.py and asserts every
     subprocess.run(...) call that captures text passes explicit
     encoding='utf-8' (source-level guard against regressions), and that
     any open() call (if present) does the same.
  2. Asserts the module reconfigures stdout/stderr to utf-8 at startup
     (the actual fix) — this is the part that FAILS before the fix and
     PASSES after.
  3. Behavioral: stubs subprocess.run (the gh-output-parsing seam used by
     tests/test_slicer_provenance.py's _mod import) to return a non-ASCII
     payload (em-dash + emoji) as `gh` would, under a simulated cp1252
     stdout, and drives main()/_fetch_open_slices() through it. Must not
     raise UnicodeDecodeError/UnicodeEncodeError/AttributeError.

Runner: stdlib unittest (no pytest dependency — matches CI's CHECK 12
fallback).  python -m unittest discover -s tests
"""

import ast
import importlib.util as _ilu
import io
import json
import sys
import unittest
from pathlib import Path
from unittest import mock


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _script_path() -> Path:
    return _repo_root() / "tools" / "check-slicer-provenance.py"


def _load_module():
    """Import check-slicer-provenance.py fresh (hyphenated filename, so
    importlib.util is required — mirrors tests/test_slicer_provenance.py's
    existing import seam)."""
    spec = _ilu.spec_from_file_location(
        "check_slicer_provenance_1050", str(_script_path())
    )
    mod = _ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# Non-ASCII fixture content mirroring a real `gh` issue body: em-dash +
# emoji, the class of glyph that crashes under cp1252 (cp1252 lacks a
# codepoint for U+1F600 entirely, and a utf-8-encoded em-dash byte sequence
# is not valid cp1252 text either).
_NON_ASCII_BODY = (
    "## Parent\n\nPRD #919 — emoji test \U0001F600\n\n"
    "Slicer-provenance: slicer-critic-APPROVED decomposition of PRD #919 (round 1)."
)


class TestSourceEncodingDiscipline(unittest.TestCase):
    """Static guard: every subprocess.run(...) call capturing text and
    every open() call in check-slicer-provenance.py must pass an explicit
    encoding= kwarg. Prevents regression to implicit-codepage decodes that
    silently fall back to sys.getdefaultencoding() (cp1252 on native
    Windows)."""

    def _calls(self, func_names):
        src = _script_path().read_text(encoding="utf-8")
        tree = ast.parse(src)
        calls = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = func.id if isinstance(func, ast.Name) else (
                func.attr if isinstance(func, ast.Attribute) else None
            )
            if name in func_names:
                calls.append((node.lineno, name, node))
        return calls

    def test_every_subprocess_run_call_has_explicit_encoding(self):
        """Every subprocess.run(...) call in the script passes encoding=."""
        calls = self._calls({"run"})
        self.assertGreater(
            len(calls), 0, "expected at least one subprocess.run(...) call to check"
        )
        missing = []
        for lineno, name, node in calls:
            has_encoding_kw = any(kw.arg == "encoding" for kw in node.keywords)
            if not has_encoding_kw:
                missing.append(f"line {lineno}: {name}(...) missing encoding= kwarg")
        self.assertEqual(
            missing, [],
            "found subprocess.run(...) call(s) without explicit encoding=:\n"
            + "\n".join(missing),
        )

    def test_every_file_open_call_has_explicit_encoding(self):
        """Every open()/read_text()/write_text() call (if any) passes
        encoding=. This script currently has none, but the guard protects
        against a future regression that adds unguarded file I/O."""
        calls = self._calls({"open", "read_text", "write_text"})
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
    """The actual #1050 fix: stdout/stderr must be utf-8 regardless of the
    OS default console codepage. This is the check that FAILS before the
    fix (module does nothing to stdout/stderr) and PASSES after (module
    reconfigures them at startup)."""

    def test_module_source_reconfigures_stdout_and_stderr_to_utf8(self):
        """Source must call sys.stdout.reconfigure/sys.stderr.reconfigure
        with utf-8 (or equivalent) — not rely on an external
        PYTHONIOENCODING env var (same self-contained requirement as
        #834's fix)."""
        src = _script_path().read_text(encoding="utf-8")
        self.assertIn(
            "reconfigure", src,
            "check-slicer-provenance.py must reconfigure stdout/stderr encoding "
            "at startup (sys.stdout.reconfigure(encoding='utf-8')-style fix) "
            "rather than relying on an external PYTHONIOENCODING env var",
        )
        self.assertIn("stdout", src)
        self.assertIn("stderr", src)

    def test_print_of_non_ascii_survives_simulated_cp1252_stdout(self):
        """Simulate a cp1252-default console: wrap a fresh TextIOWrapper
        around a bytes buffer using cp1252 (mirroring what CPython does
        natively on Windows when no override is present), monkeypatch
        sys.stdout with it, import the script fresh so its startup-time
        reconfiguration runs against the patched stream, then print
        non-ASCII fixture content through it. Must not raise
        UnicodeEncodeError."""
        buffer = io.BytesIO()
        cp1252_stdout = io.TextIOWrapper(buffer, encoding="cp1252", errors="strict")

        old_stdout = sys.stdout
        sys.stdout = cp1252_stdout
        try:
            _load_module()  # re-runs module-level startup reconfiguration

            try:
                print(_NON_ASCII_BODY, file=sys.stdout)
                sys.stdout.flush()
            except UnicodeEncodeError as exc:  # pragma: no cover - failure path
                self.fail(
                    "printing non-ASCII fixture content raised "
                    f"UnicodeEncodeError under simulated cp1252 stdout: {exc}"
                )
        finally:
            sys.stdout = old_stdout

    def test_print_of_non_ascii_survives_simulated_cp1252_stderr(self):
        """Same as above for stderr (used for FAIL/SKIP messages)."""
        buffer = io.BytesIO()
        cp1252_stderr = io.TextIOWrapper(buffer, encoding="cp1252", errors="strict")

        old_stderr = sys.stderr
        sys.stderr = cp1252_stderr
        try:
            _load_module()

            try:
                print(_NON_ASCII_BODY, file=sys.stderr)
                sys.stderr.flush()
            except UnicodeEncodeError as exc:  # pragma: no cover - failure path
                self.fail(
                    "printing non-ASCII fixture content raised "
                    f"UnicodeEncodeError under simulated cp1252 stderr: {exc}"
                )
        finally:
            sys.stderr = old_stderr


class TestGhOutputParsingPathSurvivesNonAscii(unittest.TestCase):
    """Behavioral: drive the script's gh-output-parsing path
    (_fetch_open_slices / main) with a stubbed `gh` subprocess result
    carrying a non-ASCII payload, under simulated cp1252 stdout/stderr.
    Extends the same stub-subprocess seam as tests/test_slicer_provenance.py
    (which imports the module via importlib.util for the hyphenated
    filename) rather than duplicating a new fixture shape."""

    def _run_under_simulated_cp1252(self, fake_result):
        buffer_out = io.BytesIO()
        buffer_err = io.BytesIO()
        cp1252_stdout = io.TextIOWrapper(buffer_out, encoding="cp1252", errors="strict")
        cp1252_stderr = io.TextIOWrapper(buffer_err, encoding="cp1252", errors="strict")

        old_stdout, old_stderr = sys.stdout, sys.stderr
        sys.stdout, sys.stderr = cp1252_stdout, cp1252_stderr
        try:
            mod = _load_module()  # reconfigures the now-patched streams
            with mock.patch.object(mod.subprocess, "run", return_value=fake_result):
                exit_code = mod.main()
            sys.stdout.flush()
            sys.stderr.flush()
            return exit_code
        finally:
            sys.stdout, sys.stderr = old_stdout, old_stderr

    def test_gh_output_with_non_ascii_body_does_not_crash(self):
        """A `gh` result carrying an em-dash/emoji issue body must not raise
        UnicodeDecodeError/UnicodeEncodeError/AttributeError when parsed and
        printed through main()."""
        issues = [{"number": 919, "body": _NON_ASCII_BODY}]
        fake_result = mock.Mock(
            returncode=0,
            stdout=json.dumps(issues),
            stderr="",
        )
        try:
            exit_code = self._run_under_simulated_cp1252(fake_result)
        except (UnicodeDecodeError, UnicodeEncodeError, AttributeError) as exc:
            self.fail(
                "main() crashed on non-ASCII gh output under simulated "
                f"cp1252 streams: {type(exc).__name__}: {exc}"
            )
        self.assertEqual(exit_code, 0)  # body has the trailer -> PASS

    def test_gh_error_message_with_non_ascii_does_not_crash(self):
        """A `gh` error path (non-zero returncode) with a non-ASCII stderr
        message must also survive printing through main()."""
        fake_result = mock.Mock(
            returncode=1,
            stdout="",
            stderr="unexpected failure — \U0001F600",
        )
        try:
            exit_code = self._run_under_simulated_cp1252(fake_result)
        except (UnicodeDecodeError, UnicodeEncodeError, AttributeError) as exc:
            self.fail(
                "main() crashed on non-ASCII gh stderr under simulated "
                f"cp1252 streams: {type(exc).__name__}: {exc}"
            )
        self.assertEqual(exit_code, 0)  # soft-degrade path -> exit 0


if __name__ == "__main__":
    unittest.main()
