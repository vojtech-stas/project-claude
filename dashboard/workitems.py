"""
dashboard/workitems.py — work-items fetcher (PRD→slice→PR tree via gh CLI).

Exports:
    fetch_workitems() -> dict

Import direction: server <- workitems (this module must NOT import server).

Slice #995: routes gh CLI calls through gh_cache.gh_fetch so a slow gh
degrades gracefully (stale-or-computing) rather than blocking the request
path. The returned dict now includes optional _fetched_at/_source metadata
keys at the top level (not inside the per-item lists) for /api/status to
surface as open_work.fetched_at / open_work.source.
"""

import json
import time
from pathlib import Path

from gh_cache import gh_fetch, GhResult

# ---------------------------------------------------------------------------
# Repo root — workitems.py lives at <repo>/dashboard/workitems.py
# ---------------------------------------------------------------------------
_WORKITEMS_REPO_ROOT = Path(__file__).resolve().parent.parent

# In-process cache: {"data": {...}, "ts": float}
# NOTE: gh_cache provides its own per-command TTL cache; this outer cache
# avoids redundant gh_fetch calls when fetch_workitems() is called multiple
# times within the same request burst (e.g. repeated /api/status calls).
_workitems_cache: dict = {}
_WORKITEMS_TTL = 30  # seconds — outer TTL (gh_cache inner TTL is 15s for status)

# Per-command TTL and timeout used when routing through gh_cache (slice #995).
_GH_WORKITEMS_TTL = 15      # seconds — inner gh_cache TTL for work-item queries
_GH_WORKITEMS_TIMEOUT = 5   # seconds — hard per-call gh timeout


def _gh_list_via_cache(args: list) -> tuple[list, GhResult]:
    """Fetch a gh CLI command via gh_cache and return (parsed_list, GhResult).

    On any error (timeout, missing binary, bad JSON, stale/computing sentinel)
    returns ([], result) where result.source is "stale" or "computing".
    Never raises.
    """
    result: GhResult = gh_fetch(
        args,
        ttl=_GH_WORKITEMS_TTL,
        timeout=_GH_WORKITEMS_TIMEOUT,
    )
    if result.source == "computing" or result.value is None:
        return [], result
    try:
        parsed = json.loads(result.value)
        if isinstance(parsed, list):
            return parsed, result
        return [], result
    except (json.JSONDecodeError, ValueError):
        return [], result


def fetch_workitems() -> dict:
    """Return PRD→slice→PR tree + deferred captures, 30s outer cache.

    Response shape:
      { prd: [...], slices: [...], prs: [...], captures: [...], backlog: [...],
        _fetched_at: str, _source: str }

    _fetched_at / _source describe the freshness of the gh data underlying the
    open-work counts; they are propagated into /api/status open_work by
    server.py._build_status().  Consumers that only need item lists can ignore
    the _ keys.

    Each item includes createdAt so the client can flag stale slices (>7 days).
    captures = gh issue list --label captured --state open --limit 20
    backlog  = gh issue list --label backlog  --state open --limit 20

    On any failure, returns {} (never raises, never hangs the dashboard).
    """
    now = time.time()
    cached = _workitems_cache.get("data")
    if cached is not None and (now - _workitems_cache.get("ts", 0)) < _WORKITEMS_TTL:
        return cached

    try:
        prds, r_prds = _gh_list_via_cache([
            "issue", "list",
            "--label", "prd",
            "--state", "all",
            "--limit", "30",
            "--json", "number,title,state,labels,createdAt",
        ])
        slices, _ = _gh_list_via_cache([
            "issue", "list",
            "--label", "slice",
            "--state", "all",
            "--limit", "60",
            "--json", "number,title,state,labels,createdAt",
        ])
        prs, _ = _gh_list_via_cache([
            "pr", "list",
            "--state", "all",
            "--limit", "30",
            "--json", "number,title,state,labels,createdAt",
        ])
        # Deferred captures: raw captured tier + curated backlog tier.
        captures, _ = _gh_list_via_cache([
            "issue", "list",
            "--label", "captured",
            "--state", "open",
            "--limit", "20",
            "--json", "number,title,labels,createdAt",
        ])
        backlog, _ = _gh_list_via_cache([
            "issue", "list",
            "--label", "backlog",
            "--state", "open",
            "--limit", "20",
            "--json", "number,title,labels,createdAt",
        ])

        # Use the first gh result's metadata as the representative freshness.
        # All calls share the same cache TTL so their freshness is equivalent.
        data = {
            "prd": prds,
            "slices": slices,
            "prs": prs,
            "captures": captures,
            "backlog": backlog,
            "_fetched_at": r_prds.fetched_at,
            "_source": r_prds.source,
        }

        _workitems_cache["data"] = data
        _workitems_cache["ts"] = now
        return data
    except Exception:
        return {}
