#!/usr/bin/env python3
"""
dashboard/server.py — project-claude workflow dashboard server.

Serves: GET /               -> dashboard/index.html
        GET /api/architecture -> JSON {skills, agents, hooks, adrs, edges}
        GET /api/health       -> JSON {auditMeta, auditSubagents, cascadeFinder}
        GET /api/file?path=   -> file content (path-traversal safe)
        GET /api/events       -> SSE stream of workflow-events.jsonl (slice 2)
        GET /api/runs?n=N     -> last-N runs grouped by session_id (tail-seek)
        GET /api/runs?before=<session_id> -> older runs cursor (for "show older")

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
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

# ---------------------------------------------------------------------------
# Repo root — server.py lives at <repo>/dashboard/server.py
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent
DASHBOARD_DIR = REPO_ROOT / "dashboard"


def _resolve_invoking_repo_root() -> Path:
    """Resolve the repo root from the INVOKING worktree's cwd.

    Used by --generate-readme so the generator writes into the worktree that
    invoked it (not the worktree where server.py physically lives, which may be
    a sibling worktree on a different branch).

    Resolution order:
      1. git rev-parse --show-toplevel (run from cwd — worktree-aware)
      2. $CLAUDE_PROJECT_DIR env var
      3. Path(__file__).resolve().parent.parent (script-file fallback)
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=os.getcwd(),
        )
        if result.returncode == 0:
            root = Path(result.stdout.strip())
            if root.is_dir():
                return root
    except Exception:
        pass

    claude_dir = os.environ.get("CLAUDE_PROJECT_DIR", "")
    if claude_dir:
        p = Path(claude_dir)
        if p.is_dir():
            return p

    return Path(__file__).resolve().parent.parent

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
            # Fix A: use .as_posix() so paths are forward-slash on Windows
            "path": skill_md.relative_to(REPO_ROOT).as_posix(),
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
            # Fix A: use .as_posix() so paths are forward-slash on Windows
            "path": agent_md.relative_to(REPO_ROOT).as_posix(),
        })
    return agents


def _read_hook_description(cmd: str) -> str:
    """Derive a human-readable description for a hook command.

    For .sh-script hooks: read the script's leading comment block (lines after
    the shebang that start with '#').  For inline jq/bash commands: derive a
    short string from the command pattern.
    """
    # .sh script reference: read the script's leading comment block
    m = re.search(r'hooks/([a-z0-9_-]+\.sh)', cmd)
    if m:
        script_path = REPO_ROOT / ".claude" / "hooks" / m.group(1)
        if script_path.exists():
            try:
                lines = script_path.read_text(encoding="utf-8", errors="replace").splitlines()
                for line in lines:
                    stripped = line.strip()
                    if stripped.startswith("#!"):
                        continue  # skip shebang
                    if stripped.startswith("#"):
                        text = stripped.lstrip("#").strip()
                        if text:
                            return text[:100]
                    elif stripped:
                        break  # end of leading comment block
            except Exception:
                pass

    # Inline command patterns: derive description from content
    cmd_lower = cmd.lower()
    if "workflow-events.jsonl" in cmd_lower and "agent_complete" in cmd_lower:
        return "logs agent completions to workflow-events.jsonl"
    if "workflow-events.jsonl" in cmd_lower and "bash_complete" in cmd_lower:
        return "logs bash completions to workflow-events.jsonl"
    if "workflow-events.jsonl" in cmd_lower and "session_stop" in cmd_lower:
        return "logs session-stop event to workflow-events.jsonl"
    if "subagent-edits.log" in cmd_lower:
        return "logs agent file edits; suggests /audit-subagents on agent .md changes"
    if "workflow-events.jsonl" in cmd_lower:
        return "logs workflow event to workflow-events.jsonl"

    # Fallback: truncated raw command
    return cmd[:80]


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
                    # Extract script name; resolve to actual .sh path when available (Fix C)
                    m = re.search(r'hooks/([a-z0-9_-]+\.sh)', cmd)
                    if m:
                        script_name = m.group(1)
                        name = script_name
                        script_path = REPO_ROOT / ".claude" / "hooks" / script_name
                        hook_path = (
                            f".claude/hooks/{script_name}"
                            if script_path.exists()
                            else ".claude/settings.json"
                        )
                    else:
                        name = cmd[:60]
                        hook_path = ".claude/settings.json"
                    hooks.append({
                        "name": name,
                        "event": event,
                        "command": cmd[:120],
                        "description": _read_hook_description(cmd),  # Fix C
                        "path": hook_path,  # Fix C: resolved .sh path
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
            # Fix A: use .as_posix() so paths are forward-slash on Windows
            "path": adr_file.relative_to(REPO_ROOT).as_posix(),
        })
    return adrs


def discover_edges() -> list:
    """Infer edges from canonical file bodies (body-grep, no cascade-finder).

    Edge types:
      skill -> agent  : skill SKILL.md body mentions a known agent stem name
      agent -> adr    : agent body cites ADR-NNNN or decisions/NNNN-
      hook  -> event  : each hook fires on its declared event

    Conservative: match agent stem names only (not path fragments).
    Deduplicate. Cap at 50 edges with a stderr warning if exceeded.
    """
    edges: list = []
    seen: set = set()

    def add(source: str, stype: str, target: str, ttype: str, label: str = ""):
        key = (source, target)
        if key not in seen:
            seen.add(key)
            edges.append({"source": source, "sourceType": stype,
                          "target": target, "targetType": ttype,
                          "label": label})

    # Collect agent stems for conservative name matching
    agents_dir = REPO_ROOT / ".claude" / "agents"
    agent_stems: set = set()
    if agents_dir.exists():
        for agent_md in agents_dir.glob("*.md"):
            agent_stems.add(agent_md.stem)

    # hook -> event: each configured hook fires on its event (collected first,
    # small set, so they survive if the cap fires)
    settings_path = REPO_ROOT / ".claude" / "settings.json"
    if settings_path.exists():
        try:
            data = json.loads(settings_path.read_text(encoding="utf-8"))
            for event, entries in data.get("hooks", {}).items():
                for entry in entries:
                    for hook in entry.get("hooks", []):
                        cmd = hook.get("command", "")
                        m = re.search(r'hooks/([a-z0-9_-]+\.sh)', cmd)
                        hook_id = m.group(1) if m else cmd[:40]
                        add(hook_id, "hook", event, "event", "fires on")
        except Exception:
            pass

    # skill -> agent: skill body mentions an agent stem as a standalone word
    skills_dir = REPO_ROOT / ".claude" / "skills"
    if skills_dir.exists():
        for skill_md in sorted(skills_dir.glob("*/SKILL.md")):
            skill_name = skill_md.parent.name
            try:
                body = skill_md.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            for stem in sorted(agent_stems):
                # Word-boundary on stem (hyphenated stems need explicit boundary)
                pattern = r'(?<![a-z0-9-])' + re.escape(stem) + r'(?![a-z0-9-])'
                if re.search(pattern, body):
                    add(skill_name, "skill", stem, "agent", "invokes")

    # agent -> adr: agent body cites ADR-NNNN or decisions/NNNN-
    decisions_dir = REPO_ROOT / "decisions"
    if agents_dir.exists():
        for agent_md in sorted(agents_dir.glob("*.md")):
            stem = agent_md.stem
            try:
                body = agent_md.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            adr_nums: set = set(re.findall(r'ADR-(\d{4})', body))
            adr_nums.update(re.findall(r'decisions/(\d{4})-', body))
            for num in sorted(adr_nums):
                if decisions_dir.exists():
                    matching = list(decisions_dir.glob(f"{num}-*.md"))
                    adr_id = matching[0].stem if matching else f"{num}-unknown"
                else:
                    adr_id = f"{num}-unknown"
                add(stem, "agent", adr_id, "adr", "cites")

    # Cap and log if exceeded (guard against runaway false-positive explosion)
    EDGE_CAP = 200
    if len(edges) > EDGE_CAP:
        print(
            f"[dashboard] WARNING: {len(edges)} edges inferred; capping at {EDGE_CAP}.",
            file=sys.stderr, flush=True,
        )
        edges = edges[:EDGE_CAP]

    return edges


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
# Tail-seek helper — yields lines from a text file in reverse order.
# Reads in 64 KiB chunks from the end; never loads the whole file.
# ---------------------------------------------------------------------------

def _iter_lines_reversed(path: Path, chunk_size: int = 65536):
    """Yield UTF-8 decoded lines from *path* in reverse order (last line first).

    Uses seek/read on 64 KiB chunks so callers can stop early after collecting
    enough session groups without ever loading the full file into memory.
    """
    with path.open("rb") as f:
        f.seek(0, 2)  # seek to end
        remaining = f.tell()
        buf = b""
        while remaining > 0:
            read_size = min(chunk_size, remaining)
            remaining -= read_size
            f.seek(remaining)
            chunk = f.read(read_size)
            # Prepend new chunk to leftover buffer
            buf = chunk + buf
            # Split on newlines; keep first fragment (may be incomplete line)
            # The last element of split is the incomplete leading fragment
            parts = buf.split(b"\n")
            # parts[0] may be partial; save it; yield the rest in reverse
            buf = parts[0]
            for part in reversed(parts[1:]):
                decoded = part.decode("utf-8", errors="replace")
                yield decoded
        # Yield whatever is left in buf (the very first line of the file)
        if buf:
            yield buf.decode("utf-8", errors="replace")


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

    def _serve_runs(self, query: dict) -> dict:
        """Return last-N complete runs grouped by session_id — tail-seek, no full-file read.

        Query params:
          n / limit : int  — how many runs to return (default 2)
          before    : str  — session_id cursor; return runs that appear BEFORE
                            (i.e. older than) this session in the file.

        Returns: {runs: [{session_id, first_ts, last_ts, events: [...]}]}
        Runs are ordered newest-first (by first_ts descending).
        Events within each run are time-ordered (ascending, as logged).
        Events without a session_id are grouped under "unknown".

        Implementation: reads the file backwards in 64 KiB chunks to collect
        only the lines needed for the last N session_id groups.  For the
        ?before cursor it scans backward from the end to skip sessions until
        the cursor session_id is exhausted, then collects N more groups.
        This avoids loading the full file on the hot path.
        """
        log_path = REPO_ROOT / ".claude" / "logs" / "workflow-events.jsonl"
        if not log_path.exists():
            return {"runs": []}

        # Parse query params
        try:
            n = int((query.get("n") or query.get("limit") or ["2"])[0])
        except (ValueError, IndexError, TypeError):
            n = 2
        n = max(1, min(n, 50))  # safety clamp

        before_cursor = None
        before_raw = (query.get("before") or [""])[0]
        if before_raw:
            before_cursor = before_raw

        try:
            # Read lines backward via chunk-seek so we never load the full file
            lines_reversed = _iter_lines_reversed(log_path)

            # Collect session groups in reverse insertion order (newest first)
            sessions_newest_first: list = []  # list of (sid, [event, ...])
            sid_to_idx: dict = {}

            # When before_cursor is set we skip all sessions that appear AFTER
            # the cursor in the file (i.e., sessions newer than the cursor when
            # reading reversed).  We track whether we have SEEN the cursor
            # session at all; only AFTER we first encounter it AND then move past
            # it (into a different session_id) do we start collecting.
            cursor_seen = False  # have we observed at least one cursor-session line?
            in_before_skip = (before_cursor is not None)

            for raw in lines_reversed:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    obj = json.loads(raw)
                except Exception:
                    continue

                sid = obj.get("session_id") or "unknown"

                if in_before_skip:
                    if sid == before_cursor:
                        # Inside the cursor session — mark it seen, keep skipping
                        cursor_seen = True
                        continue
                    elif not cursor_seen:
                        # Haven't seen the cursor yet; this is a newer session — skip
                        continue
                    else:
                        # cursor_seen and now a different sid → we've passed the cursor
                        in_before_skip = False
                        # Fall through to process this line normally

                if sid not in sid_to_idx:
                    if len(sessions_newest_first) >= n:
                        break  # have enough sessions; stop reading
                    sid_to_idx[sid] = len(sessions_newest_first)
                    sessions_newest_first.append((sid, [obj]))
                else:
                    idx = sid_to_idx[sid]
                    sessions_newest_first[idx][1].append(obj)

        except Exception:
            return {"runs": []}

        runs = []
        for sid, events_reversed in sessions_newest_first:
            # Events were collected newest-to-oldest; reverse to get time order
            events = list(reversed(events_reversed))
            first_ts = events[0].get("ts", "") if events else ""
            last_ts = events[-1].get("ts", "") if events else ""
            runs.append({"session_id": sid, "first_ts": first_ts,
                         "last_ts": last_ts, "events": events})

        # Already newest-first from reversed iteration; sort is belt-and-suspenders
        runs.sort(key=lambda r: r["first_ts"], reverse=True)
        return {"runs": runs}

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

        elif path == "/api/runs":
            self._send_json(self._serve_runs(query))

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
    server = HTTPServer(("localhost", port), DashboardHandler)
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


# ---------------------------------------------------------------------------
# README generator  (--generate-readme CLI mode)
# ---------------------------------------------------------------------------

# Fixed pipeline diagram — canonical Mermaid block; static because the diagram
# represents the *designed* pipeline topology, not a runtime-derived graph.
# Reuse discover_* for the component-map and counts sections.

_PIPELINE_DIAGRAM = """\
```mermaid
flowchart TD
  subgraph S1["Stage 1: Idea capture"]
    U1[User] --> GM["/grill-me"]
    GM -->|settled design| SHIP["/ship"]
  end
  subgraph S2["Stage 2: PRD authoring"]
    SHIP --> TOPRD["/to-prd"]
    TOPRD --> PRDC[prd-critic]
    TOPRD -.if ADR.-> ADRC[adr-critic]
    PRDC -->|joint APPROVE| PRDISSUE[(PRD issue)]
    ADRC -->|joint APPROVE| PRDISSUE
    PRDC -.BLOCK ≤3 rounds.-> TOPRD
    ADRC -.BLOCK ≤3 rounds.-> TOPRD
  end
  subgraph S3["Stage 3: Slice decomposition"]
    PRDISSUE --> TOISSUES["/to-issues"]
    TOISSUES --> SLICER[slicer]
    SLICER -->|N alternatives| SLICERC[slicer-critic]
    SLICERC -->|APPROVE| SLICEISSUES[(slice issues)]
    SLICERC -.BLOCK ≤1 revision.-> SLICER
  end
  subgraph S4["Stage 4: Implementation"]
    SLICEISSUES --> IMPL[implementer]
    IMPL --> PR[(PR with Closes #N)]
    PR --> REV[reviewer]
    REV -->|APPROVE| MERGE[(merged on main)]
    REV -.BLOCK ≤3 rounds.-> IMPL
    REV -.round-3 BLOCK.-> NH[needs-human label]
  end
  subgraph S5["Stage 5: Acceptance"]
    MERGE --> QA["/qa-plan"]
    QA --> U2[User accepts PRD]
  end
  subgraph SS["Side workflows"]
    AUTO["/audit-subagents"] -.periodic.- REV
    GA["/glossary-add"] --> GC[glossary-critic]
    GC -->|APPROVE| GAPR[(glossary PR)]
    GAPR --> REV
    CAP[captured issue] --> PTB["/promote-to-backlog"]
    PTB --> BC[backlog-critic]
    BC -->|APPROVE| BL[backlog label]
    BC -->|BLOCK| CAPSTAY[stays in captured tier]
  end
  classDef human fill:#3b82f6,color:#fff
  classDef skill fill:#14b8a6,color:#fff
  classDef gen fill:#22c55e,color:#fff
  classDef critic fill:#f97316,color:#fff
  classDef reviewer fill:#ef4444,color:#fff
  classDef artifact fill:#9ca3af,color:#fff
  class U1,U2 human
  class GM,SHIP,TOPRD,TOISSUES,QA,AUTO,GA,PTB skill
  class SLICER,IMPL gen
  class PRDC,ADRC,SLICERC,GC,BC critic
  class REV reviewer
  class PRDISSUE,SLICEISSUES,PR,MERGE,NH,GAPR,CAP,BL,CAPSTAY artifact
```"""


def _build_component_map() -> str:
    """Build the component-map section from filesystem discovery."""
    skills = discover_skills()
    agents = discover_agents()
    hooks = discover_hooks()
    adrs = discover_adrs()

    lines = []

    # Skills
    lines.append("### Skills\n")
    lines.append("User-invocable commands under `.claude/skills/`:\n")
    if skills:
        for s in skills:
            name = s.get("name") or s["path"].split("/")[-2]
            desc = s.get("description", "")
            path = s["path"]
            if desc:
                lines.append(f"- **[`/{name}`]({path})** — {desc}")
            else:
                lines.append(f"- **[`/{name}`]({path})**")
    else:
        lines.append("_(no skills found)_")
    lines.append("")

    # Agents
    lines.append("### Subagents\n")
    lines.append("Specialist agents under `.claude/agents/`:\n")
    critics = [a for a in agents if a.get("type") == "critic"]
    generators = [a for a in agents if a.get("type") != "critic"]
    if critics:
        lines.append("**Critics** (adversarial gates):\n")
        for a in critics:
            name = a.get("name") or a["stem"]
            desc = a.get("description", "")
            path = a["path"]
            if desc:
                lines.append(f"- **[`{name}`]({path})** — {desc}")
            else:
                lines.append(f"- **[`{name}`]({path})**")
        lines.append("")
    if generators:
        lines.append("**Generators** (output-producing agents):\n")
        for a in generators:
            name = a.get("name") or a["stem"]
            desc = a.get("description", "")
            path = a["path"]
            if desc:
                lines.append(f"- **[`{name}`]({path})** — {desc}")
            else:
                lines.append(f"- **[`{name}`]({path})**")
        lines.append("")

    # Hooks
    lines.append("### Hooks\n")
    lines.append(
        "Claude Code session hooks configured in `.claude/settings.json`"
        " (scripts in `.claude/hooks/`):\n"
    )
    if hooks:
        seen_hooks = set()
        for h in hooks:
            key = (h["name"], h["event"])
            if key in seen_hooks:
                continue
            seen_hooks.add(key)
            name = h["name"]
            event = h["event"]
            desc = h.get("description", "")
            path = h.get("path", ".claude/settings.json")
            if desc:
                lines.append(f"- **[`{name}`]({path})** (`{event}`) — {desc}")
            else:
                lines.append(f"- **[`{name}`]({path})** (`{event}`)")
    else:
        lines.append("_(no hooks configured)_")
    lines.append("")

    # ADRs (just count + link)
    lines.append("### Architecture Decision Records\n")
    lines.append(
        f"[`decisions/`](decisions/) holds {len(adrs)} ADR(s)."
        " See [`decisions/README.md`](decisions/README.md) for the full index."
    )
    lines.append("")

    return "\n".join(lines)


def _build_counts() -> str:
    """Build the counts summary line."""
    skills = discover_skills()
    agents = discover_agents()
    hooks = discover_hooks()
    adrs = discover_adrs()

    critics = [a for a in agents if a.get("type") == "critic"]
    generators = [a for a in agents if a.get("type") != "critic"]

    # Deduplicate hooks by (name, event)
    seen = set()
    unique_hooks = []
    for h in hooks:
        key = (h["name"], h["event"])
        if key not in seen:
            seen.add(key)
            unique_hooks.append(h)

    lines = [
        f"> **Auto-generated component counts** (as of last generator run):"
        f" {len(skills)} skill(s),"
        f" {len(critics)} critic(s) + {len(generators)} generator(s),"
        f" {len(unique_hooks)} hook(s),"
        f" {len(adrs)} ADR(s)."
    ]
    return "\n".join(lines)


def generate_readme() -> None:
    """Read README.template.md, substitute placeholders, write README.md.

    Placeholders:
      {{GENERATED:pipeline-diagram}}  — fixed Mermaid diagram block
      {{GENERATED:component-map}}     — filesystem-derived skills/agents/hooks/ADR map
      {{GENERATED:counts}}            — one-line component count summary

    Idempotent: running twice produces the same README.md.
    No LLM calls — pure stdlib + pathlib.

    Uses _resolve_invoking_repo_root() so that when invoked from a worktree,
    the README is written into THAT worktree's root rather than the script's
    physical location (which may be a sibling worktree on a different branch).
    """
    gen_root = _resolve_invoking_repo_root()
    template_path = gen_root / "README.template.md"
    readme_path = gen_root / "README.md"

    if not template_path.exists():
        print(
            f"ERROR: template not found at {template_path}",
            file=sys.stderr, flush=True,
        )
        sys.exit(1)

    template = template_path.read_text(encoding="utf-8")

    substitutions = {
        "{{GENERATED:pipeline-diagram}}": _PIPELINE_DIAGRAM,
        "{{GENERATED:component-map}}": _build_component_map().rstrip("\n"),
        "{{GENERATED:counts}}": _build_counts(),
    }

    result = template
    for placeholder, value in substitutions.items():
        result = result.replace(placeholder, value)

    header = (
        "<!-- AUTO-GENERATED from README.template.md"
        " — edit the template, run the generator. -->\n"
    )
    final = header + result

    readme_path.write_text(final, encoding="utf-8")
    print(f"README.md written ({len(final)} bytes)", flush=True)


if __name__ == "__main__":
    if "--generate-readme" in sys.argv:
        generate_readme()
    else:
        main()
