"""
dashboard/gh_cache.py — shared in-memory TTL cache + timeout wrapper for gh CLI calls.

Provides:
    gh_fetch(args, *, ttl, timeout) -> GhResult

Design (PRD #993 §5, slice #995):
  - Runs `gh` via subprocess.run with a hard per-call timeout (never blocks longer
    than `timeout`).
  - Shared in-memory TTL cache keyed by a normalized command tuple; thread-safe.
  - Fresh cache hit (within ttl): return cached value immediately (source="cache").
  - Cache miss/expiry: run gh with the hard timeout.
    - On success: cache + return (source="live").
    - On subprocess.TimeoutExpired or non-zero exit: return last-cached value
      (source="stale") if any, else the "computing" sentinel (source="computing").
  - If `gh` binary is unavailable (FileNotFoundError, OSError), behave like a timeout.
  - Every returned GhResult carries fetched_at (UTC ISO) + source.
  - NEVER raises into the request path.

Windows note: always pass encoding="utf-8" to subprocess.run (#930 — cp1252 on emoji).
             Guard stdout for None (subprocess quirk).
"""

import subprocess
import threading
import time
from datetime import datetime, timezone
from typing import NamedTuple, Optional, Tuple


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

class GhResult(NamedTuple):
    """Immutable result returned by gh_fetch.

    Attributes
    ----------
    value : str or None
        The stdout string from gh (possibly empty), or None when no data
        is available at all ("computing" sentinel).
    fetched_at : str
        UTC ISO timestamp of when the value was last fetched/computed.
    source : str
        One of "live", "cache", "stale", "computing".
        - "live"      : freshly fetched from gh on this call.
        - "cache"     : returned from the in-memory TTL cache (still fresh).
        - "stale"     : gh timed out / failed; this is the last-known value.
        - "computing" : no previous value and gh is unavailable / timed out.
    """
    value: Optional[str]
    fetched_at: str
    source: str  # "live" | "cache" | "stale" | "computing"


# Sentinel value returned when gh fails and no prior cached value exists.
_COMPUTING_SENTINEL: GhResult = GhResult(
    value=None,
    fetched_at=datetime.now(timezone.utc).isoformat(),
    source="computing",
)


def _make_sentinel() -> GhResult:
    """Return a fresh computing sentinel (timestamp updated per call)."""
    return GhResult(
        value=None,
        fetched_at=datetime.now(timezone.utc).isoformat(),
        source="computing",
    )


# ---------------------------------------------------------------------------
# Cache internals
# ---------------------------------------------------------------------------

# _gh_cache: {cmd_key: {"result": GhResult, "ts": float}}
_gh_cache: dict = {}
_gh_cache_lock = threading.Lock()


def _cmd_key(args: list) -> tuple:
    """Normalize gh args list to a hashable cache key."""
    return tuple(str(a) for a in args)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def gh_fetch(args: list, *, ttl: float, timeout: float) -> GhResult:
    """Fetch data from the gh CLI with TTL caching and a hard per-call timeout.

    Parameters
    ----------
    args : list
        Arguments passed to `gh`, e.g. ["issue", "list", "--label", "prd"].
        The "gh" binary itself is prepended automatically.
    ttl : float
        Cache time-to-live in seconds.  A cached result younger than ttl is
        returned without calling gh.
    timeout : float
        Hard per-call timeout in seconds for the subprocess.run call.  If gh
        blocks longer than this, the call is interrupted and the last-cached
        value (or computing sentinel) is returned.

    Returns
    -------
    GhResult
        Named tuple with .value (str or None), .fetched_at (UTC ISO str),
        .source ("live" | "cache" | "stale" | "computing").

    Notes
    -----
    - Thread-safe; a single global lock serialises cache reads and writes.
      gh subprocess calls happen outside the lock to avoid blocking other
      threads on the timeout duration.
    - Never raises; all exceptions are caught and degraded to stale/computing.
    """
    key = _cmd_key(args)
    now = time.time()

    # --- Check cache first (under lock) ---
    with _gh_cache_lock:
        entry = _gh_cache.get(key)
        if entry is not None:
            age = now - entry["ts"]
            if age < ttl:
                # Fresh cache hit — return as-is with source="cache"
                cached_result = entry["result"]
                return GhResult(
                    value=cached_result.value,
                    fetched_at=cached_result.fetched_at,
                    source="cache",
                )
            # Expired — keep a reference to last-known value for stale fallback
            last_known: Optional[GhResult] = entry["result"]
        else:
            last_known = None

    # --- Cache miss or expired — run gh (outside lock so we don't block others) ---
    fetched_at = datetime.now(timezone.utc).isoformat()
    try:
        result = subprocess.run(
            ["gh"] + list(args),
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=timeout,
        )
        stdout = result.stdout if result.stdout is not None else ""
        if result.returncode == 0:
            # Success — cache and return as live
            gh_result = GhResult(value=stdout, fetched_at=fetched_at, source="live")
            with _gh_cache_lock:
                _gh_cache[key] = {"result": gh_result, "ts": time.time()}
            return gh_result
        else:
            # Non-zero exit — gh ran but returned an error; treat as failure
            raise RuntimeError(
                f"gh exited {result.returncode}: "
                f"{(result.stderr or '')[:200]}"
            )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError, RuntimeError):
        # Degrade: return last-known stale value or computing sentinel
        if last_known is not None:
            return GhResult(
                value=last_known.value,
                fetched_at=last_known.fetched_at,
                source="stale",
            )
        return _make_sentinel()
    except Exception:
        # Unexpected exception — safe fallback
        if last_known is not None:
            return GhResult(
                value=last_known.value,
                fetched_at=last_known.fetched_at,
                source="stale",
            )
        return _make_sentinel()


def clear_cache() -> None:
    """Clear the entire in-memory cache (used in tests)."""
    with _gh_cache_lock:
        _gh_cache.clear()
