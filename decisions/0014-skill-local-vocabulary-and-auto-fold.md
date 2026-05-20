# ADR-0014: Skill-local vocabulary sections + `/glossary-fold` auto-fold (supersedes ADR-0012 D6 deferral)

- **Status:** Accepted
- **Date:** 2026-05-20
- **Supersedes:** [ADR-0012](0012-glossary-consolidation-single-tier.md) D6 — the deferral becomes the implementation. ADR-0012 D6 deferred the skill-local-vocabulary + auto-folder mechanism to "a follow-up PRD (likely ADR-0013)"; this ADR is that follow-up (numbered 0014 since ADR-0013 shipped first for the slicer N=1 carveout per PRD #116).
- **Extends:** [ADR-0012](0012-glossary-consolidation-single-tier.md) D1 (single-tier glossary in CLAUDE.md — preserved); D2 (≥3-citation inclusion threshold — preserved + applied to skill-local entries); D3 (`/glossary-add` simplified — preserved + complemented by `/glossary-fold`); D4 (`glossary-critic` rubric — preserved unchanged; rules 2 and 5 handle conflict + threshold); D5 (~35 entry cap — preserved as soft policy); D7 (bootstrap-mode forward-binding pattern — modeled in this ADR's own D6 below). [ADR-0008](0008-workflow-autolog-bootstrap-and-naming.md) D7 (6-critic-cap meta-rule — honored; no new critic added). [ADR-0004](0004-bypass-prevention.md) D2 (bootstrap-mode policy cited in D6 below). The no-args invocation pattern used by `/glossary-fold` is convention across sibling skills (`/glossary-add`, `/audit-subagents`, `/promote-to-backlog`), not anchored to a single ADR D-ID.

## Context

ADR-0012 (shipped 2026-05-20 via PR #113) consolidated the two-tier glossary into single-tier in CLAUDE.md and tightened glossary-critic's inclusion threshold. ADR-0012 D6 explicitly deferred the second half of the user's 2026-05-20 ask: *"we should automatically add [skill-local vocabulary] to the claude.md"*. The deferral named two questions for the follow-up PRD: (a) skill local-vocabulary section convention; (b) auto-fold trigger mechanism (reviewer rule? new skill? slice-merge hook?); (c) conflict resolution.

The grill session for PRD #119 (this ADR's parent PRD) made the design decisions inline (no formal /grill-me — per cadence memory + ADR-0013 D1 degenerate-case framing, the design space was sufficiently bounded by ADR-0012 D6's framing to ship without grilling):

- **Section location:** end of skill body, optional, `## Local vocabulary` H2.
- **Trigger:** user-invoked skill `/glossary-fold` (matches `/glossary-add` pattern; doesn't add reviewer burden; doesn't require hooks).
- **Conflict resolution:** existing `glossary-critic` rubric rule 2 (duplicate-check) catches same-term conflicts; skill author resolves.
- **No new critic:** `glossary-fold` invokes existing `glossary-critic` per entry. Honors ADR-0008 D7 6-critic-cap.

## Decisions

### D1: Optional skill-local `## Local vocabulary` section convention

Each skill MAY include an OPTIONAL `## Local vocabulary` H2 section at the END of its `SKILL.md` body (after `## References` if present, before any final notes). Entries follow the canonical CLAUDE.md glossary format verbatim per ADR-0007 D2 (preserved):

- **term** — one-sentence definition.
  - *Scope:* (a) project jargon coined here / (b) external standard adopted / (c) common word with narrowed meaning here
  - *Authority:* `ADR-NNNN D-X` | URL | `external`
  - *See also:* related terms

The section is **opt-in**. Existing skills without `## Local vocabulary` work unchanged; no retroactive addition mandate.

### D2: `/glossary-fold` skill (NEW)

`/glossary-fold` is a user-invokable skill at `.claude/skills/glossary-fold/SKILL.md`. Behavior:

1. **Glob** `.claude/skills/*/SKILL.md` for `## Local vocabulary` H2 sections.
2. **Parse** entries (same format as CLAUDE.md glossary per D1).
3. **For each entry**:
   - If term already exists in `CLAUDE.md`'s `## Glossary (key terms)` section → **skip** with `SKIPPED (already in CLAUDE.md)` note in report.
   - If term fails citation-threshold check per ADR-0012 D2 (`grep -rc <term> decisions/ .claude/agents/ .claude/skills/` < 3 OR hits in < 2 dirs) → **defer** with `DEFERRED (below threshold: <count> citations across <dir-count> dirs)` note.
   - Otherwise → **invoke `glossary-critic`** per entry (existing 5-rule rubric); accumulate APPROVE'd entries.
4. **Open one PR** adding all APPROVE'd entries to CLAUDE.md `## Glossary (key terms)` section (alphabetical insert), with the report (skipped/deferred/approved) as the PR body Verification section.
5. **No-args invocation** — convention across sibling skills (`/glossary-add`, `/audit-subagents`, `/promote-to-backlog`), not anchored to a single ADR D-ID (matches Extends-header phrasing).

Tool boundaries: Read, Glob, Grep, Bash (for `gh api`, `gh pr create`, `Agent` invocation of `glossary-critic`).

### D3: Conflict resolution (term collision)

If a skill-local entry has the same term as a CLAUDE.md glossary entry with a DIFFERENT definition, `glossary-critic` BLOCKs the fold per its existing rule 2 (duplicate-check). The skill author resolves by:
- (a) updating the skill-local entry to match the CLAUDE.md definition (most common path), OR
- (b) requesting the CLAUDE.md entry be updated separately via `/glossary-add` revision, OR
- (c) renaming the local term to disambiguate.

No new rubric rule is added; rule 2's existing semantics cover this case. If a future false-positive pattern emerges (e.g., legitimately-different definitions for context-dependent terms), a follow-up PRD may add a `local-only:` field to the entry shape — out of scope here.

### D4: No new critic (`glossary-fold` invokes existing `glossary-critic` per entry)

The fold mechanism is critic-gated by `glossary-critic` (existing). No `glossary-fold-critic` subagent is added. This honors:
- **ADR-0008 D7 6-critic-cap meta-rule:** zero new critics.
- **ADR-0011 D1 absorption-choice precedent:** skills handle bulk/periodic operations; subagents handle synchronous adversarial gates.

If `/glossary-fold`'s output proves unreliable (e.g., systemic false approves), a future PRD may extend `glossary-critic`'s rubric or wrap `/glossary-fold` in additional verification — but not add a 7th critic.

### D5: No auto-trigger; user-invoked only

`/glossary-fold` is user-invoked, matching `/glossary-add`'s pattern. No reviewer rule (would couple to PR-time only and ignore drift in unchanged skill bodies). No merge hook (would require hook infrastructure). No scheduled job (out of scope).

If user-invocation friction proves high (e.g., skill authors add `## Local vocabulary` entries but never run `/glossary-fold`), a future PRD may add an `/audit-skills`-style periodic audit that surfaces unsynchronized local vocabularies. Out of scope here.

### D6: Bootstrap-mode acknowledgment (per ADR-0004 D2)

This ADR's mechanism binds **forward from slice 1's merge**. Specifically:
- The `## Local vocabulary` section convention applies to skills that opt in from slice 1 forward. Existing skills without the section are grandfathered indefinitely; there is no audit-against-this-mandate.
- `/glossary-fold` operates on whatever `## Local vocabulary` sections exist at invocation time. Pre-merge skills had none; post-merge skills may or may not.
- ADR-0012 D6's deferral is replaced by this ADR's D1-D5; the deferral is fulfilled.
- No retroactive sweep of existing CLAUDE.md glossary entries against this ADR's mechanism (the consolidated glossary stands; ADR-0012's bootstrap-mode for D2 threshold preserved).

The 6-critic-cap (ADR-0008 D7) is unaffected — no new critic.

## Consequences

### Positive

- **Closes the user's 2026-05-20 second ask.** The auto-folder mechanism the user wanted (deferred per ADR-0012 D6) is now implementable.
- **Reduces glossary drift.** Skill authors can lock terminology close to the prose that uses it; `/glossary-fold` proposes globally-qualified terms to CLAUDE.md without requiring per-term `/glossary-add` ceremony.
- **No 6-critic-cap pressure.** Honors ADR-0008 D7 cleanly.
- **Composable with future improvements.** Auto-trigger, periodic audit, and threshold-relaxation are all separable future PRDs that don't require re-deciding this ADR.

### Negative / Accepted

- **Opt-in convention may see low adoption.** Skill authors who don't see the value may never add `## Local vocabulary` sections, and `/glossary-fold` becomes dead-letter. Mitigation: D6 acknowledges this; if adoption is zero after observation, a future PRD may sunset the mechanism. The dogfood in slice 1 (an example in `/ship/SKILL.md`) seeds the pattern.
- **User-invoked-only means drift can accumulate.** A skill with 5 entries in `## Local vocabulary` that the author forgets to fold becomes silent staleness. Acceptable trade — reviewer rule or auto-trigger could be added later if pain emerges.
- **Conflict resolution puts burden on skill author.** Rule 2 BLOCK requires the author to investigate; for context-dependent definitions, this may feel restrictive. Acceptable for the walking-skeleton; D3 names the future-PRD path if pain emerges.

## Alternatives considered

- **Alt-A: Reviewer rule (R-LOCAL-VOCAB) auto-folds on PR-time.** Rejected per D5. Couples to PR-time only; reviewer rubric grows from 11 → 12 rules; couples meta-quality to per-PR gating which is the wrong cadence for periodic vocabulary drift.
- **Alt-B: Merge hook auto-folds.** Rejected per D5. Requires hook infrastructure (`.githooks/`) extension; couples to git-side rather than human-side cadence; hooks are bypassable.
- **Alt-C: Scheduled job (cron/GitHub Action) auto-folds.** Rejected per D5. Requires CI infrastructure (backlog #63 deferred); user-invoked is the right baseline.
- **Alt-D: New `glossary-fold-critic` subagent.** Rejected per D4. Breaches 6-critic-cap (ADR-0008 D7); existing `glossary-critic` is the right gate; folder mechanism is bulk-of-singles, each gated by `glossary-critic`.
- **Alt-E: Modify `glossary-critic`'s rubric for fold-specific cases.** Rejected per D3. Rules 2 + 5 already cover the cases; no new rubric rule needed.
- **Alt-F: Inline definitions in skill prose (no dedicated section).** Rejected — the convention's value is grep-ability and structured parsing; inline prose isn't mechanically discoverable.
- **Alt-G: Separate file per skill (`.claude/skills/<name>/glossary.md`).** Rejected — extra file proliferation; in-body section is simpler and stays close to the prose that uses the term.
- **Alt-H: Require `## Local vocabulary` for all skills (mandatory not opt-in).** Rejected — would force ceremony on skills that don't need it; opt-in matches the "don't add abstractions before they're needed" principle.

## Open questions deferred

- **Adoption metric**: defer to post-merge observation. If zero adoption after 3 months, future PRD may sunset the mechanism.
- **Auto-trigger emergence**: if user-invocation friction proves high, future PRD may add periodic audit or reviewer-rule integration.
- **Threshold relaxation for skill-local terms**: start strict (ADR-0012 D2 unchanged); if false negatives accumulate, future PRD may add a `local-only:` carveout.
- **Subagent-local vocabulary**: this ADR scopes to `.claude/skills/*/SKILL.md` only; subagents under `.claude/agents/` have their own conventions per ADR-0001 D6. A future PRD may extend.

## Future direction

- **Periodic skill audit** that surfaces unsynchronized local vocabularies — sibling to `/audit-subagents` (ADR-0011).
- **Threshold relaxation** for skill-local terms (the `local-only:` carveout above).
- **Subagent-local vocabulary** extension (apply this convention to `.claude/agents/*.md`).
- **`/glossary-extract` reverse skill** — propose moving rarely-cited CLAUDE.md entries down to skill-local sections (the reverse direction).

## References

- [ADR-0012](0012-glossary-consolidation-single-tier.md) — D6 (the deferral being filled); D1-D5, D7 (preserved, see Extends header). ADR-0012 has D1-D7 only.
- [ADR-0007](0007-vocabulary-glossary-and-grill-me-extension.md) D2 (entry shape preserved). The no-args invocation pattern is convention across sibling skills, not anchored to a single ADR D-ID (per Extends-header correction).
- [ADR-0008](0008-workflow-autolog-bootstrap-and-naming.md) D7 (6-critic-cap meta-rule — honored).
- [ADR-0004](0004-bypass-prevention.md) D2 — bootstrap-mode policy cited in D6.
- [ADR-0011](0011-subagent-quality-framework.md) D1 (skill-vs-critic absorption-choice precedent).
- [ADR-0003](0003-autonomous-pipeline-with-critics.md) D8 — macro-ADR placement at grill→PRD boundary.
- `.claude/skills/glossary-fold/SKILL.md` — the skill being created (D2).
- `.claude/skills/glossary-add/SKILL.md` — sibling single-entry skill (preserved, complementary to D2).
- `.claude/agents/glossary-critic.md` — the critic invoked per fold (preserved).
- `CLAUDE.md` `## Glossary (key terms)` — the destination for folded entries.
- Backlog #98 (closed) — the original captured item for glossary consolidation (this PRD's grandparent).
- PR #113 (closed) — the consolidation merge; ADR-0012 D6 was the deferral.
