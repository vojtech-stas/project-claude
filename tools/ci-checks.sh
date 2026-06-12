#!/usr/bin/env bash
# tools/ci-checks.sh — deterministic CI gate for project-claude.
#
# Runnable locally and in GitHub Actions (see .github/workflows/ci.yml).
# Exits 0 if all checks pass; exits 1 if any check fails.
# ADR-0042 D1 — mechanical CI gate; mirrors audit-meta DOCS-1/DOCS-2/DOCS-7
# logic + ADR-0041 D2 origin/main base for commit-range checks.
#
# Usage: bash tools/ci-checks.sh
#   (run from the repo root)

# set -e intentionally OMITTED: this script accumulates failures via FAIL_COUNT
# so ALL checks must run regardless of earlier failures.  -u (unbound vars) and
# -o pipefail are kept; -e (abort-on-error) is incompatible with the run-all
# design (see #727 root-cause).
set -uo pipefail

FAIL_COUNT=0

fail() {
    echo "FAIL: $*" >&2
    FAIL_COUNT=$((FAIL_COUNT + 1))
}

pass() {
    echo "PASS: $*"
}

# ---------------------------------------------------------------------------
# CHECK 1: settings.json valid JSON
# ---------------------------------------------------------------------------
echo "--- CHECK 1: .claude/settings.json valid JSON ---"
if python3 -m json.tool .claude/settings.json > /dev/null 2>&1; then
    pass ".claude/settings.json is valid JSON"
else
    fail ".claude/settings.json is not valid JSON"
fi

# ---------------------------------------------------------------------------
# CHECK 2: README regen-clean
# ---------------------------------------------------------------------------
echo "--- CHECK 2: README regen-clean ---"
if command -v python3 > /dev/null 2>&1 && [ -f "dashboard/server.py" ]; then
    # Stash the current README into a temp file so we can restore it without
    # clobbering pre-existing uncommitted edits (issue #727: git checkout --
    # README.md is destructive; cp/mv is safe).
    _readme_tmp=$(mktemp)
    cp README.md "$_readme_tmp"
    python3 dashboard/server.py --generate-readme > /dev/null 2>&1
    if git diff --exit-code README.md > /dev/null 2>&1; then
        pass "README.md is up-to-date with regen output"
    else
        fail "README.md is stale — run 'python3 dashboard/server.py --generate-readme' and commit"
    fi
    # Always restore to pre-check state (avoids polluting diff for other checks
    # and preserves any pre-existing uncommitted edits).
    cp "$_readme_tmp" README.md
    rm -f "$_readme_tmp"
else
    echo "SKIP: CHECK 2 — python3 or dashboard/server.py not available (soft-degrade)"
fi

# ---------------------------------------------------------------------------
# CHECK 3: Commit subjects — ≤72 chars + Conventional Commits format
# ---------------------------------------------------------------------------
echo "--- CHECK 3: commit subjects over origin/main..HEAD ---"
# Fetch origin/main so the range is available in CI (ADR-0041 D2).
git fetch origin main --quiet 2>/dev/null || true

CONV_RE='^(feat|fix|chore|refactor|docs|test|perf|style|build|ci)(\(.+\))?: .+'
RANGE_COMMITS=$(git log --no-merges --format='%s' origin/main..HEAD 2>/dev/null || true)

if [ -z "$RANGE_COMMITS" ]; then
    echo "CHECK 3 VACUOUS — no commits in range; subject-format not verified"
else
    CHECK3_FAIL=0
    while IFS= read -r subject; do
        [ -z "$subject" ] && continue
        # Length check
        len=${#subject}
        if [ "$len" -gt 72 ]; then
            fail "commit subject exceeds 72 chars ($len): $subject"
            CHECK3_FAIL=1
        fi
        # Conventional Commits format
        if ! printf '%s' "$subject" | grep -qE "$CONV_RE"; then
            fail "commit subject not Conventional Commits format: $subject"
            CHECK3_FAIL=1
        fi
    done <<< "$RANGE_COMMITS"
    if [ "$CHECK3_FAIL" -eq 0 ]; then
        pass "all commit subjects pass length + Conventional Commits check"
    fi
fi

# ---------------------------------------------------------------------------
# CHECK 4: Dangling ADR links (DOCS-7 mechanic)
# ---------------------------------------------------------------------------
echo "--- CHECK 4: dangling decisions/NNNN-*.md links in tracked .md files ---"
# Fake/pedagogical slugs to ignore (mirrors audit-meta DOCS-7 allowlist).
FAKE_SLUG_RE='decisions/00[0-9]{2}-(old-name|fictional|fictional-adr|new-adr|new-decision)\.md'

CHECK4_FAIL=0
# Find all tracked .md files (excluding .git).
while IFS= read -r mdfile; do
    [ -f "$mdfile" ] || continue
    # Extract all decisions/NNNN-*.md targets from this file.
    while IFS= read -r target; do
        [ -z "$target" ] && continue
        # Skip fake/example slugs.
        if printf '%s' "$target" | grep -qE "$FAKE_SLUG_RE"; then
            continue
        fi
        if [ ! -f "$target" ]; then
            fail "dangling ADR link '$target' in $mdfile"
            CHECK4_FAIL=1
        fi
    done < <(grep -oE 'decisions/[0-9]{4}-[a-z0-9-]+\.md' "$mdfile" 2>/dev/null | sort -u || true)
done < <(git ls-files '*.md' 2>/dev/null)

if [ "$CHECK4_FAIL" -eq 0 ]; then
    pass "no dangling decisions/NNNN-*.md links found"
fi

# ---------------------------------------------------------------------------
# CHECK 5: decisions/README.md <-> decisions/[0-9]*.md index consistency
# ---------------------------------------------------------------------------
echo "--- CHECK 5: decisions/README.md <-> decisions/*.md index consistency ---"
CHECK5_FAIL=0

# DOCS-1: every index row resolves to an existing file.
while IFS= read -r target; do
    [ -z "$target" ] && continue
    if [ ! -f "decisions/$target" ]; then
        fail "decisions/README.md row references missing file: decisions/$target"
        CHECK5_FAIL=1
    fi
done < <(grep -oE '[0-9]{4}-[a-z0-9-]+\.md' decisions/README.md 2>/dev/null || true)

# DOCS-2: every ADR file on disk has a row in decisions/README.md.
for adrfile in decisions/[0-9]*.md; do
    [ -f "$adrfile" ] || continue
    basename_adr=$(basename "$adrfile")
    if ! grep -qF "$basename_adr" decisions/README.md 2>/dev/null; then
        fail "decisions/README.md missing index row for: $adrfile"
        CHECK5_FAIL=1
    fi
done

if [ "$CHECK5_FAIL" -eq 0 ]; then
    pass "decisions/README.md index is consistent with decisions/*.md on disk"
fi

# ---------------------------------------------------------------------------
# CHECK 6: Dangling ADR D-ID citations (mirrors CHECK 4 / DOCS-7 mechanic)
# ---------------------------------------------------------------------------
echo "--- CHECK 6: dangling ADR D-ID citations in tracked .md files ---"
# Requires python3 + git; soft-degrade if unavailable.
if ! command -v python3 > /dev/null 2>&1 || ! command -v git > /dev/null 2>&1; then
    echo "SKIP: CHECK 6 — python3 or git not available (soft-degrade)"
else
python3 - << 'PYEOF'
import re, os, sys, glob, subprocess

# ---------------------------------------------------------------------------
# Allowlist: (file_suffix_pattern, adr_nnnn, d_id, reason)
# Entries are matched when the source file path ENDS WITH file_suffix_pattern.
# Add an entry here (with a reason comment) instead of editing immutable ADRs.
# ---------------------------------------------------------------------------
ALLOWLIST = [
    # Pedagogical example in AC-SUPERSEDES-WITHOUT-HEADER rule body — fictional
    # scenario contrasting "ADR-0002 D1" with a real policy. ADR-0002 has no D1
    # (only D9-revised). Citation is illustrative, not referential.
    ('.claude/agents/adr-critic.md', '0002', 1,
     'pedagogical example in rule body; fictional D1 for illustration only'),

    # Pedagogical example in GC-AUTHORITY-RESOLVABLE rationale — illustrates
    # what a bad authority citation looks like ("authors citing ADR-0007 D9
    # when the actual section is D8"). ADR-0007 has no D9 (only D1-D7).
    ('.claude/agents/glossary-critic.md', '0007', 9,
     'pedagogical example in rationale; illustrates a bad-citation failure mode'),

]

def is_allowlisted(filepath, nnnn, did):
    """Return True if (filepath, nnnn, did) is in the allowlist."""
    for suffix, a_nnnn, a_did, _ in ALLOWLIST:
        if filepath.endswith(suffix) and nnnn == a_nnnn and did == a_did:
            return True
    return False

# Step 1: Build ADR D-ID heading map from decisions/NNNN-*.md files.
adr_d_ids = {}
for adrfile in sorted(glob.glob('decisions/[0-9]*.md')):
    nnnn = adrfile[10:14]
    headings = set()
    try:
        with open(adrfile, 'r', encoding='utf-8', errors='replace') as f:
            for line in f:
                # Accept: ### D<n>  ### D<n>.  ### D<n>:  ### D<n> (  ### D<n>-
                m = re.match(r'^### D(\d+)([.:( \-]|$)', line.strip())
                if m:
                    headings.add(int(m.group(1)))
    except OSError:
        pass
    adr_d_ids[nnnn] = headings

# Step 2: Enumerate tracked .md files (reuse CHECK 4's exclusions).
result = subprocess.run(
    ['git', 'ls-files', '*.md'],
    capture_output=True, text=True
)
md_files = [
    f for f in result.stdout.strip().split('\n')
    if f
    and not f.startswith('.git/')
    and not f.startswith('.claude/worktrees/')
    and not f.startswith('tool-results/')
]

# Step 3: Citation pattern — catch common forms:
#   ADR-0008 D6
#   [ADR-0008](path) D6
#   ADR-0008 D6/D7  (extracts D6 and D7 separately via findall)
#   Avoids over-matching: D<n> must be the IMMEDIATE next token after the ADR
#   ref (+ optional md-link close), separated by exactly one space — no
#   intervening parentheses, dashes, or prose words.
#   Rejected forms (false positives): "ADR-0033 (D10)" or
#   "[ADR-0012](path) — prose (D10 references)".
CITE_RE = re.compile(
    r'(?:\[)?ADR-([0-9]{4})(?:\][^\)]*\))?'  # ADR-NNNN or [ADR-NNNN](...)
    r' D([0-9]+)\b'                           # single space then D<n> directly
)

# Also catch slash-separated D-IDs like "D6/D7" after the initial match
SLASH_D_RE = re.compile(r'\bD([0-9]+)\b')

# Step 4: Scan all files for citations.
danglings = []  # (filepath, nnnn, did)
seen_danglings = set()

for mdfile in md_files:
    if not os.path.isfile(mdfile):
        continue
    try:
        with open(mdfile, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
    except OSError:
        continue

    for m in CITE_RE.finditer(content):
        nnnn = m.group(1)
        first_did = int(m.group(2))

        # Collect all D-IDs from this match position (handles D6/D7 slash form):
        # Look at the text immediately following the matched D<n> for /D<m> forms.
        tail_start = m.end()
        tail_end = min(len(content), tail_start + 20)
        tail = content[tail_start:tail_end]
        did_list = [first_did]
        for slash_m in re.finditer(r'^/D([0-9]+)\b', tail):
            did_list.append(int(slash_m.group(1)))

        for did in did_list:
            key = (mdfile, nnnn, did)
            if key in seen_danglings:
                continue

            # Skip allowlisted entries.
            if is_allowlisted(mdfile, nnnn, did):
                continue

            # Check ADR file exists.
            adr_glob = glob.glob(f'decisions/{nnnn}-*.md')
            if not adr_glob:
                # ADR file doesn't exist — but this is also caught by CHECK 4.
                # Skip here to avoid double-reporting (CHECK 4 owns file-level checks).
                continue

            # Check D-ID heading exists.
            valid_dids = adr_d_ids.get(nnnn, set())
            if did not in valid_dids:
                seen_danglings.add(key)
                danglings.append((mdfile, nnnn, did))

# Step 5: Report results.
if danglings:
    for filepath, nnnn, did in sorted(danglings):
        print(
            f'FAIL: CHECK 6 — dangling D-ID ADR-{nnnn} D{did} in {filepath}',
            file=sys.stderr
        )
    sys.exit(1)
else:
    print('PASS: CHECK 6 — no dangling ADR D-ID citations found')
    sys.exit(0)
PYEOF
CHECK6_EXIT=$?
if [ "$CHECK6_EXIT" -ne 0 ]; then
    FAIL_COUNT=$((FAIL_COUNT + 1))
fi
fi  # end python3/git availability check

# ---------------------------------------------------------------------------
# CHECK 7: doc-vs-reality drift gate (ADR-0047 D3)
#   (a) source ↔ reality  — PIPELINE/KNOWN_CRITICS spec vs .claude/agents/*.md
#   (b) artifact ↔ source — README critic list entries have matching agent files
#   (c) prose-facts ↔ reality — CLAUDE.md critic count/names vs filesystem
# ---------------------------------------------------------------------------
echo "--- CHECK 7: doc-vs-reality drift gate ---"
if ! command -v python3 > /dev/null 2>&1 || ! command -v git > /dev/null 2>&1; then
    echo "SKIP: CHECK 7 — python3 or git not available (soft-degrade)"
else
python3 - << 'PYEOF'
import re, os, sys, glob

REPO_ROOT = os.getcwd()
AGENTS_DIR = os.path.join(REPO_ROOT, '.claude', 'agents')
SERVER_PY  = os.path.join(REPO_ROOT, 'dashboard', 'server.py')
CLAUDE_MD  = os.path.join(REPO_ROOT, 'CLAUDE.md')
README_MD  = os.path.join(REPO_ROOT, 'README.md')

fail_msgs = []

def fail(msg):
    fail_msgs.append(msg)

# ------------------------------------------------------------------ helpers --
def read_file(path):
    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            return f.read()
    except OSError:
        return ''

# ------------------------------------------------ (a) source ↔ reality ------
# Parse KNOWN_CRITICS from dashboard/server.py (set literal, one name per line).
spec_text = read_file(SERVER_PY)
if not spec_text:
    fail('CHECK 7(a) — could not read dashboard/server.py')
else:
    # Extract the KNOWN_CRITICS set: lines like: "    \"reviewer\","
    kc_block = re.search(
        r'KNOWN_CRITICS\s*=\s*\{([^}]+)\}', spec_text, re.DOTALL
    )
    if not kc_block:
        fail('CHECK 7(a) — KNOWN_CRITICS not found in dashboard/server.py')
    else:
        spec_critics = set(re.findall(r'"([^"]+)"', kc_block.group(1)))
        # Discover agent file stems from .claude/agents/*.md
        agent_stems = set()
        if os.path.isdir(AGENTS_DIR):
            for f in glob.glob(os.path.join(AGENTS_DIR, '*.md')):
                agent_stems.add(os.path.splitext(os.path.basename(f))[0])

        # Every critic in the spec must have a matching agent file
        for critic in sorted(spec_critics):
            if critic not in agent_stems:
                fail(
                    f'CHECK 7(a) — spec critic "{critic}" has no '
                    f'.claude/agents/{critic}.md file'
                )

        # Every *-critic.md file must appear in the spec (or be reviewer.md)
        # We check all agent files whose stem ends in "-critic"
        for stem in sorted(agent_stems):
            if stem.endswith('-critic') and stem not in spec_critics:
                fail(
                    f'CHECK 7(a) — .claude/agents/{stem}.md exists but '
                    f'"{stem}" is not in KNOWN_CRITICS spec'
                )

# ------------------------------------------------ (b) artifact ↔ source -----
# README "Adversarial critics" section lists critics — each must have an agent file.
readme_text = read_file(README_MD)
if not readme_text:
    print('SKIP: CHECK 7(b) — README.md not found (soft-degrade)')
else:
    # Find the "## Adversarial critics" section and extract linked agent names.
    # Pattern: **[`name`](.claude/agents/name.md)**
    section_m = re.search(
        r'##\s+Adversarial critics\s*(.*?)(?=\n## |\Z)',
        readme_text, re.DOTALL
    )
    if section_m:
        section = section_m.group(1)
        # Extract stem from links: .claude/agents/<stem>.md
        readme_critic_stems = set(
            re.findall(r'\.claude/agents/([a-z0-9-]+)\.md', section)
        )
        for stem in sorted(readme_critic_stems):
            agent_path = os.path.join(AGENTS_DIR, stem + '.md')
            if not os.path.isfile(agent_path):
                fail(
                    f'CHECK 7(b) — README "Adversarial critics" lists '
                    f'"{stem}" but .claude/agents/{stem}.md does not exist'
                )
    # If section not found, soft-skip (README structure may differ)

# ------------------------------------------------ (c) prose-facts ↔ reality -
# CLAUDE.md says "currently runs **N critics**: name, name, ..."
claude_text = read_file(CLAUDE_MD)
if not claude_text:
    print('SKIP: CHECK 7(c) — CLAUDE.md not found (soft-degrade)')
else:
    # Re-parse KNOWN_CRITICS (already done above) for count comparison.
    if spec_text and 'spec_critics' in dir():
        # Extract the numeric count claim
        count_m = re.search(
            r'currently runs \*\*(\d+) critics\*\*', claude_text
        )
        if count_m:
            claimed_count = int(count_m.group(1))
            actual_count  = len(spec_critics) if spec_critics else 0
            if claimed_count != actual_count:
                fail(
                    f'CHECK 7(c) — CLAUDE.md claims {claimed_count} critics '
                    f'but KNOWN_CRITICS spec has {actual_count}'
                )

        # Extract names from the inline list after "currently runs **N critics**:"
        list_m = re.search(
            r'currently runs \*\*\d+ critics\*\*:\s*([^\n.]+)',
            claude_text
        )
        if list_m:
            raw = list_m.group(1)
            # Names are backtick-quoted: `reviewer`, `prd-critic`, ...
            named = set(re.findall(r'`([^`]+)`', raw))
            agent_stems_c = set()
            if os.path.isdir(AGENTS_DIR):
                for f in glob.glob(os.path.join(AGENTS_DIR, '*.md')):
                    agent_stems_c.add(os.path.splitext(os.path.basename(f))[0])
            for name in sorted(named):
                if name not in agent_stems_c:
                    fail(
                        f'CHECK 7(c) — CLAUDE.md names critic "{name}" '
                        f'but .claude/agents/{name}.md does not exist'
                    )

# ------------------------------------------------------------------ output --
if fail_msgs:
    for msg in fail_msgs:
        print(f'FAIL: {msg}', file=sys.stderr)
    sys.exit(1)
else:
    print('PASS: CHECK 7 — no doc-vs-reality drift detected')
    sys.exit(0)
PYEOF
CHECK7_EXIT=$?
if [ "$CHECK7_EXIT" -ne 0 ]; then
    FAIL_COUNT=$((FAIL_COUNT + 1))
fi
fi  # end python3/git availability check

# ---------------------------------------------------------------------------
# CHECK 8: Agent-payload hook-path fixture test (ADR-0042 D1 extension)
#   Updated for PRD #668 slice #670: Agent hooks now call log-tool-event.sh
#   (python3 parser path) instead of inline jq.  Assertions updated accordingly:
#   (a) settings.json Agent-matcher hooks call log-tool-event.sh (not inline jq).
#   (b) The fixture's .tool_input.subagent_type resolves non-empty via python3
#       (proves the python3 parser path handles the canonical Agent payload).
#   Agent-payload schema changes: refresh dashboard/fixtures/agent-payload-sample.json
#   and re-verify this check.  Soft-degrades if python3 unavailable.
# ---------------------------------------------------------------------------
echo "--- CHECK 8: Agent-payload hook-path fixture test ---"
FIXTURE="dashboard/fixtures/agent-payload-sample.json"
SETTINGS=".claude/settings.json"
if ! command -v python3 > /dev/null 2>&1; then
    echo "SKIP: CHECK 8 — python3 not available (soft-degrade)"
elif [ ! -f "$FIXTURE" ]; then
    fail "CHECK 8 — fixture not found: $FIXTURE"
elif [ ! -f "$SETTINGS" ]; then
    fail "CHECK 8 — settings.json not found: $SETTINGS"
else
    CHECK8_FAIL=0
    # Assert settings.json Agent-matcher hooks call log-tool-event.sh (python3 path).
    if ! grep -q 'log-tool-event\.sh.*agent_start\|agent_start.*log-tool-event\.sh\|log-tool-event\.sh.*agent_complete\|agent_complete.*log-tool-event\.sh' "$SETTINGS"; then
        fail "CHECK 8 — settings.json Agent hooks do not call log-tool-event.sh for agent_start/agent_complete"
        CHECK8_FAIL=1
    fi
    # Assert the fixture's tool_input.subagent_type resolves non-empty via python3.
    SUBAGENT_VAL=$(python3 -c "
import json, sys
with open('$FIXTURE') as f:
    d = json.load(f)
val = d.get('tool_input', {}).get('subagent_type', '')
print(val)
" 2>/dev/null)
    if [ -z "$SUBAGENT_VAL" ]; then
        fail "CHECK 8 — tool_input.subagent_type resolved empty in $FIXTURE via python3 (fixture stale?)"
        CHECK8_FAIL=1
    fi
    if [ "$CHECK8_FAIL" -eq 0 ]; then
        pass "CHECK 8 — Agent hooks call log-tool-event.sh; python3 resolves subagent_type='$SUBAGENT_VAL' from fixture"
    fi
fi

# ---------------------------------------------------------------------------
# CHECK 9: Dashboard check_docs* drift guard
#   Imports the ten check_docs* functions from dashboard/server.py (safe to
#   import: server-start is guarded by if __name__ == "__main__") and runs
#   each against the live repo.  On a clean main all DOCS-* checks must be
#   PASS or WARN — a FAIL means the dashboard re-implementation has drifted
#   from canonical (the #550/#560/#557 bug class).
#
#   Design rationale: importing server.py is the cheapest, most faithful test
#   of the dashboard's own logic.  Re-deriving the canonical verdict in this
#   script would duplicate logic (YAGNI) and could itself drift.  A spawned
#   Python subprocess avoids any server-import side-effects on the shell
#   process.  WARN-level checks (DOCS-8/DOCS-9) returning WARN is allowed;
#   only a result=="FAIL" trips CHECK 9.
# ---------------------------------------------------------------------------
echo "--- CHECK 9: dashboard check_docs* drift guard ---"
if ! command -v python3 > /dev/null 2>&1; then
    echo "SKIP: CHECK 9 — python3 not available (soft-degrade)"
elif [ ! -f "dashboard/server.py" ]; then
    echo "SKIP: CHECK 9 — dashboard/server.py not found (soft-degrade)"
else
python3 - << 'PYEOF'
import sys, os

# Inject dashboard/ onto the path so "import server" finds server.py
# without starting the HTTP server (guarded by if __name__ == "__main__").
sys.path.insert(0, os.path.join(os.getcwd(), 'dashboard'))
import server  # noqa: E402 — dynamic path manipulation required

CHECK_FNS = [
    server.check_docs1_adr_index_forward,
    server.check_docs2_adr_index_reverse,
    server.check_docs3_claude_md_agents,
    server.check_docs4_claude_md_skills,
    server.check_docs5_n3_literal,
    server.check_docs6_glossary_md_refs,
    server.check_docs7_adr_citations,
    server.check_docs8_supersession_notes,
    server.check_docs9_glossary_cap,
    server.check_docs10_backlog_surfacing,
]

fails = []
for fn in CHECK_FNS:
    r = fn()
    if r.get('result') == 'FAIL':
        fails.append(r)

if fails:
    for r in fails:
        print(
            f"FAIL: CHECK 9 — dashboard check_docs* drift "
            f"({r['id']} reports FAIL on clean main: {r.get('detail','')})",
            file=sys.stderr
        )
    sys.exit(1)
else:
    print('PASS: CHECK 9 — all dashboard check_docs* return non-FAIL on clean main')
    sys.exit(0)
PYEOF
CHECK9_EXIT=$?
if [ "$CHECK9_EXIT" -ne 0 ]; then
    FAIL_COUNT=$((FAIL_COUNT + 1))
fi
fi  # end python3/dashboard/server.py availability check

# ---------------------------------------------------------------------------
# CHECK 10: Trailer-schema completeness (ADR-0054 D2 + ADR-0059 D1/D2)
#   Critic files (*-critic.md + reviewer.md): must document VERDICT, REASON,
#   ROUND, and CRITIC: (attribution field per ADR-0059 D1).
#   Generator files (implementer.md, slicer.md, qa-tester.md): must document
#   DIDNT_TOUCH: and CONCERNS: (scope-disclosure fields per ADR-0059 D2).
#   Whole-file fixed-string grep; SPIDR-I fallback (fenced-block scoping later
#   if false-positive issues arise).  Deterministic, local, network-free.
# ---------------------------------------------------------------------------
echo "--- CHECK 10: trailer-schema completeness (critic CRITIC: + generator DIDNT_TOUCH:/CONCERNS:) ---"
CHECK10_FAIL=0

# --- 10a: Critic files: VERDICT, REASON, ROUND, CRITIC: ---
CRITIC_FILES=()
# nullglob: if no *-critic.md files exist, the glob expands to nothing rather
# than passing the literal pattern string through (closes #667).
shopt -s nullglob
# Collect all *-critic.md files
for f in .claude/agents/*-critic.md; do
    [ -f "$f" ] && CRITIC_FILES+=("$f")
done
shopt -u nullglob
# Add reviewer.md
[ -f ".claude/agents/reviewer.md" ] && CRITIC_FILES+=(".claude/agents/reviewer.md")

for agent_file in "${CRITIC_FILES[@]}"; do
    for key in VERDICT REASON ROUND "CRITIC:"; do
        if ! grep -qF "$key" "$agent_file" 2>/dev/null; then
            fail "CHECK 10 — $agent_file missing trailer key: $key"
            CHECK10_FAIL=1
        fi
    done
done

# --- 10b: Generator files: DIDNT_TOUCH: and CONCERNS: ---
GENERATOR_FILES=()
for f in .claude/agents/implementer.md .claude/agents/slicer.md .claude/agents/qa-tester.md; do
    [ -f "$f" ] && GENERATOR_FILES+=("$f")
done

for agent_file in "${GENERATOR_FILES[@]}"; do
    for key in "DIDNT_TOUCH:" "CONCERNS:"; do
        if ! grep -qF "$key" "$agent_file" 2>/dev/null; then
            fail "CHECK 10 — $agent_file missing generator trailer key: $key"
            CHECK10_FAIL=1
        fi
    done
done

if [ "$CHECK10_FAIL" -eq 0 ]; then
    pass "CHECK 10 — all critic files document VERDICT/REASON/ROUND/CRITIC:; all generator files document DIDNT_TOUCH:/CONCERNS:"
fi

# ---------------------------------------------------------------------------
# CHECK 11: qa-tester.md documents PROOF_SOURCE (ADR-0061 D2)
#   Verifies that qa-tester.md contains the PROOF_SOURCE: field in its
#   production-verify trailer template, confirming that structured proof
#   provenance (session_id + timestamp) is documented for machine-validation.
#   Whole-file fixed-string grep; no network calls; deterministic.
# ---------------------------------------------------------------------------
echo "--- CHECK 11: qa-tester.md documents PROOF_SOURCE ---"
QA_TESTER=".claude/agents/qa-tester.md"
if [ ! -f "$QA_TESTER" ]; then
    fail "CHECK 11 — $QA_TESTER not found"
else
    if grep -qF "PROOF_SOURCE:" "$QA_TESTER" 2>/dev/null; then
        pass "CHECK 11 — $QA_TESTER documents PROOF_SOURCE:"
    else
        fail "CHECK 11 — $QA_TESTER missing PROOF_SOURCE: (required by ADR-0061 D2)"
    fi
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo ""
echo "--- CI SUMMARY ---"
if [ "$FAIL_COUNT" -eq 0 ]; then
    echo "ALL CHECKS PASSED"
    exit 0
else
    echo "FAILED: $FAIL_COUNT check(s) failed" >&2
    exit 1
fi
