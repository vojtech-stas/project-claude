"""
dashboard/workitems.py — work-items fetcher (PRD→slice→PR tree via gh CLI).

Exports:
    fetch_workitems() -> dict

Import direction: server <- workitems (this module must NOT import server).
"""

import json
import subprocess
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Repo root — workitems.py lives at <repo>/dashboard/workitems.py
# ---------------------------------------------------------------------------
_WORKITEMS_REPO_ROOT = Path(__file__).resolve().parent.parent

# In-process cache: {"data": {...}, "ts": float}
_workitems_cache: dict = {}
_WORKITEMS_TTL = 30  # seconds


def _gh_list(args: list, timeout: int = 10) -> list:
    """Run a gh CLI command and return parsed JSON list.

    On any error (timeout, missing binary, non-zero exit, bad JSON) returns [].
    Never raises.
    """
    try:
        result = subprocess.run(
            ["gh"] + args,
            capture_output=True,
            text=True,
            encoding='utf-8',
            timeout=timeout,
            cwd=str(_WORKITEMS_REPO_ROOT),
            stdin=subprocess.DEVNULL,
        )
        if result.returncode != 0:
            return []
        return json.loads(result.stdout)
    except subprocess.TimeoutExpired:
        return []
    except FileNotFoundError:
        return []
    except Exception:
        return []


def fetch_workitems() -> dict:
    """Return PRD→slice→PR tree + deferred captures, 30s in-process cache.

    Response shape:
      { prd: [...], slices: [...], prs: [...], captures: [...], backlog: [...] }

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
        prds = _gh_list([
            "issue", "list",
            "--label", "prd",
            "--state", "all",
            "--limit", "30",
            "--json", "number,title,state,labels,createdAt",
        ])
        slices = _gh_list([
            "issue", "list",
            "--label", "slice",
            "--state", "all",
            "--limit", "60",
            "--json", "number,title,state,labels,createdAt",
        ])
        prs = _gh_list([
            "pr", "list",
            "--state", "all",
            "--limit", "30",
            "--json", "number,title,state,labels,createdAt",
        ])
        # Deferred captures: raw captured tier + curated backlog tier.
        captures = _gh_list([
            "issue", "list",
            "--label", "captured",
            "--state", "open",
            "--limit", "20",
            "--json", "number,title,labels,createdAt",
        ])
        backlog = _gh_list([
            "issue", "list",
            "--label", "backlog",
            "--state", "open",
            "--limit", "20",
            "--json", "number,title,labels,createdAt",
        ])

        data = {
            "prd": prds,
            "slices": slices,
            "prs": prs,
            "captures": captures,
            "backlog": backlog,
        }

        _workitems_cache["data"] = data
        _workitems_cache["ts"] = now
        return data
    except Exception:
        return {}
