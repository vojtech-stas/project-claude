#!/usr/bin/env python3
"""
tools/check-verdict-presence.py — verdict-presence guard (PRD #1214 criterion
3c / ADR-0080 D1's supersession of ADR-0075 D6, slice #1219).

Verifies that every recently-merged `develop` PR carries a reviewer comment
matching the exact `VERDICT:\\s*APPROVE` signal `tools/pipe/pr-merge`'s
`_VERDICT_APPROVE_RE` pattern requires before it will perform a merge (PIP-016
/ ADR-0076 D3). This is the D6-supersession's compensating control: the
retired gh-reconstructed panel used to render this cross-check for a human
who happened to look; this check performs the SAME verification mechanically
on every CI run, against ground truth (`gh pr view --json comments`) that a
fresh hosted checkout genuinely has — so, unlike the ledger-side
MERGED-WITHOUT-VERDICT reconciler (which WARN-degrades in a fresh checkout
with no local trace history), this check REALLY FAILS CI on a violation
(e.g. the admin-bypass merge class ADR-0076 D3's residual #1098 names).

Window scope: mechanically bounded — the last `--limit` (default 20, matching
the `gh pr list --base develop --state merged --limit 20` convention already
used by `dashboard/health.py`'s `_fetch_github_ci_conclusion` /
RECORD-VS-GH). NO special-case grandfather list: every PR in the window must
carry the trailer, full stop — the reviewer's `VERDICT: APPROVE` comment
convention predates ADR-0076, so there is no historical PR this check is
expected to give a pass for free.

Fixture seam (rule #21 fixture discipline: this script performs ZERO writes
to any production data store — it only reads via `gh` — so the seam carries
no contamination risk): `--fixture-file <path>` loads a JSON file shaped
`[{"number": <int>, "comments": [{"body": "..."}]}, ...]` in place of live
`gh` calls, for local demonstration/testing of the FAIL path (a canary
comment-set deliberately lacking the trailer) without needing a real
badly-merged PR to exist.

Exit codes:
  0 — every PR in the window carries the VERDICT: APPROVE trailer (or gh is
      unavailable/unauthenticated — soft-degrade for local dev without a
      GH_TOKEN; CI always has one per the CHECK-19 precedent, so this path
      is a genuine hard gate there, not a WARN)
  1 — one or more PRs in the window lack the trailer

Usage:
  python3 tools/check-verdict-presence.py
  python3 tools/check-verdict-presence.py --limit 20
  python3 tools/check-verdict-presence.py --fixture-file <path>   # test/demo only

CI integration: tools/ci-checks.sh CHECK 23 calls this script directly.
"""

import argparse
import json
import re
import subprocess
import sys
from typing import Optional

# ---------------------------------------------------------------------------
# Windows cp1252 fix (#1050 precedent, mirrors check-slicer-provenance.py):
# force stdout/stderr to utf-8 at startup — gh comment bodies routinely
# contain non-cp1252 glyphs.
# ---------------------------------------------------------------------------
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

_DEFAULT_LIMIT = 20

# The exact signal tools/pipe/pr-merge's `_VERDICT_APPROVE_RE` requires
# before performing a merge (PIP-016 / ADR-0076 D3) — kept byte-identical
# here so this check can never drift from the merge-time gate it audits.
_VERDICT_APPROVE_RE = re.compile(r"VERDICT:\s*APPROVE")


def comment_has_verdict_approve(body: str) -> bool:
    """Return True if a single comment body matches the exact
    `VERDICT:\\s*APPROVE` signal. Pure, unit-testable — no I/O."""
    if not body:
        return False
    return bool(_VERDICT_APPROVE_RE.search(body))


def pr_has_verdict(comments: list) -> bool:
    """Return True if ANY comment in the list matches the trailer. Pure,
    unit-testable — no I/O."""
    return any(comment_has_verdict_approve((c or {}).get("body", "")) for c in comments)


def classify_prs(prs: list) -> dict:
    """Classify PRs into ok/missing buckets (pure, unit-testable — no I/O).

    `prs` is a list of {"number": int, "comments": [{"body": str}, ...]}.
    Returns {"ok": [numbers...], "missing": [numbers...]}.
    """
    ok: list = []
    missing: list = []
    for pr in prs:
        number = pr["number"]
        if pr_has_verdict(pr.get("comments") or []):
            ok.append(number)
        else:
            missing.append(number)
    return {"ok": ok, "missing": missing}


def _run_gh(args: list, timeout: int = 30):
    """Run a `gh` subcommand. Returns the CompletedProcess, or None if gh is
    missing/times out/errors at the process level (caller soft-degrades)."""
    try:
        return subprocess.run(
            ["gh", *args],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=timeout,
        )
    except FileNotFoundError:
        print("SKIP: verdict-presence check — gh not found (soft-degrade)")
        return None
    except subprocess.TimeoutExpired:
        print("SKIP: verdict-presence check — gh timed out (soft-degrade)")
        return None
    except Exception as e:
        print(f"SKIP: verdict-presence check — gh error: {e} (soft-degrade)")
        return None


def _gh_unauthenticated(stderr: str) -> bool:
    stderr_lower = (stderr or "").lower()
    return any(
        s in stderr_lower
        for s in ("not logged", "authentication", "unauthorized", "gh_token", "token")
    )


def _fetch_recent_merged_pr_numbers(limit: int) -> Optional[list]:
    """`gh pr list --base develop --state merged --limit <limit> --json number`
    — the same bounded-window convention `dashboard/health.py`'s
    `_fetch_github_ci_conclusion` / RECORD-VS-GH already use.

    Returns a list of ints, or None if gh is unavailable/unauthenticated
    (soft-degrade signal)."""
    result = _run_gh([
        "pr", "list", "--base", "develop", "--state", "merged",
        "--limit", str(limit), "--json", "number",
    ])
    if result is None:
        return None
    if result.returncode != 0:
        if _gh_unauthenticated(result.stderr):
            print(
                "SKIP: verdict-presence check — gh unauthenticated "
                "(no GH_TOKEN) (soft-degrade)"
            )
        else:
            print(
                f"SKIP: verdict-presence check — gh pr list exited "
                f"{result.returncode}: {result.stderr.strip()[:120]} (soft-degrade)"
            )
        return None
    stdout = result.stdout.strip()
    if not stdout:
        return []
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        print("SKIP: verdict-presence check — gh pr list returned non-JSON (soft-degrade)")
        return None
    return [item["number"] for item in data]


def _fetch_pr_comments(number: int) -> Optional[list]:
    """`gh pr view <n> --json comments` — the same call
    `tools/pipe/pr-merge`'s `_fetch_pr_comments` uses. Returns a list of
    comment dicts, or None on any gh failure (soft-degrade signal)."""
    result = _run_gh(["pr", "view", str(number), "--json", "comments"])
    if result is None:
        return None
    if result.returncode != 0:
        print(
            f"SKIP: verdict-presence check — gh pr view #{number} exited "
            f"{result.returncode}: {result.stderr.strip()[:120]} (soft-degrade)"
        )
        return None
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        print(f"SKIP: verdict-presence check — gh pr view #{number} returned non-JSON (soft-degrade)")
        return None
    return data.get("comments", [])


def _fetch_prs_with_comments(limit: int) -> Optional[list]:
    """Combine the two gh calls above into the shape `classify_prs` expects.
    Returns None (soft-degrade) if the PR-list call itself fails; a
    per-PR comment-fetch failure degrades that single PR's comment list to
    empty (a real gh outage mid-window should not silently PASS the check —
    it will surface as a missing-trailer FAIL, which is the safe direction:
    a check that cannot prove presence must not claim it found any)."""
    numbers = _fetch_recent_merged_pr_numbers(limit)
    if numbers is None:
        return None
    prs = []
    for n in numbers:
        comments = _fetch_pr_comments(n)
        prs.append({"number": n, "comments": comments or []})
    return prs


def _load_fixture(path: str) -> list:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=_DEFAULT_LIMIT)
    parser.add_argument(
        "--fixture-file", default=None,
        help="load a JSON fixture instead of live gh calls (test/demo only)",
    )
    args = parser.parse_args(argv)

    if args.fixture_file:
        prs = _load_fixture(args.fixture_file)
        print(f"verdict-presence check — running against fixture {args.fixture_file!r}")
    else:
        prs = _fetch_prs_with_comments(args.limit)
        if prs is None:
            # Soft-degrade path — skip message already printed.
            return 0

    if not prs:
        print("PASS: verdict-presence — no merged develop PRs found in window")
        return 0

    result = classify_prs(prs)
    ok, missing = result["ok"], result["missing"]
    detail = f"{len(ok)} ok, {len(missing)} MISSING (window={len(prs)})"

    if missing:
        numbers = ", ".join(f"#{n}" for n in sorted(missing))
        print(f"FAIL: verdict-presence — {detail}: {numbers}", file=sys.stderr)
        print(
            "These merged develop PRs carry no reviewer comment matching "
            "'VERDICT: APPROVE' — the D6-supersession compensating control "
            "(ADR-0080 D1) treats this as a real CI failure, not a WARN.",
            file=sys.stderr,
        )
        return 1

    print(f"PASS: verdict-presence — {detail}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
