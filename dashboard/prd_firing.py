"""
dashboard/prd_firing.py — per-PR workflow-firing timeline derived from gh CLI.

Provides public functions consumed by server.py's /api/prd-firing route:

  parse_pr_firing_timeline(pr: dict) -> dict
    Given a single PR dict from `gh pr view --json number,title,createdAt,
    mergedAt,body,comments`, extract the ordered agent-firing event sequence:
      implementer (createdAt) -> critic events (parsed from comments
      with CRITIC:/VERDICT:/ROUND: fields) -> merge (mergedAt).

  build_prd_firing_payload(timelines: list[dict]) -> dict
    Wrap a list of parsed timeline dicts into the /api/prd-firing response
    envelope: {prs, pr_count, fetched_at}.

  fetch_prd_firing(limit: int) -> dict   [BLOCKING — backward-compat]
    Fetches recent PRs via gh CLI, parses each one, and caches the result
    for _CACHE_TTL seconds.  Returns honest-empty if gh unavailable.
    NOTE: this is the SLOW blocking path (~40s cold); callers that need
    non-blocking behaviour must use serve_prd_firing() instead.

  serve_prd_firing(limit: int) -> dict   [NON-BLOCKING — HTTP handler]
    Stale-while-revalidate serve path (issue #962 fix).  Always returns
    immediately: cached data if warm, {"status":"computing"} on first cold
    call.  Kicks a daemon background thread to recompute on miss/TTL expiry.
    Mirrors the pattern used by health.py::serve_health().

  _fetch_prd_firing_blocking(limit: int) -> dict   [internal; testable seam]
    The pure blocking gh-call computation. Extracted so tests can mock it
    without patching fetch_prd_firing (which also reads cache). Background
    thread calls this; HTTP handler never calls it directly.

Design constraints (from slice #871, updated #962):
  - Real gh data only — no fixtures, no mock data.
  - Honest empty: if gh unavailable or no PRs, returns {prs:[], pr_count:0}.
  - Cache: gh calls are slow; cache result for _CACHE_TTL seconds.
  - Works with hooks dark: entirely gh-derived, never reads event log.
  - Non-blocking serve: /api/prd-firing must return in <3s always (issue #962).
    Background-warm + stale-while-revalidate; serve {"status":"computing"} on
    true cold start (no prior payload). TTL is generous (300s) to avoid
    constant recompute — correlation of ~20 PRs is expensive.
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
_CACHE_TTL = 300           # seconds — generous TTL; ~20 PRs × gh pr view is
                           # expensive; background-warm keeps it fresh enough.
                           # (Was 60s — increased for issue #962: frequent expiry
                           # caused back-to-back cold blocks on every request.)

# ---------------------------------------------------------------------------
# Background-warm state — mirrors health.py / live.py pattern (issue #962)
# ---------------------------------------------------------------------------
_cache_computing: bool = False   # True while background thread is running

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


# ---------------------------------------------------------------------------
# PRD resolution cache — avoids repeated gh calls for the same issue number
# ---------------------------------------------------------------------------
_prd_resolve_cache: dict[int, int | None] = {}  # {issue_num: prd_num | None}
_prd_resolve_lock = threading.Lock()


def resolve_prd_for_issue(issue_num: int) -> int | None:
    """Resolve an issue number to its parent PRD number, or None if not a slice.

    Two-tier-aware: GitHub's `closingIssuesReferences` is empty for develop-base
    PRs, so the trail's closes_issues list may contain slice numbers or arbitrary
    issue numbers (captured, backlog, etc.).  This function:
      1. Checks if issue_num has the 'slice' label (fast gh issue view call).
      2. If yes, fetches its parent PRD via GraphQL subIssue parent link.
      3. Returns the parent PRD issue number (int), or None if no parent or
         the issue is not a slice.

    Results are cached in-process (_prd_resolve_cache) to minimise gh round-trips.
    Returns None on any gh error (treated as unresolvable — caller renders
    the PR as non-PRD / maintenance).
    """
    with _prd_resolve_lock:
        if issue_num in _prd_resolve_cache:
            return _prd_resolve_cache[issue_num]

    result: int | None = None
    try:
        rc, stdout = _gh_run([
            "issue", "view", str(issue_num),
            "--json", "labels,number",
        ])
        if rc != 0 or not stdout.strip():
            with _prd_resolve_lock:
                _prd_resolve_cache[issue_num] = None
            return None

        data = json.loads(stdout)
        labels = [lbl.get("name", "") for lbl in (data.get("labels") or [])]

        if "slice" not in labels:
            # Not a slice (could be captured/backlog/prd directly) — no parent PRD
            with _prd_resolve_lock:
                _prd_resolve_cache[issue_num] = None
            return None

        # It's a slice — find its parent PRD via gh issue view parent field
        # GitHub returns a `parent` object when the issue is a sub-issue.
        rc2, out2 = _gh_run([
            "issue", "view", str(issue_num),
            "--json", "parent",
        ])
        if rc2 == 0 and out2.strip():
            d2 = json.loads(out2)
            parent = d2.get("parent") or {}
            parent_num = parent.get("number") if isinstance(parent, dict) else None
            if parent_num:
                result = int(parent_num)

    except Exception:
        result = None

    with _prd_resolve_lock:
        _prd_resolve_cache[issue_num] = result
    return result


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
      prd_number    : int | None  — parent PRD if closes_issues contains a slice;
                                    None for non-PRD closes (captured/backlog/etc.)
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

    # Resolve parent PRD: try each closed issue; use first one that maps to a PRD.
    prd_number: int | None = None
    for closed_num in closes_issues:
        parent = resolve_prd_for_issue(closed_num)
        if parent is not None:
            prd_number = parent
            break

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
        "prd_number":    prd_number,
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


# ---------------------------------------------------------------------------
# Blocking computation — testable seam; called ONLY by background thread
# ---------------------------------------------------------------------------

def _fetch_prd_firing_blocking(limit: int = 30) -> dict:
    """Pure blocking computation: fetch PRs from gh CLI and build payload.

    This is the slow path (~40s cold on 20 PRs).  It must NEVER be called
    directly from the HTTP request handler — use serve_prd_firing() instead.
    Exposed as a named function so tests can mock it in isolation.

    Does NOT touch _cache; the caller (background thread) is responsible for
    storing the result.
    """
    timelines: list[dict] = []

    # Step 1: list recent PRs
    rc, stdout = _gh_run([
        "pr", "list",
        "--state", "all",
        "--limit", str(limit),
        "--json", "number,title,createdAt,mergedAt",
    ])
    if rc != 0 or not stdout.strip():
        return build_prd_firing_payload([])

    try:
        prs_list = json.loads(stdout)
    except (json.JSONDecodeError, ValueError):
        return build_prd_firing_payload([])

    if not isinstance(prs_list, list):
        return build_prd_firing_payload([])

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

    return build_prd_firing_payload(timelines)


# ---------------------------------------------------------------------------
# Background thread target
# ---------------------------------------------------------------------------

def _prd_firing_background(limit: int) -> None:
    """Compute prd-firing payload in a background thread and cache the result.

    Called by serve_prd_firing() on cache miss or TTL expiry.
    Sets _cache_computing=False in the finally block.
    """
    global _cache_computing
    try:
        result = _fetch_prd_firing_blocking(limit)
        with _cache_lock:
            _cache[limit] = {"data": result, "ts": time.time()}
    except Exception as exc:
        # On failure: store an honest-empty so the next serve returns something
        empty = build_prd_firing_payload([])
        empty["error"] = str(exc)
        with _cache_lock:
            _cache[limit] = {"data": empty, "ts": time.time()}
    finally:
        with _cache_lock:
            _cache_computing = False


# ---------------------------------------------------------------------------
# Non-blocking serve — HTTP handler entry point (issue #962 fix)
# ---------------------------------------------------------------------------

def serve_prd_firing(limit: int = 30) -> dict:
    """Stale-while-revalidate serve path for /api/prd-firing.

    ALWAYS returns immediately (target: <3s, typically <10ms):
      - Warm cache (not expired): return cached data.
      - Stale cache (TTL expired): return cached data with "refreshing":true
        and kick a background recompute thread (if not already running).
      - Cold (no prior payload): return {"status":"computing"} and kick
        background thread.

    Mirrors health.py::serve_health() / live.py::_live_progress_background
    pattern (issue #962).
    """
    global _cache_computing
    with _cache_lock:
        cached_entry = _cache.get(limit)
        now = time.time()

        if cached_entry is not None:
            cached_data = cached_entry.get("data")
            ts = cached_entry.get("ts", 0)
            expired = (now - ts) >= _CACHE_TTL

            if not expired:
                # Cache is fresh — serve immediately, no background kick needed
                return cached_data

            # Cache is stale — serve last-known data with refreshing marker,
            # kick background refresh if not already running.
            payload = dict(cached_data)
            payload["refreshing"] = True
            if not _cache_computing:
                _cache_computing = True
                t = threading.Thread(
                    target=_prd_firing_background, args=(limit,), daemon=True
                )
                t.start()
            return payload

        # No payload yet (cold start) — kick background if not already running
        if _cache_computing:
            return {"status": "computing"}
        _cache_computing = True

    # Start background thread outside the lock
    t = threading.Thread(target=_prd_firing_background, args=(limit,), daemon=True)
    t.start()
    return {"status": "computing"}


# ---------------------------------------------------------------------------
# Backward-compat blocking function (preserves old callers)
# ---------------------------------------------------------------------------

def fetch_prd_firing(limit: int = 30) -> dict:
    """Fetch recent PRs via gh CLI and build the /api/prd-firing payload.

    BLOCKING: may take 40s+ on cold start with ~20 PRs.

    Backward-compatible wrapper: checks cache first, then calls
    _fetch_prd_firing_blocking() and stores the result.
    HTTP handlers must use serve_prd_firing() instead (issue #962 fix).

    Returns honest-empty {prs:[], pr_count:0, fetched_at:...} if gh is
    unavailable or returns no PRs.
    """
    with _cache_lock:
        cached = _cache.get(limit)
        if cached and (time.time() - cached.get("ts", 0)) < _CACHE_TTL:
            return cached["data"]

    payload = _fetch_prd_firing_blocking(limit)
    with _cache_lock:
        _cache[limit] = {"data": payload, "ts": time.time()}
    return payload
