"""
dashboard/_gitfiles.py — shared git-aware file enumeration primitive.

Extracted from health.py's ``_tracked_files`` (introduced in issue #926) so
that discovery.py (README generator) can also enumerate via the committed git
tree instead of raw filesystem globs.

Exports:
    tracked_files(root, pathspec) -> list[Path] | None

Import direction: discovery, health -> _gitfiles (this module must NOT import
server, discovery, or health).
"""

import subprocess
from pathlib import Path


def tracked_files(root: Path, pathspec: str) -> "list[Path] | None":
    """Return tracked-file Paths matching *pathspec* under *root*.

    Runs ``git -C <root> ls-files <pathspec>`` and converts each output line
    to an absolute Path.

    Return values:
    - list (possibly empty) — git is available and the repo is valid; the list
      contains exactly the tracked files matching pathspec (empty list = no
      tracked files match, NOT a git failure).
    - None — git is unavailable, the directory is not a git repo, or the
      command failed; callers should fall back to the legacy fs-glob path.

    This is the enumeration primitive introduced in #926 and extended to the
    README generator's discover_* functions in #999.  Only ENUMERATION is gated
    on the committed tree; file *contents* are still read from the working tree
    (which matches the commit in clean CI environments).
    """
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "ls-files", pathspec],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            # git failed (e.g. not a git repo) — signal fallback with None
            return None
        paths = []
        for line in result.stdout.splitlines():
            line = line.strip()
            if line:
                paths.append(root / line)
        return paths
    except Exception:
        # git not installed or subprocess error — signal fallback with None
        return None
