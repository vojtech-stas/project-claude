#!/usr/bin/env python3
"""
dashboard/server.py — project-claude workflow dashboard server.

Serves: GET /               -> dashboard/index.html
        GET /api/architecture -> JSON {skills, agents, hooks, adrs, edges}
        GET /api/pipeline     -> JSON pipeline spec (SPEC v2 from pipeline_spec.py)
        GET /api/health       -> JSON {auditMeta, auditSubagents, cascadeFinder}
        GET /api/file?path=   -> file content (path-traversal safe)
        GET /api/status           -> JSON aggregated liveness snapshot: sha/branch, hooks_live, last_event, main_green, health_summary, open_work (slice #859)
        GET /api/workitems        -> JSON {prd:[...], slices:[...], prs:[...], captures:[...], backlog:[...]} via gh CLI (30s cache); data available via /api/status open_work
        GET /api/live-progress    -> JSON Lane A run-progress for most recent open PRD (25s TTL bg-thread cache)
        GET /api/live-poll?cursor=N -> JSON {cursor, events[], reset} — byte-cursor incremental read (Lane B)
        GET /api/trail?prd=N      -> JSON artifact trail for PRD #N (cache-first, ADR-0053 D1/D4)
        GET /api/comparison?prd=N -> JSON per-run comparison report for PRD #N (ADR-0053 D3)
        GET /api/trail-runs?last=N -> JSON list of last N closed PRDs (for run picker)
        GET /api/rollup?last=N    -> JSON repo rollup over last N closed PRDs (ADR-0053 D3)
        GET /api/meta             -> JSON {sha, started_at, stale} server-identity endpoint (ADR-0056/0057/0058)
        (GET /api/dora removed — slice #854, fleet-economics machinery retired)

Start: python dashboard/server.py
Config: DASH_PORT env var (default 8765)
Requires: Python 3 stdlib only — no pip install needed.
"""

import json
import os
import re
import subprocess
import sys
import threading
import time
import webbrowser
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

# ---------------------------------------------------------------------------
# Repo root — server.py lives at <repo>/dashboard/server.py
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent
DASHBOARD_DIR = REPO_ROOT / "dashboard"

# ---------------------------------------------------------------------------
# sys.path injection keeps imports working both when:
#   (a) server.py is run as __main__ (dashboard/ is cwd or on path)
#   (b) server.py is imported by CHECK 9 (cwd is repo root)
# ---------------------------------------------------------------------------
_DASHBOARD_DIR_STR = str(Path(__file__).resolve().parent)
if _DASHBOARD_DIR_STR not in sys.path:
    sys.path.insert(0, _DASHBOARD_DIR_STR)

from collector import get_trail, get_closed_prd_numbers, rollup  # noqa: E402
from comparison import compare, get_spec_for_compare  # noqa: E402
from pipeline_spec import get_spec as _get_pipeline_spec  # noqa: E402
import live  # noqa: E402
from live import serve_live_poll, _live_progress_background  # noqa: E402

# Sibling module imports (facade re-exports)
from discovery import (  # noqa: E402
    discover_skills, discover_agents, discover_hooks, discover_adrs, discover_edges,
)
import health as _health_mod  # noqa: E402
from health import (  # noqa: E402
    check_docs1_adr_index_forward,
    check_docs2_adr_index_reverse,
    check_docs3_claude_md_agents,
    check_docs4_claude_md_skills,
    check_docs5_n3_literal,
    check_docs6_glossary_md_refs,
    check_docs7_adr_citations,
    check_docs8_supersession_notes,
    check_docs9_glossary_cap,
    check_docs10_backlog_surfacing,
    audit_subagents, audit_meta, cascade_finder_summary,
    serve_health as _serve_health_cached,
)
from events import serve_runs as _serve_runs_fn  # noqa: E402
from workitems import fetch_workitems  # noqa: E402
from readme_gen import generate_readme, render_pipeline_mermaid  # noqa: E402

# ---------------------------------------------------------------------------
# Server identity — captured once at import/startup time (ADR-0056/0057/0058).
# /api/meta returns {sha, started_at, stale}; stale is recomputed per-request
# by comparing the current HEAD to the sha captured at startup.
# ---------------------------------------------------------------------------
def _capture_startup_sha() -> str:
    """Return git HEAD sha at server startup; empty string on failure."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.stdout.strip() if result.returncode == 0 else ""
    except Exception:
        return ""


def _current_head_sha() -> str:
    """Return current git HEAD sha; empty string on failure."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.stdout.strip() if result.returncode == 0 else ""
    except Exception:
        return ""


_SERVER_SHA: str = _capture_startup_sha()
_SERVER_STARTED_AT: str = datetime.now(timezone.utc).isoformat()

# ---------------------------------------------------------------------------
# /api/status — aggregated liveness snapshot (slice #859)
# ---------------------------------------------------------------------------

def _build_status() -> dict:
    """Build the /api/status payload synchronously.

    Returns real aggregated liveness; honest nulls allowed for fields that
    depend on unavailable data (no fixtures, no mock data).

    Fields:
      head_sha, short_sha, branch   — git HEAD at call time
      server_sha, stale             — server startup identity (mirrors /api/meta)
      hooks_live                    — {alive, newest_beacon_ts, age_minutes}
      last_event                    — {ts, age_minutes} from workflow-events.jsonl
      main_green                    — {sha, lag, age_hours} from GREEN-MAIN check
      health_summary                — {pass, warn, fail} counts across all checks
      open_work                     — {prs, slices, captured, backlog} open counts
    """
    import json as _json

    # --- git HEAD ---
    head_sha = ""
    short_sha = ""
    branch = ""
    try:
        r = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=5,
        )
        head_sha = r.stdout.strip() if r.returncode == 0 else ""
        short_sha = head_sha[:7] if head_sha else ""
    except Exception:
        pass
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=5,
        )
        branch = r.stdout.strip() if r.returncode == 0 else ""
    except Exception:
        pass

    # --- server identity (mirrors /api/meta) ---
    current_sha = head_sha
    stale = bool(_SERVER_SHA and current_sha and current_sha != _SERVER_SHA)

    # --- hooks_live: newest beacon in hook-fires.jsonl ---
    fires_log = REPO_ROOT / ".claude" / "logs" / "hook-fires.jsonl"
    hooks_live = {"alive": False, "newest_beacon_ts": None, "age_minutes": None}
    if fires_log.exists():
        beacon_ts: float = 0.0
        newest_ts_str: str = ""
        try:
            with fires_log.open(encoding="utf-8", errors="replace") as fh:
                for raw in fh:
                    raw = raw.strip()
                    if not raw:
                        continue
                    try:
                        obj = _json.loads(raw)
                    except Exception:
                        continue
                    ts_str = obj.get("ts", "")
                    if ts_str:
                        try:
                            candidate = datetime.fromisoformat(
                                ts_str.replace("Z", "+00:00")
                            ).timestamp()
                            if candidate > beacon_ts:
                                beacon_ts = candidate
                                newest_ts_str = ts_str
                        except Exception:
                            pass
        except Exception:
            pass
        if beacon_ts > 0.0:
            age_min = round((time.time() - beacon_ts) / 60.0, 1)
            alive = age_min < 60.0  # mirrors _HOOK_LIVENESS_DARK_MINUTES
            hooks_live = {
                "alive": alive,
                "newest_beacon_ts": newest_ts_str,
                "age_minutes": age_min,
            }

    # --- last_event: newest entry in workflow-events.jsonl ---
    events_log = REPO_ROOT / ".claude" / "logs" / "workflow-events.jsonl"
    last_event = {"ts": None, "age_minutes": None}
    if events_log.exists():
        newest_event_ts: float = 0.0
        newest_event_str: str = ""
        try:
            with events_log.open(encoding="utf-8", errors="replace") as fh:
                for raw in fh:
                    raw = raw.strip()
                    if not raw:
                        continue
                    try:
                        obj = _json.loads(raw)
                    except Exception:
                        continue
                    ts_str = obj.get("ts", "")
                    if ts_str:
                        try:
                            candidate = datetime.fromisoformat(
                                ts_str.replace("Z", "+00:00")
                            ).timestamp()
                            if candidate > newest_event_ts:
                                newest_event_ts = candidate
                                newest_event_str = ts_str
                        except Exception:
                            pass
        except Exception:
            pass
        if newest_event_ts > 0.0:
            age_min = round((time.time() - newest_event_ts) / 60.0, 1)
            last_event = {"ts": newest_event_str, "age_minutes": age_min}

    # --- main_green: reuse GREEN-MAIN check from health.py ---
    from health import check_green_main as _check_green_main
    gm = _check_green_main()
    main_green = {
        "sha": gm.get("sha", None),
        "lag": gm.get("lag", None),
        "age_hours": gm.get("age_hours", None),
    }

    # --- health_summary: count PASS/WARN/FAIL from cached health payload ---
    # Use serve_health() which is TTL-cached; avoids redundant computation.
    health_data, _ = _serve_health_cached()
    pass_count = 0
    warn_count = 0
    fail_count = 0
    for group_key, group_val in health_data.items():
        if not isinstance(group_val, dict):
            continue
        checks_list = group_val.get("checks", [])
        if isinstance(checks_list, list):
            for chk in checks_list:
                result = chk.get("result", "")
                if result == "PASS":
                    pass_count += 1
                elif result == "WARN":
                    warn_count += 1
                elif result == "FAIL":
                    fail_count += 1
        # Also handle nested groups (auditMeta has sub-groups)
        for sub_key, sub_val in group_val.items():
            if sub_key == "checks":
                continue
            if isinstance(sub_val, dict):
                sub_checks = sub_val.get("checks", [])
                if isinstance(sub_checks, list):
                    for chk in sub_checks:
                        result = chk.get("result", "")
                        if result == "PASS":
                            pass_count += 1
                        elif result == "WARN":
                            warn_count += 1
                        elif result == "FAIL":
                            fail_count += 1
    health_summary = {"pass": pass_count, "warn": warn_count, "fail": fail_count}

    # --- open_work: counts from fetch_workitems() (30s cached) ---
    wi = fetch_workitems()
    # Count only OPEN items for prs/slices/captured/backlog
    open_prs = sum(1 for p in wi.get("prs", []) if p.get("state", "").upper() == "OPEN")
    open_slices = sum(
        1 for s in wi.get("slices", []) if s.get("state", "").upper() == "OPEN"
    )
    open_captured = len(wi.get("captures", []))  # already filtered --state open
    open_backlog = len(wi.get("backlog", []))    # already filtered --state open
    open_work = {
        "prs": open_prs,
        "slices": open_slices,
        "captured": open_captured,
        "backlog": open_backlog,
    }

    return {
        "head_sha": head_sha,
        "short_sha": short_sha,
        "branch": branch,
        "server_sha": _SERVER_SHA,
        "stale": stale,
        "hooks_live": hooks_live,
        "last_event": last_event,
        "main_green": main_green,
        "health_summary": health_summary,
        "open_work": open_work,
    }


# ---------------------------------------------------------------------------
# Known critics (explicit allow-list per implementer note 1).
# 7 critics per ADR-0046 D1 (parsimony principle; codebase-critic added ADR-0046 D2).
# CHECK 7 regexes server.py SOURCE for this literal — it must stay here.
# ---------------------------------------------------------------------------
KNOWN_CRITICS = {
    "reviewer",
    "prd-critic",
    "adr-critic",
    "slicer-critic",
    "glossary-critic",
    "backlog-critic",
    "codebase-critic",
}

# ---------------------------------------------------------------------------
# Rollup cache — rollup calls gh CLI per-PR so it can take 20-40s on cold
# start; keyed by last_n with 120s TTL.  Background-thread computation so
# the HTTP handler returns immediately with {"status":"computing"} while the
# work runs; client polls until status transitions to "ready".
# ---------------------------------------------------------------------------
_rollup_cache: dict = {}        # {last_n: {"data": {...}, "ts": float}}
_rollup_computing: dict = {}    # {last_n: True} — in-flight marker
_rollup_lock = threading.Lock()
_ROLLUP_CACHE_TTL = 120    # seconds


def _rollup_background(last_n: int) -> None:
    """Compute rollup in a background thread and store result in _rollup_cache."""
    try:
        spec = get_spec_for_compare()
        result = rollup(last_n=last_n, compare_fn=compare, spec=spec)
        with _rollup_lock:
            _rollup_cache[last_n] = {"data": result, "ts": time.time()}
    except Exception as e:
        # Store error so polling can surface it
        with _rollup_lock:
            _rollup_cache[last_n] = {
                "data": {"status": "error", "error": str(e)},
                "ts": time.time(),
            }
    finally:
        with _rollup_lock:
            _rollup_computing.pop(last_n, None)


# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------

class DashboardHandler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):  # quiet by default; override for debug
        pass

    def _send_json(self, data: dict, status: int = 200):
        body = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _send_text(self, body: bytes, content_type: str = "text/html; charset=utf-8",
                   status: int = 200):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, status: int, message: str):
        self._send_json({"error": message}, status)

    # Reader-side fixture-pattern guard — mirrors the writer's FIXTURE_PATTERN in
    # log-tool-event.sh so the server defensively drops synthetic sids even if the
    # writer's routing was bypassed (e.g. direct file writes during testing).
    _FIXTURE_SID_RE = re.compile(
        r"^(demo|test|verify|fixture|manual|sess-|sample-session-id$)", re.IGNORECASE
    )

    @classmethod
    def _is_valid_v2_event(cls, obj: dict) -> bool:
        """Return True iff obj is a schema-v2 event with a non-empty, non-fixture session_id."""
        if obj.get("v") != 2:
            return False
        sid = obj.get("session_id", "")
        if not sid:
            return False
        if cls._FIXTURE_SID_RE.match(sid):
            return False
        return True

    def _serve_runs(self, query: dict) -> dict:
        """Delegate to events.serve_runs with the canonical log path."""
        log_path = REPO_ROOT / ".claude" / "logs" / "workflow-events.jsonl"
        return _serve_runs_fn(query, log_path)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        if path == "/" or path == "/index.html":
            index = DASHBOARD_DIR / "index.html"
            if index.exists():
                self._send_text(index.read_bytes(), "text/html; charset=utf-8")
            else:
                self._send_error(404, "index.html not found")

        elif path == "/api/architecture":
            data = {
                "skills": discover_skills(),
                "agents": discover_agents(),
                "hooks": discover_hooks(),
                "adrs": discover_adrs(),
                "edges": discover_edges(),
            }
            self._send_json(data)

        elif path == "/api/pipeline":
            # Canonical topology spec (ADR-0053 D2 / ADR-0039 D1 extended).
            # Returns SPEC v2 from pipeline_spec.py; dashboard index.html fetches
            # this for the declared topology render.
            self._send_json(_get_pipeline_spec())

        elif path == "/api/health":
            # TTL-cached; second consecutive call returns <200 ms.
            data, _ = _serve_health_cached()
            self._send_json(data)

        elif path == "/api/status":
            # GET /api/status — aggregated liveness snapshot (slice #859).
            # Returns real-time aggregated state: git identity, hooks liveness,
            # last event age, main_green health, health summary counts, open-work
            # counts. Reuses health.py TTL cache + workitems 30s cache.
            # DEFENSIVE: try/except so a partial failure returns best-effort data.
            try:
                self._send_json(_build_status())
            except Exception as exc:
                self._send_json({"error": str(exc)}, 500)

        elif path == "/api/live-progress":
            # GET /api/live-progress — Lane A run-progress for most recent open PRD.
            # Stale-while-revalidate: if a previous payload exists, ALWAYS return it
            # immediately (with "refreshing":true while a rebuild is in flight).
            # {"status":"computing"} is returned ONLY when no payload has ever been
            # built since process start.  Pattern mirrors /api/rollup.
            with live._live_progress_lock:
                cached = live._live_progress_cache.get("data")
                now = time.time()
                ts = live._live_progress_cache.get("ts", 0)
                expired = (now - ts) >= live._LIVE_PROGRESS_TTL
                if cached is not None and not expired:
                    # Fresh cache — return as-is
                    self._send_json(cached)
                    return
                if cached is not None and expired:
                    # Stale-while-revalidate: serve stale payload immediately,
                    # kick off a background refresh if not already running.
                    payload = dict(cached)
                    payload["refreshing"] = True
                    if not live._live_progress_computing:
                        live._live_progress_computing = True
                        t = threading.Thread(
                            target=_live_progress_background, daemon=True
                        )
                        t.start()
                    self._send_json(payload)
                    return
                # No payload ever built yet — bootstrap case
                if live._live_progress_computing:
                    self._send_json({"status": "computing"})
                    return
                live._live_progress_computing = True
            t = threading.Thread(
                target=_live_progress_background, daemon=True
            )
            t.start()
            self._send_json({"status": "computing"})

        elif path == "/api/live-poll":
            # GET /api/live-poll?cursor=<N>
            # Byte-cursor incremental read of workflow-events.jsonl (Lane B).
            # Returns {cursor, events[], reset}.
            cursor_raw = (query.get("cursor") or ["0"])[0]
            self._send_json(serve_live_poll(cursor_raw))

        elif path == "/api/trail":
            # GET /api/trail?prd=N — raw artifact trail for a PRD (ADR-0053 D1/D4).
            prd_raw = query.get("prd", [""])[0]
            if not prd_raw or not prd_raw.isdigit():
                self._send_error(400, "prd parameter required (integer)")
                return
            try:
                trail = get_trail(int(prd_raw))
                self._send_json(trail)
            except Exception as e:
                self._send_error(500, str(e))

        elif path == "/api/comparison":
            # GET /api/comparison?prd=N[&format=download] — comparison report (ADR-0053 D3).
            # ?format=download serves identical JSON with Content-Disposition attachment.
            prd_raw = query.get("prd", [""])[0]
            if not prd_raw or not prd_raw.isdigit():
                self._send_error(400, "prd parameter required (integer)")
                return
            fmt = query.get("format", [""])[0]
            try:
                trail = get_trail(int(prd_raw))
                spec = get_spec_for_compare()
                report = compare(spec, trail)
                if fmt == "download":
                    import json as _json
                    body = _json.dumps(report, indent=2).encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(body)))
                    self.send_header(
                        "Content-Disposition",
                        f'attachment; filename="prd-{prd_raw}-comparison.json"',
                    )
                    self.end_headers()
                    self.wfile.write(body)
                else:
                    self._send_json(report)
            except Exception as e:
                self._send_error(500, str(e))

        elif path == "/api/trail-runs":
            # GET /api/trail-runs?last=N — list of last N closed PRDs for run picker.
            last_raw = query.get("last", ["20"])[0]
            try:
                last_n = int(last_raw) if last_raw.isdigit() else 20
            except (ValueError, AttributeError):
                last_n = 20
            try:
                numbers = get_closed_prd_numbers(last_n=last_n)
                # Fetch minimal metadata (title + closedAt) for each PRD
                runs = []
                for n in numbers:
                    trail = get_trail(n)
                    runs.append({
                        "number": n,
                        "title": trail.get("prd_title", f"PRD #{n}"),
                        "closed_at": trail.get("prd_closed_at", ""),
                        "wall_time_s": trail.get("wall_time_s"),
                    })
                self._send_json({"runs": runs})
            except Exception as e:
                self._send_error(500, str(e))

        elif path == "/api/rollup":
            # GET /api/rollup?last=N — repo rollup over last N closed PRDs.
            # Returns immediately: {"status":"computing"} while background thread
            # runs; client polls every 2s until status is absent (data ready).
            last_raw = query.get("last", ["10"])[0]
            try:
                last_n = int(last_raw) if last_raw.isdigit() else 10
            except (ValueError, AttributeError):
                last_n = 10
            with _rollup_lock:
                cached = _rollup_cache.get(last_n)
                now = time.time()
                if cached and (now - cached.get("ts", 0)) < _ROLLUP_CACHE_TTL:
                    # Serve cached result; propagate any error status from failed run
                    self._send_json(cached["data"])
                    return
                if _rollup_computing.get(last_n):
                    # Already in flight — return computing sentinel
                    self._send_json({"status": "computing", "last_n": last_n})
                    return
                # Kick off background computation
                _rollup_computing[last_n] = True
            t = threading.Thread(
                target=_rollup_background, args=(last_n,), daemon=True
            )
            t.start()
            self._send_json({"status": "computing", "last_n": last_n})

        elif path == "/api/meta":
            # GET /api/meta — server identity: {sha, started_at, stale}
            # sha: HEAD sha captured at startup; stale: HEAD has moved since startup.
            # stale is recomputed per-request (cheap git rev-parse).
            current_sha = _current_head_sha()
            stale = bool(_SERVER_SHA and current_sha and current_sha != _SERVER_SHA)
            self._send_json({
                "sha": _SERVER_SHA,
                "started_at": _SERVER_STARTED_AT,
                "stale": stale,
            })

        elif path == "/api/file":
            rel_path = query.get("path", [""])[0]
            if not rel_path:
                self._send_error(400, "path parameter required")
                return
            # Fix A: normalize any incoming backslashes (Windows round-trip defence)
            rel_path = rel_path.replace("\\", "/")
            # Path-traversal protection: resolve against repo root
            try:
                target = (REPO_ROOT / rel_path).resolve()
                if not target.is_relative_to(REPO_ROOT):
                    self._send_error(403, "Path traversal rejected")
                    return
                if not target.exists() or not target.is_file():
                    self._send_error(404, "File not found")
                    return
                content = target.read_text(encoding="utf-8", errors="replace")
                self._send_json({"path": rel_path, "content": content})
            except Exception as e:
                self._send_error(400, str(e))

        else:
            self._send_error(404, f"Not found: {path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    port = int(os.environ.get("DASH_PORT", "8765"))
    server = ThreadingHTTPServer(("localhost", port), DashboardHandler)
    server.daemon_threads = True
    print(f"Dashboard running at http://localhost:{port}", flush=True)
    print(f"Repo root: {REPO_ROOT}", flush=True)
    print("Press Ctrl+C to stop.", flush=True)
    if not os.environ.get("DASH_NO_BROWSER"):
        try:
            webbrowser.open(f"http://localhost:{port}")
        except Exception as e:
            print(f"(could not open browser: {e})", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping.", flush=True)
        server.server_close()


if __name__ == "__main__":
    if "--generate-readme" in sys.argv:
        generate_readme()
    else:
        main()
