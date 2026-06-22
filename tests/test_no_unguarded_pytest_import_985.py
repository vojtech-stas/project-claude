"""
Regression test for slice #985: no test module may hard-import pytest at the top level
without a try/except ImportError guard.

CHECK 12 runs 'python -m unittest discover' in a no-pytest CI environment (ci.yml installs
no pytest). If any test_*.py has an unguarded 'import pytest' or 'from pytest import ...',
unittest's discovery will raise ModuleNotFoundError on that module -> suite ERROR -> CI red.

Rule: every test_*.py that imports pytest MUST guard it:
    try:
        import pytest
    except ImportError:
        pytest = None

This test scans all tests/test_*.py files and fails if any violates the rule.
"""

import os
import re
import unittest

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))

# Pattern: a line starting with "import pytest" or "from pytest import ..." at column 0
_IMPORT_PYTEST_RE = re.compile(r'^(import pytest|from pytest\b)', re.MULTILINE)


def _has_import_error_guard(source: str) -> bool:
    """Return True if the source contains an 'except ImportError' block that plausibly
    guards a pytest import.  We use a simple heuristic: the file contains both
    'import pytest' inside a try-block region and 'except ImportError'.
    """
    return 'except ImportError' in source


def find_unguarded_pytest_imports():
    """Return a list of (filename, line_number, line_text) for unguarded pytest imports."""
    violations = []
    for fname in sorted(os.listdir(TESTS_DIR)):
        if not (fname.startswith('test_') and fname.endswith('.py')):
            continue
        fpath = os.path.join(TESTS_DIR, fname)
        with open(fpath, encoding='utf-8') as fh:
            source = fh.read()

        # If the file has no pytest import at all, skip
        if not _IMPORT_PYTEST_RE.search(source):
            continue

        # If the file has an ImportError guard, consider it guarded
        if _has_import_error_guard(source):
            continue

        # Unguarded: report the specific lines
        for lineno, line in enumerate(source.splitlines(), start=1):
            if re.match(r'^(import pytest|from pytest\b)', line):
                violations.append((fname, lineno, line))

    return violations


class TestNoUnguardedPytestImport(unittest.TestCase):
    def test_no_test_module_hard_imports_pytest(self):
        """No test_*.py may have an unguarded top-level 'import pytest'."""
        violations = find_unguarded_pytest_imports()
        if violations:
            lines = '\n'.join(
                f'  {fname}:{lineno}: {text}'
                for fname, lineno, text in violations
            )
            self.fail(
                f"Found {len(violations)} unguarded pytest import(s) in tests/test_*.py.\n"
                f"Wrap each with try/except ImportError (see #985):\n{lines}"
            )


if __name__ == '__main__':
    unittest.main()
