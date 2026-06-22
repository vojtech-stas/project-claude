"""
dashboard/prd_firing.py — per-PR workflow-firing timeline derived from gh CLI.

Provides two public functions consumed by server.py's /api/prd-firing route:

  parse_pr_firing_timeline(pr: dict) -> dict
    Given a single PR dict from `gh pr view --json number,title,createdAt,
    mergedAt,body,comments`, extract the ordered agent-firing event sequence:
      implementer (createdAt) -> critic events (parsed from comments
      with CRITIC:/VERDICT:/ROUND: fields) -> merge (mergedAt).

  build_prd_firing_payload(timelines: list[dict]) -> dict
    Wrap a list of parsed timeline dicts into the /api/prd-firing response
    envelope: {prs, pr_count, fetched_at}.

  fetch_prd_firing(limit: int) -> dict
    Fetches recent PRs via gh CLI, parses each one, and caches the result
    for _CACHE_TTL seconds.  Returns honest-empty if gh unavailable.

Design constraints (from slice #871):
  - Real gh data only — no fixtures, no mock data.
  - Honest empty: if gh unavailable or no PRs, returns {prs:[], pr_count:0}.
  - Cache: gh calls are slow; cache result for _CACHE_TTL seconds.
  - Works with hooks dark: entirely gh-derived, never reads event log.
"""

import json
import re
import subprocess
import threading
import time
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# gh_cache — shared TTL+timeout wrapper for gh CLI calls (slice #996/PRD #993).
# Routed through _gh_run so prd_firing's existing callers are unchanged.
# ---------------------------------------------------------------------------
try:
    from gh_cache import gh_fetch as _gh_fetch_impl
    _GH_CACHE_AVAILABLE = True
except ImportError:
    _gh_fetch_impl = None  # type: ignore[assignment]
    _GH_CACHE_AVAILABLE = False

# ---------------------------------------------------------------------------
# Internal cache — one shared result keyed by (limit,)
# ---------------------------------------------------------------------------
_cache: dict = {}          # {limit: {"data": dict, "ts": float}}
_cache_lock = threading.Lock()
_CACHE_TTL = 60            # seconds — gh is slow; cache for 1 minute

# ---------------------------------------------------------------------------
# CRITIC/VERDICT/ROUND extraction patterns
# These match lines like:
#   VERDICT: APPROVE
#   CRITIC: reviewer
#   ROUND: 3
# Handles both fenced-code-block and bare trailer formats.
# ---------------------------------------------------------------------------
_VERDICT_RE = re.compile(r"^\s*VERDICT\s*:\s*(APPROVE|BLOCK)\s*$", re.IGNORECASE | re.MULTILINE)
_CRITIC_RE  = re.compile(r"^\s*CRITIC\s*:\s*(\S+)\s*$", re.IGNORECASE | re.MULTILINE)
_ROUND_RE   = re.compile(r"^\s*ROUND\s*:\s*(\d+)\s*$", re.IGNORECASE | re.MULTILINE)

# Closes #N pattern — from PR body
_CLOSES_RE  = re.compile(r"(?:Closes|closes|Fixes|fixes|Resolves|resolves)\s+#(\d+)", re.IGNORECASE)


def _parse_closes(body: str) -> list[int]:
    """Extract issue numbers from 'Closes #N' patterns in a PR body."""
    if not body:
        return []
    return [int(m) for m in _CLOSES_RE.findall(body)]


def _parse_comment_critic_event(comment: dict) -> dict | None:
    """Parse a single PR comment for CRITIC trailer fields.

    Returns a critic-event dict {agent, ts, verdict, round} if the comment
    contains a VERDICT field, otherwise None.
    """
    body = comment.get("body") or ""
    ts   = comment.get("createdAt") or ""

    verdict_m = _VERDICT_RE.search(body)
    if not verdict_m:
        return None  # not a critic comment

    verdict = verdict_m.group(1).upper()

    critic_m = _CRITIC_RE.search(body)
    critic   = critic_m.group(1).lower() if critic_m else "reviewer"

    round_m  = _ROUND_RE.search(body)
    round_n  = int(round_m.group(1)) if round_m else None

    return {
        "agent":   critic,
        "ts":      ts,
        "verdict": verdict,
        "round":   round_n,
    }


def parse_pr_firing_timeline(pr: dict) -> dict:
    """Derive the agent-firing event timeline for a single PR.

    Parameters
    ----------
    pr : dict
        PR object with keys: number, title, createdAt, mergedAt, body, comments.
        Matches the shape returned by `gh pr view --json number,title,
        createdAt,mergedAt,body,comments`.

    Returns
    -------
    dict with keys:
      pr_number     : int
      pr_title      : str
      closes_issues : list[int]   — from 'Closes #N' in body
      events        : list[dict]  — ordered by ts; each has {agent, ts} plus
                                    optional {verdict, round} for critic events.
    """
    pr_number = pr.get("number", 0)
    pr_title  = pr.get("title") or ""
    created   = pr.get("createdAt") or ""
    merged    = pr.get("mergedAt") or None
    body      = pr.get("body") or ""
    comments  = pr.get("comments") or []

    closes_issues = _parse_closes(body)
    events: list[dict] = []

    # Implementer event = PR opened (implementer fired when PR was created)
    if created:
        events.append({
            "agent": "implementer",
            "ts":    created,
        })

    # Parse each comment for critic events
    for comment in comments:
        ev = _parse_comment_critic_event(comment)
        if ev is not None:
            events.append(ev)

    # Merge event = PR merged
    if merged:
        events.append({
            "agent": "merge",
            "ts":    merged,
        })

    # Sort chronologically by ts (ISO strings sort lexicographically)
    events.sort(key=lambda e: e.get("ts") or "")

    return {
        "pr_number":     pr_number,
        "pr_title":      pr_title,
        "closes_issues": closes_issues,
        "events":        events,
    }


def build_prd_firing_payload(timelines: list[dict]) -> dict:
    """Wrap a list of parsed PR timelines into the /api/prd-firing response.

    Parameters
    ----------
    timelines : list[dict]
        List of dicts from parse_pr_firing_timeline().

    Returns
    -------
    dict with keys:
      prs        : list[dict]    — the timeline dicts, newest-PR-first
      pr_count   : int
      fetched_at : str           — ISO timestamp of when this payload was built
    """
    fetched_at = datetime.now(timezone.utc).isoformat()
    return {
        "prs":        timelines,
        "pr_count":   len(timelines),
        "fetched_at": fetched_at,
    }


def _gh_run(args: list[str], timeout: int = 30) -> tuple[int, str]:
    """Run a gh CLI command; return (returncode, stdout).

    Routed through gh_cache (ttl=_CACHE_TTL, hard timeout=5s) when available so
    a slow gh degrades rather than stalls (PRD #993 cr.5, slice #996).  The
    existing _CACHE_TTL=60s is the TTL; the 5s hard timeout ensures no single
    call blocks more than 5s on the request path.

    encoding="utf-8" with errors="replace" prevents the Windows cp1252
    UnicodeDecodeError: on Windows, text=True without an explicit encoding
    uses the system default codec (cp1252), which cannot decode bytes outside
    Latin-1 (e.g. emoji, Unicode arrows in PR bodies — byte 0x90).  When
    that decode fails inside subprocess's background _readerthread, r.stdout
    is set to None instead of a string, causing 'NoneType.strip()' errors
    downstream (root cause captured in issue #934).
    """
    if _GH_CACHE_AVAILABLE and _gh_fetch_impl is not None:
        result = _gh_fetch_impl(args, ttl=float(_CACHE_TTL), timeout=5.0)
        if result.source == "computing" or result.value is None:
            return 1, ""
        return 0, result.value
    # Fallback: bounded subprocess (still prevents infinite stall)
    try:
        r = subprocess.run(
            ["gh"] + args,
            capture_output=True, text=True, timeout=min(timeout, 5),
            encoding="utf-8", errors="replace",
        )
        return r.returncode, r.stdout or ""
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return 1, ""  # gh unavailable


def fetch_prd_firing(limit: int = 30) -> dict:
    """Fetch recent PRs via gh CLI and build the /api/prd-firing payload.

    Uses a TTL cache (_CACHE_TTL seconds) because gh CLI calls are slow.
    Returns honest-empty {prs:[], pr_count:0, fetched_at:...} if gh is
    unavailable or returns no PRs.

    Procedure:
      1. gh pr list --state all --limit N --json number,title,createdAt,mergedAt
      2. For each PR: gh pr view N --json number,title,createdAt,mergedAt,body,comments
      3. parse_pr_firing_timeline() -> build_prd_firing_payload()
    """
    with _cache_lock:
        cached = _cache.get(limit)
        if cached and (time.time() - cached.get("ts", 0)) < _CACHE_TTL:
            return cached["data"]

    timelines: list[dict] = []

    # Step 1: list recent PRs
    rc, stdout = _gh_run([
        "pr", "list",
        "--state", "all",
        "--limit", str(limit),
        "--json", "number,title,createdAt,mergedAt",
    ])
    if rc != 0 or not stdout.strip():
        payload = build_prd_firing_payload([])
        with _cache_lock:
            _cache[limit] = {"data": payload, "ts": time.time()}
        return payload

    try:
        prs_list = json.loads(stdout)
    except (json.JSONDecodeError, ValueError):
        payload = build_prd_firing_payload([])
        with _cache_lock:
            _cache[limit] = {"data": payload, "ts": time.time()}
        return payload

    if not isinstance(prs_list, list):
        payload = build_prd_firing_payload([])
        with _cache_lock:
            _cache[limit] = {"data": payload, "ts": time.time()}
        return payload

    # Step 2: fetch full detail for each PR (comments + body for timeline parsing)
    for pr_stub in prs_list:
        pr_num = pr_stub.get("number")
        if not pr_num:
            continue
        rc2, out2 = _gh_run([
            "pr", "view", str(pr_num),
            "--json", "number,title,createdAt,mergedAt,body,comments",
        ], timeout=20)
        if rc2 != 0 or out2 is None or not out2.strip():
            # Fall back to stub data (no comments).
            # out2 is None guard: belt-and-suspenders for any future path where
            # _gh_run returns (0, None) — e.g. subprocess stdout decode failure
            # that propagates as None despite the encoding fix (issue #934).
            timeline = parse_pr_firing_timeline(pr_stub)
        else:
            try:
                pr_detail = json.loads(out2)
            except (json.JSONDecodeError, ValueError):
                pr_detail = pr_stub
            timeline = parse_pr_firing_timeline(pr_detail)

        timelines.append(timeline)

    payload = build_prd_firing_payload(timelines)
    with _cache_lock:
        _cache[limit] = {"data": payload, "ts": time.time()}
    return payload
