#!/usr/bin/env python3
"""
dashboard/server.py — project-claude workflow dashboard server.

Serves: GET /               -> dashboard/index.html
        GET /api/architecture -> JSON {skills, agents, hooks, adrs, edges}
        GET /api/health       -> JSON {auditMeta, auditSubagents, cascadeFinder}
        GET /api/file?path=   -> file content (path-traversal safe)
        GET /api/events       -> SSE stream of workflow-events.jsonl (slice 2)

Start: python dashboard/server.py
Config: DASH_PORT env var (default 8765)
Requires: Python 3 stdlib only — no pip install needed.
"""

import json
import os
import re
import subprocess
import sys
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

# ---------------------------------------------------------------------------
# Repo root — server.py lives at <repo>/dashboard/server.py
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent
DASHBOARD_DIR = REPO_ROOT / "dashboard"

# Known critics (explicit allow-list per implementer note 1)
KNOWN_CRITICS = {
    "reviewer",
    "prd-critic",
    "adr-critic",
    "slicer-critic",
    "glossary-critic",
    "backlog-critic",
}


# ---------------------------------------------------------------------------
# Discovery helpers
# ---------------------------------------------------------------------------

def _parse_frontmatter(path: Path) -> dict:
    """Extract YAML frontmatter fields from a markdown file (name, description, role)."""
    fields = {}
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        if not text.startswith("---"):
            return fields
        end = text.find("\n---", 3)
        if end == -1:
            return fields
        fm_block = text[3:end]
        for line in fm_block.splitlines():
            m = re.match(r'^(\w+):\s*(.+)$', line.strip())
            if m:
                fields[m.group(1)] = m.group(2).strip().strip('"').strip("'")
    except Exception:
        pass
    return fields


KNOWN_GENERATORS = {
    "slicer",
    "implementer",
    "qa-tester",
    "current-state-reader",
}


def _classify_agent(stem: str, description: str) -> str:
    """Classify an agent as 'critic' or 'generator'.

    Priority: explicit allow-lists first (both directions), then description heuristic.
    slicer is a generator even though its description mentions 'slicer-critic'.
    """
    if stem in KNOWN_GENERATORS:
        return "generator"
    if stem in KNOWN_CRITICS:
        return "critic"
    # Description heuristic: look for standalone 'critic' word, not substring of another token
    if re.search(r'\bcritic\b', description.lower()):
        return "critic"
    return "generator"


def discover_skills() -> list:
    skills_dir = REPO_ROOT / ".claude" / "skills"
    skills = []
    if not skills_dir.exists():
        return skills
    for skill_md in sorted(skills_dir.glob("*/SKILL.md")):
        fm = _parse_frontmatter(skill_md)
        skills.append({
            "name": fm.get("name", skill_md.parent.name),
            "description": fm.get("description", ""),
            "path": str(skill_md.relative_to(REPO_ROOT)),
        })
    return skills


def discover_agents() -> list:
    agents_dir = REPO_ROOT / ".claude" / "agents"
    agents = []
    if not agents_dir.exists():
        return agents
    for agent_md in sorted(agents_dir.glob("*.md")):
        fm = _parse_frontmatter(agent_md)
        stem = agent_md.stem
        description = fm.get("description", "")
        kind = _classify_agent(stem, description)
        agents.append({
            "name": fm.get("name", stem),
            "stem": stem,
            "type": kind,
            "description": description,
            "path": str(agent_md.relative_to(REPO_ROOT)),
        })
    return agents


def discover_hooks() -> list:
    settings_path = REPO_ROOT / ".claude" / "settings.json"
    hooks = []
    if not settings_path.exists():
        return hooks
    try:
        data = json.loads(settings_path.read_text(encoding="utf-8"))
        for event, entries in data.get("hooks", {}).items():
            for entry in entries:
                for hook in entry.get("hooks", []):
                    cmd = hook.get("command", "")
                    # Extract script name if it references a .sh file
                    m = re.search(r'hooks/([a-z0-9_-]+\.sh)', cmd)
                    name = m.group(1) if m else cmd[:60]
                    hooks.append({
                        "name": name,
                        "event": event,
                        "command": cmd[:120],
                        "path": ".claude/settings.json",
                    })
    except Exception:
        pass
    return hooks


def discover_adrs() -> list:
    decisions_dir = REPO_ROOT / "decisions"
    adrs = []
    if not decisions_dir.exists():
        return adrs
    for adr_file in sorted(decisions_dir.glob("[0-9]*.md")):
        title = ""
        try:
            for line in adr_file.read_text(encoding="utf-8", errors="replace").splitlines():
                if line.startswith("# "):
                    title = line[2:].strip()
                    break
        except Exception:
            pass
        adrs.append({
            "name": adr_file.stem,
            "title": title,
            "path": str(adr_file.relative_to(REPO_ROOT)),
        })
    return adrs


def discover_edges() -> list:
    """Invoke tools/cascade-finder.py if available; return edge list."""
    cascade_script = REPO_ROOT / "tools" / "cascade-finder.py"
    if not cascade_script.exists():
        return []
    try:
        result = subprocess.run(
            [sys.executable, str(cascade_script)],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(REPO_ROOT),
        )
        if result.returncode == 0 and result.stdout.strip():
            # cascade-finder may output JSON or text; try JSON first
            try:
                data = json.loads(result.stdout)
                if isinstance(data, list):
                    return data
                if isinstance(data, dict) and "edges" in data:
                    return data["edges"]
            except json.JSONDecodeError:
                # Return raw lines as edge descriptors
                edges = []
                for line in result.stdout.strip().splitlines():
                    line = line.strip()
                    if line:
                        edges.append({"raw": line})
                return edges
    except Exception:
        pass
    return []


# ---------------------------------------------------------------------------
# Health check helpers (re-implementing DOCS-* and AS-* in Python)
# ---------------------------------------------------------------------------

def _read_file(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def _grep_count(pattern: str, text: str, flags=re.MULTILINE) -> int:
    return len(re.findall(pattern, text, flags))


def _grep_fixed(literal: str, text: str) -> bool:
    return literal in text


# -- DOCS checks --

def check_docs1_adr_index_forward() -> dict:
    """DOCS-1: every link in decisions/README.md resolves to an existing file."""
    readme = REPO_ROOT / "decisions" / "README.md"
    if not readme.exists():
        return {"id": "DOCS-1", "result": "FAIL", "detail": "decisions/README.md missing"}
    text = _read_file(readme)
    refs = re.findall(r'\(?((?:0|[1-9]\d{3})-[a-z0-9-]+\.md)\)?', text)
    missing = []
    for ref in set(refs):
        if not (REPO_ROOT / "decisions" / ref).exists():
            missing.append(ref)
    if missing:
        return {"id": "DOCS-1", "result": "FAIL", "detail": f"Dangling refs: {missing}"}
    return {"id": "DOCS-1", "result": "PASS", "detail": ""}


def check_docs2_adr_index_reverse() -> dict:
    """DOCS-2: every decisions/NNNN-*.md is in decisions/README.md."""
    readme = REPO_ROOT / "decisions" / "README.md"
    decisions_dir = REPO_ROOT / "decisions"
    if not readme.exists():
        return {"id": "DOCS-2", "result": "FAIL", "detail": "decisions/README.md missing"}
    text = _read_file(readme)
    missing = []
    for f in sorted(decisions_dir.glob("[0-9]*.md")):
        if f.name not in text:
            missing.append(f.name)
    if missing:
        return {"id": "DOCS-2", "result": "FAIL", "detail": f"Not indexed: {missing}"}
    return {"id": "DOCS-2", "result": "PASS", "detail": ""}


def check_docs3_claude_md_agents() -> dict:
    """DOCS-3: every .claude/agents/*.md ref in CLAUDE.md Map exists."""
    claude_md = REPO_ROOT / "CLAUDE.md"
    if not claude_md.exists():
        return {"id": "DOCS-3", "result": "FAIL", "detail": "CLAUDE.md missing"}
    text = _read_file(claude_md)
    refs = re.findall(r'\.claude/agents/([a-z-]+\.md)', text)
    missing = []
    for ref in set(refs):
        if not (REPO_ROOT / ".claude" / "agents" / ref).exists():
            missing.append(ref)
    if missing:
        return {"id": "DOCS-3", "result": "FAIL", "detail": f"Missing agents: {missing}"}
    return {"id": "DOCS-3", "result": "PASS", "detail": ""}


def check_docs4_claude_md_skills() -> dict:
    """DOCS-4: every .claude/skills/*/SKILL.md ref in CLAUDE.md Map exists."""
    claude_md = REPO_ROOT / "CLAUDE.md"
    if not claude_md.exists():
        return {"id": "DOCS-4", "result": "FAIL", "detail": "CLAUDE.md missing"}
    text = _read_file(claude_md)
    refs = re.findall(r'\.claude/skills/([a-z-]+)/SKILL\.md', text)
    missing = []
    for ref in set(refs):
        if not (REPO_ROOT / ".claude" / "skills" / ref / "SKILL.md").exists():
            missing.append(ref)
    if missing:
        return {"id": "DOCS-4", "result": "FAIL", "detail": f"Missing skills: {missing}"}
    return {"id": "DOCS-4", "result": "PASS", "detail": ""}


def check_docs5_n3_literal() -> dict:
    """DOCS-5: no bare N=3 in README.md without adjacent ADR-0013."""
    readme = REPO_ROOT / "README.md"
    if not readme.exists():
        return {"id": "DOCS-5", "result": "PASS", "detail": "README.md missing (skip)"}
    lines = _read_file(readme).splitlines()
    offenders = []
    for i, line in enumerate(lines):
        if "N=3" in line:
            ctx_start = max(0, i - 2)
            ctx_end = min(len(lines), i + 3)
            ctx = "\n".join(lines[ctx_start:ctx_end])
            if "ADR-0013" not in ctx:
                offenders.append(f"L{i+1}: {line.strip()}")
    if offenders:
        return {"id": "DOCS-5", "result": "FAIL", "detail": f"Bare N=3: {offenders}"}
    return {"id": "DOCS-5", "result": "PASS", "detail": ""}


def check_docs6_glossary_md_refs() -> dict:
    """DOCS-6: no GLOSSARY.md refs outside the 5-file allowlist + decisions/."""
    allowlist = {
        ".claude/skills/audit-meta/SKILL.md",
        ".claude/skills/grill-me/SKILL.md",
        "docs/current/concepts/rules/am-docs-literal-drift.md",
        "docs/current/entities/skills/audit-meta.md",
        "docs/current/topics/knowledge-architecture.md",
    }
    offenders = []
    for md_file in REPO_ROOT.rglob("*.md"):
        rel = str(md_file.relative_to(REPO_ROOT)).replace("\\", "/")
        # Skip .git, worktrees, tool-results, decisions/
        if any(skip in rel for skip in [".git/", "worktrees/", "tool-results/", "decisions/"]):
            continue
        if rel in allowlist:
            continue
        try:
            if "GLOSSARY.md" in md_file.read_text(encoding="utf-8", errors="replace"):
                offenders.append(rel)
        except Exception:
            pass
    if offenders:
        return {"id": "DOCS-6", "result": "FAIL", "detail": f"GLOSSARY.md refs: {offenders}"}
    return {"id": "DOCS-6", "result": "PASS", "detail": ""}


def check_docs7_adr_citations() -> dict:
    """DOCS-7: every [ADR-NNNN](decisions/NNNN-*.md) citation resolves."""
    fake_slugs = re.compile(
        r'decisions/00\d{2}-(old-name|fictional|fictional-adr|new-adr|new-decision)\.md'
    )
    offenders = []
    for md_file in REPO_ROOT.rglob("*.md"):
        rel = str(md_file.relative_to(REPO_ROOT)).replace("\\", "/")
        if ".git/" in rel or "worktrees/" in rel:
            continue
        try:
            text = md_file.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        for target in re.findall(r'decisions/[0-9]{4}-[a-z0-9-]+\.md', text):
            if fake_slugs.match(target):
                continue
            if not (REPO_ROOT / target).exists():
                offenders.append(f"{rel} -> {target}")
    if offenders:
        return {"id": "DOCS-7", "result": "FAIL", "detail": f"Dangling ADR citations: {offenders[:5]}"}
    return {"id": "DOCS-7", "result": "PASS", "detail": ""}


def check_docs8_supersession_notes() -> dict:
    """DOCS-8 (WARN): decisions/README.md Status column has superseded-by annotations."""
    readme = REPO_ROOT / "decisions" / "README.md"
    if not readme.exists():
        return {"id": "DOCS-8", "result": "WARN", "detail": "decisions/README.md missing"}
    readme_text = _read_file(readme)
    missing_annotations = []
    decisions_dir = REPO_ROOT / "decisions"
    for adr_file in sorted(decisions_dir.glob("[0-9]*.md")):
        try:
            adr_text = _read_file(adr_file)
            for match in re.finditer(r'^- \*\*Supersedes:\*\*\s*(.+)$', adr_text, re.MULTILINE):
                superseded_ref = match.group(1).strip()
                if "superseded by" not in readme_text.lower():
                    missing_annotations.append(f"{adr_file.name}: {superseded_ref}")
        except Exception:
            pass
    if missing_annotations:
        return {"id": "DOCS-8", "result": "WARN", "detail": f"Missing annotations: {missing_annotations[:3]}"}
    return {"id": "DOCS-8", "result": "PASS", "detail": ""}


def check_docs9_glossary_cap() -> dict:
    """DOCS-9 (WARN): CLAUDE.md glossary entry count <= 35."""
    claude_md = REPO_ROOT / "CLAUDE.md"
    if not claude_md.exists():
        return {"id": "DOCS-9", "result": "WARN", "detail": "CLAUDE.md missing"}
    text = _read_file(claude_md)
    lines = text.splitlines()
    in_glossary = False
    count = 0
    for line in lines:
        if re.match(r'^## Glossary', line):
            in_glossary = True
            continue
        if in_glossary and re.match(r'^## ', line):
            break
        if in_glossary and re.match(r'^- \*\*', line):
            count += 1
    if count > 35:
        return {"id": "DOCS-9", "result": "WARN", "detail": f"Glossary has {count} entries (cap 35)"}
    return {"id": "DOCS-9", "result": "PASS", "detail": f"{count} entries"}


def check_docs10_backlog_surfacing() -> dict:
    """DOCS-10: no backlog-label surfacing idiom in agents/skills (except allowlist)."""
    allowlist = {"backlog-critic.md", "promote-to-backlog"}
    pattern = re.compile(r'(`backlog`-labeled|--label backlog)')
    offenders = []
    for search_dir in [REPO_ROOT / ".claude" / "agents", REPO_ROOT / ".claude" / "skills"]:
        if not search_dir.exists():
            continue
        for md_file in search_dir.rglob("*.md"):
            rel = str(md_file.relative_to(REPO_ROOT)).replace("\\", "/")
            if any(skip in rel for skip in allowlist):
                continue
            try:
                text = md_file.read_text(encoding="utf-8", errors="replace")
                if pattern.search(text):
                    offenders.append(rel)
            except Exception:
                pass
    if offenders:
        return {"id": "DOCS-10", "result": "FAIL", "detail": f"Backlog-label drift: {offenders}"}
    return {"id": "DOCS-10", "result": "PASS", "detail": ""}


# -- AS-* checks --

def _check_as_all_1(path: Path) -> dict:
    """AS-ALL-1: frontmatter name/description/tools/model."""
    text = _read_file(path)
    count = len(re.findall(r'^(name|description|tools|model):', text, re.MULTILINE))
    result = "PASS" if count >= 4 else "FAIL"
    return {"id": "AS-ALL-1", "result": result, "detail": f"field count={count}"}


def _check_as_all_2(path: Path) -> dict:
    """AS-ALL-2: Tool boundaries section heading."""
    text = _read_file(path)
    ok = bool(re.search(r'^#+\s*Tool boundaries', text, re.MULTILINE))
    return {"id": "AS-ALL-2", "result": "PASS" if ok else "FAIL", "detail": ""}


def _check_as_all_3(path: Path) -> dict:
    """AS-ALL-3: cross-reference section heading."""
    text = _read_file(path)
    ok = bool(re.search(r'^#+\s*.*(References|Related|See also|Cross-refs)', text,
                        re.MULTILINE | re.IGNORECASE))
    return {"id": "AS-ALL-3", "result": "PASS" if ok else "FAIL", "detail": ""}


def _check_as_all_4(path: Path) -> dict:
    """AS-ALL-4: no backlog-label surfacing idiom (backlog-critic excluded)."""
    if path.name == "backlog-critic.md":
        return {"id": "AS-ALL-4", "result": "N/A", "detail": "excluded"}
    text = _read_file(path)
    has_drift = bool(re.search(r'(`backlog`-labeled|--label backlog)', text))
    return {"id": "AS-ALL-4", "result": "FAIL" if has_drift else "PASS", "detail": ""}


def _check_as_all_5(path: Path) -> dict:
    """AS-ALL-5: Mandatory reading order OR When invoked section."""
    text = _read_file(path)
    ok = bool(re.search(r'^#+\s*(Mandatory reading order|When invoked)', text, re.MULTILINE))
    return {"id": "AS-ALL-5", "result": "PASS" if ok else "FAIL", "detail": ""}


def _check_as_crit_1(path: Path) -> dict:
    """AS-CRIT-1: Default conservative literal."""
    ok = "Default conservative" in _read_file(path)
    return {"id": "AS-CRIT-1", "result": "PASS" if ok else "FAIL", "detail": ""}


def _check_as_crit_2(path: Path) -> dict:
    """AS-CRIT-2: paranoid OR Adversarial mindset (backlog-critic excluded)."""
    if path.name == "backlog-critic.md":
        return {"id": "AS-CRIT-2", "result": "N/A", "detail": "excluded"}
    text = _read_file(path)
    ok = bool(re.search(r'(paranoid|Adversarial mindset)', text))
    return {"id": "AS-CRIT-2", "result": "PASS" if ok else "FAIL", "detail": ""}


def _check_as_crit_3(path: Path) -> dict:
    """AS-CRIT-3: VERDICT: REASON: ROUND: in body."""
    text = _read_file(path)
    ok = "VERDICT:" in text and "REASON:" in text and "ROUND:" in text
    return {"id": "AS-CRIT-3", "result": "PASS" if ok else "FAIL", "detail": ""}


def _check_as_crit_4(path: Path) -> dict:
    """AS-CRIT-4: 5-section verdict template."""
    text = _read_file(path)
    checks = [
        "Subject of review" in text,
        bool(re.search(r'^#+\s*Rubric', text, re.MULTILINE)),
        bool(re.search(r'^#+\s*Findings', text, re.MULTILINE)),
        bool(re.search(r'^#+\s*Summary', text, re.MULTILINE)),
        bool(re.search(r'verdict:', text, re.IGNORECASE)),
    ]
    ok = all(checks)
    return {"id": "AS-CRIT-4", "result": "PASS" if ok else "FAIL",
            "detail": "" if ok else f"missing sections"}


def _check_as_gen_1(path: Path) -> dict:
    """AS-GEN-1: RESULT: REASON: ARTIFACTS: in generator body."""
    text = _read_file(path)
    ok = "RESULT:" in text and "REASON:" in text and "ARTIFACTS:" in text
    return {"id": "AS-GEN-1", "result": "PASS" if ok else "FAIL", "detail": ""}


def _is_critic(stem: str, path: Path) -> bool:
    if stem in KNOWN_CRITICS or stem == "reviewer":
        return True
    fm = _parse_frontmatter(path)
    desc = fm.get("description", "")
    return "critic" in desc.lower()


def audit_subagents() -> dict:
    agents_dir = REPO_ROOT / ".claude" / "agents"
    results = {}
    if not agents_dir.exists():
        return results
    for agent_md in sorted(agents_dir.glob("*.md")):
        stem = agent_md.stem
        is_critic = _is_critic(stem, agent_md)
        checks = [
            _check_as_all_1(agent_md),
            _check_as_all_2(agent_md),
            _check_as_all_3(agent_md),
            _check_as_all_4(agent_md),
            _check_as_all_5(agent_md),
        ]
        if is_critic:
            checks += [
                _check_as_crit_1(agent_md),
                _check_as_crit_2(agent_md),
                _check_as_crit_3(agent_md),
                _check_as_crit_4(agent_md),
            ]
        else:
            checks.append(_check_as_gen_1(agent_md))
        results[stem] = {
            "type": "critic" if is_critic else "generator",
            "checks": checks,
        }
    return results


def audit_meta() -> dict:
    checks = [
        check_docs1_adr_index_forward(),
        check_docs2_adr_index_reverse(),
        check_docs3_claude_md_agents(),
        check_docs4_claude_md_skills(),
        check_docs5_n3_literal(),
        check_docs6_glossary_md_refs(),
        check_docs7_adr_citations(),
        check_docs8_supersession_notes(),
        check_docs9_glossary_cap(),
        check_docs10_backlog_surfacing(),
    ]
    return {"checks": checks}


def cascade_finder_summary() -> dict:
    cascade_script = REPO_ROOT / "tools" / "cascade-finder.py"
    if not cascade_script.exists():
        return {"available": False, "detail": "tools/cascade-finder.py not found"}
    try:
        result = subprocess.run(
            [sys.executable, str(cascade_script), "--help"],
            capture_output=True, text=True, timeout=10, cwd=str(REPO_ROOT),
        )
        return {"available": True, "detail": "cascade-finder.py present; use /api/architecture edges for data"}
    except Exception as e:
        return {"available": False, "detail": str(e)}


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

    def _serve_sse(self, query: dict):
        """SSE stream: tail workflow-events.jsonl from Last-Event-ID offset."""
        log_path = REPO_ROOT / ".claude" / "logs" / "workflow-events.jsonl"
        last_id = self.headers.get("Last-Event-ID", "")
        try:
            start_line = int(last_id) if last_id else 0
        except ValueError:
            start_line = 0

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        line_index = 0
        try:
            while True:
                if not log_path.exists():
                    # Empty-state: send a keepalive comment and wait
                    self.wfile.write(b": keepalive\n\n")
                    self.wfile.flush()
                    time.sleep(2)
                    continue

                with log_path.open(encoding="utf-8", errors="replace") as f:
                    lines = f.readlines()

                for i, raw in enumerate(lines):
                    if i < start_line:
                        continue
                    raw = raw.strip()
                    if not raw:
                        continue
                    event_id = i + 1
                    data = raw.replace("\n", " ")
                    msg = f"id: {event_id}\ndata: {data}\n\n"
                    self.wfile.write(msg.encode("utf-8"))
                    line_index = event_id

                self.wfile.flush()
                start_line = line_index
                time.sleep(1)

        except (BrokenPipeError, ConnectionResetError):
            pass  # client disconnected — normal

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

        elif path == "/api/health":
            data = {
                "auditMeta": audit_meta(),
                "auditSubagents": audit_subagents(),
                "cascadeFinder": cascade_finder_summary(),
            }
            self._send_json(data)

        elif path == "/api/events":
            self._serve_sse(query)

        elif path == "/api/file":
            rel_path = query.get("path", [""])[0]
            if not rel_path:
                self._send_error(400, "path parameter required")
                return
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
    server = HTTPServer(("localhost", port), DashboardHandler)
    print(f"Dashboard running at http://localhost:{port}", flush=True)
    print(f"Repo root: {REPO_ROOT}", flush=True)
    print("Press Ctrl+C to stop.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping.", flush=True)
        server.server_close()


if __name__ == "__main__":
    main()
