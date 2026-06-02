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

set -euo pipefail

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
    python3 dashboard/server.py --generate-readme > /dev/null 2>&1
    if git diff --exit-code README.md > /dev/null 2>&1; then
        pass "README.md is up-to-date with regen output"
    else
        fail "README.md is stale — run 'python3 dashboard/server.py --generate-readme' and commit"
        # restore to not pollute diff output for other checks
        git checkout -- README.md 2>/dev/null || true
    fi
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
    pass "no commits ahead of origin/main — nothing to check"
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
