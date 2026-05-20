# ADR-0012: Glossary consolidation — single-tier in CLAUDE.md (supersedes ADR-0007 D1)

- **Status:** Accepted
- **Date:** 2026-05-20
- **Supersedes:** [ADR-0007](0007-vocabulary-glossary-and-grill-me-extension.md) D1 (two-tier architecture: key-zone in CLAUDE.md + long-tail in GLOSSARY.md); [ADR-0007](0007-vocabulary-glossary-and-grill-me-extension.md) D5 (glossary-critic rubric — replaced by D4 below per partial-supersession; D5's other facets remain unchanged).
- **Extends:** [ADR-0007](0007-vocabulary-glossary-and-grill-me-extension.md) D2 (entry shape preserved unchanged); D3 (3-category scope rule preserved unchanged); D4 (write-path skill + agent-surfacing-convention pattern preserved); D6 (`/grill-me` doc-path argument preserved unchanged); D7 (bootstrap-mode pattern modeled in ADR-0012's own D7 below). [ADR-0004](0004-bypass-prevention.md) D2 (bootstrap-mode policy cited in D7 below).

## Context

ADR-0007 D1 (shipped 2026-05-15) established a two-tier glossary mechanism: a key-zone in `CLAUDE.md` capped at ~25 entries (auto-loaded), and a long-tail in a separate `GLOSSARY.md` at the repo root (read on-demand by agents when an unfamiliar term comes up). The split was motivated by avoiding CLAUDE.md auto-load bloat: *"only CLAUDE.md is genuinely auto-loaded; separate-file approaches reduce to agent-discipline reliance which user explicitly rejected"*.

Five days of empirical operation surfaced the split's actual cost-benefit:

- The long-tail has grown by exactly **1 entry** ("hamburger method") since ADR-0007 shipped. The read-on-demand path is rarely used.
- `/glossary-add` has zone-classification branching (key-zone vs long-tail) that's pure overhead for a 1-entry tier.
- The on-demand-read path is the exact discipline-burden the user explicitly rejected at ADR-0007-time. The auto-load concern that motivated the split has been resolved by simply observing that CLAUDE.md size growth is bounded by the glossary entry budget itself, not by a separate file mechanism.
- Two files = two places to drift (the same failure mode this project keeps surfacing — see PRD #94's `/audit-subagents` rubric, PRD #103's `backlog`→`captured` propagation across 6 files).

The user surfaced the change directly on 2026-05-20:

> *"I don't like we have GLOSSARY.md and Glossary in the claude.md, I would like to have it all in the claude.md and also i would like to change all the skills so that we actually have long tail of vocabulary there. It should be the last thing there and we should automatically add it to the claude.md, just use the critik to block some stupid stuff that will not be used again and that we will not need."*

The user's framing has two layered asks:
1. **Consolidation** (this ADR's scope): drop GLOSSARY.md; everything lives in CLAUDE.md; glossary-critic enforces a tighter inclusion bar.
2. **Skill auto-folder mechanism** (deferred to future PRD per walking-skeleton tightening): every skill's body has a local-vocabulary section; an auto-fold step at slice-merge time proposes additions to CLAUDE.md.

This ADR addresses ask #1 only.

## Decisions

### D1: Single-tier glossary — consolidated into CLAUDE.md

`GLOSSARY.md` is deleted as a file. The repo's full glossary lives in `CLAUDE.md` under the existing `## Glossary (key terms)` section header (parenthetical "(key terms)" may be dropped since there's no longer a non-key tier — implementer judgment). The single entry currently in GLOSSARY.md ("hamburger method") is merged into the CLAUDE.md glossary section in the same slice as this ADR ships.

**Supersedes ADR-0007 D1.** The two-tier architecture is replaced by single-tier. The auto-load concern that motivated the split (CLAUDE.md size growth) is addressed by D5's raised entry-cap budget rather than by a separate file.

### D2: Tightened inclusion threshold

A term qualifies for the glossary IFF it is **cited ≥3 times across at least two of {`decisions/`, `.claude/agents/`, `.claude/skills/`}**. Mechanically checkable via `grep -rc "<term>" decisions/ .claude/agents/ .claude/skills/` ≥ 3 with hits in ≥2 directories.

This tightens ADR-0007 D5's implicit threshold (which leaned on glossary-critic's scope-rule judgment via D3's a/b/c categories without a numeric bar). The new bar:
- Cross-domain citation requirement (≥2 directories) prevents single-file jargon from leaking in
- Numeric threshold (≥3 occurrences) is mechanically checkable, removing judgment ambiguity for the most common case
- Existing entries are grandfathered (per D7 bootstrap-mode)

### D3: `/glossary-add` SKILL simplification

`.claude/skills/glossary-add/SKILL.md` drops the zone-classification branching (no more `--key` flag or zone argument). The skill always writes to CLAUDE.md. The interactive prompt no longer asks "key-zone or long-tail?" — there is only one destination.

### D4: `glossary-critic.md` rubric update (partial supersession of ADR-0007 D5)

The existing `glossary-critic.md` rubric (per ADR-0007 D5, verified on `origin/main`) has 4 rules: (1) scope category fits exactly one of a/b/c per ADR-0007 D3; (2) no duplicate; (3) one-sentence definition; (4) authority field present and well-formed. The mechanism around the rubric also includes a frontmatter description, a `target zone` invocation parameter with `INVALID_INPUT: target zone unspecified` guard, and a paranoid-linguist mindset block per ADR-0009 D4.

`.claude/agents/glossary-critic.md` changes:

- **Drop the `target zone` invocation parameter and its `INVALID_INPUT` guard.** No longer applicable since there's only one destination (`CLAUDE.md`). Frontmatter description and "When invoked" section both updated to remove zone references.
- **Update rule 2 (no duplicate) duplicate-check arm.** Currently rule 2 says: *"`Grep` for the literal term … against the `## Glossary (key terms)` section of `CLAUDE.md` AND against `GLOSSARY.md`."* Post-consolidation, the `AND … GLOSSARY.md` clause is dropped — `grep` only the `## Glossary (key terms)` section of `CLAUDE.md`.
- **Add a new rubric rule (5)** checking D2's tightened inclusion threshold: *"Term cited ≥3 times across at least two of {`decisions/`, `.claude/agents/`, `.claude/skills/`}."* Verified by the critic via `grep -rc <term> decisions/ .claude/agents/ .claude/skills/` ≥ 3 with hits in ≥2 directories (the critic has `Bash` tool boundary per ADR-0007 D5 + ADR-0011 D2's mechanical-rubric philosophy alignment). The new rule lives at position 5 of the rubric; rules 1–4 stay (with rule 2's grep arm updated as above).
- **Trim the paranoid-linguist mindset block** of two-tier-specific clauses. Currently the mindset block mentions *"duplicate hunting across both tiers (key-zone vs long-tail collisions)"* and *"cross-reference accuracy (pointers that name a zone the term doesn't actually inhabit)."* Both clauses are stale post-consolidation. Replace the first with *"duplicate hunting against the existing CLAUDE.md glossary"*; remove the second clause entirely. Other mindset clauses (scope-category misalignment, authority anchoring drift, definition tightness) are preserved unchanged.
- **Preserve** the asymmetric-default-BLOCK clause per ADR-0009 D3 (already present on `glossary-critic` per its own ADR-0007 drafting + ADR-0009 D3's generalization).
- **Preserve** rules 1, 3, 4 unchanged (scope category a/b/c; one-sentence definition; authority well-formed).

This block is a **partial supersession of ADR-0007 D5** (per the header) — the rubric contract is materially changed (added rule 5, modified rule 2's mechanism, modified invocation contract, trimmed mindset prose), even though most of D5's rubric is preserved. The supersession is bounded to D5; D2/D3/D4/D6 in ADR-0007 are untouched.

### D5: Raised entry-cap budget

The CLAUDE.md glossary section's entry cap is raised from ~25 entries (ADR-0007 D1's key-zone cap) to **~35 entries** to accommodate the merged long-tail with headroom for future additions. Documented in CLAUDE.md's glossary section header prose. This is a soft cap (no mechanical enforcement); `glossary-critic` is the bouncer per D4.

**Headroom rationale (not a quantified bloat solution, a soft policy lever):** the existing CLAUDE.md glossary today has ~22 entries (verified by counting `^- \*\*` lines in the `## Glossary (key terms)` section on `origin/main`). Merging the 1 long-tail entry brings the count to 23 — well under the new 35-entry soft cap. The 12-entry headroom is intentional buffer for future organic additions and for the eventual auto-folder mechanism (D6 deferral). If CLAUDE.md size growth becomes a genuine problem, a future ADR can introduce a hard mechanical cap (e.g., a reviewer rule); today the lever is `glossary-critic`'s rubric, not a size enforcer.

### D6: Skill auto-folder mechanism — DEFERRED

The user's second ask (skill bodies have local-vocabulary sections that auto-fold into CLAUDE.md at slice-merge time) is **deferred to a follow-up PRD**. This ADR's scope is consolidation + critic-rubric tightening only. The deferral is a walking-skeleton tightening per CLAUDE.md rule #2: ship the smallest end-to-end vertical first; the auto-folder mechanism is value-additive but not load-bearing for consolidation.

A future PRD addressing the auto-folder will need its own ADR (likely ADR-0013) covering:
- Skill local-vocabulary section convention
- Auto-fold trigger (reviewer rule? skill body? a new skill?)
- Conflict resolution (skill-local vs CLAUDE.md-global)

Tracked as the natural follow-up; captured if/when this PRD ships.

### D7: Bootstrap-mode acknowledgment (per ADR-0004 D2)

This ADR's mechanism binds **forward from the slice that ships it**. Existing GLOSSARY.md content (the single "hamburger method" entry) is merged into CLAUDE.md as part of the same slice. After merge:

- `GLOSSARY.md` does not exist
- All future `/glossary-add` invocations write only to CLAUDE.md
- Existing CLAUDE.md glossary entries are grandfathered (not retroactively re-audited against D2's tightened threshold)
- `glossary-critic`'s new D4 rubric applies to NEW entries from slice-1 merge forward; existing entries don't need to pass the tightened threshold

The reviewer-enforcement of the ~35 entry cap (D5) is also forward-binding — no retroactive sweep if existing CLAUDE.md somehow has >35 (it has ~22 today, well under).

## Consequences

### Positive

- **Simpler mental model**: one place to look for vocabulary. No more "is it key-zone or long-tail?" cognitive overhead.
- **Reduced drift surface**: one file to maintain vs two.
- **Auto-load gain**: the 1 long-tail entry that was previously on-demand-read is now auto-loaded, eliminating one discipline-burden the user explicitly rejected.
- **`/glossary-add` simpler**: dropping zone branching removes ~15-20 LoC and one interactive question.
- **`glossary-critic` more rigorous**: the tightened D2 inclusion threshold makes the critic's APPROVE/BLOCK decision more mechanical (less judgment-dependent), aligning with ADR-0011's "mechanical/grep-only" philosophy for `/audit-subagents`.

### Negative / Accepted

- **Two open questions remain**: (a) should the section move to end-of-CLAUDE.md per the user's "It should be the last thing there" framing; (b) will the tightened threshold reject useful future entries. Both deferred per PRD §6.
- **GLOSSARY.md deletion is one-way**: agents that learned to read GLOSSARY.md will encounter a missing file on first lookup post-merge. Acceptable because (a) only 1 entry was there, (b) agents auto-load CLAUDE.md so the consolidated content is immediately available, (c) ADR-0007's discipline-burden concern (agents may not read GLOSSARY.md every time) goes away.
- **Skill auto-folder still missing**: the user's second ask is deferred to a follow-up PRD, so this ADR doesn't deliver the full vision. Mitigation: D6 explicitly tracks the deferred work and names what its ADR will need to cover.
- **Tightening + grandfathering creates a subtle two-tier-of-rules**: new entries must pass D2's stricter bar, existing entries are exempt. This is a one-time bootstrap cost; the grandfathered set is small (~22 entries) and the alternative (retroactive audit against the new threshold) would be ceremony for marginal benefit.

## Alternatives considered

- **Alt-A: Keep two-tier as-is, don't consolidate.** Rejected per the user's explicit 2026-05-20 ask. The empirical operation showed the long-tail tier was rarely used; the split's overhead was paying for unused infrastructure.
- **Alt-B: Consolidate AND ship the skill auto-folder mechanism in one PRD.** Rejected per walking-skeleton tightening (CLAUDE.md rule #2). The consolidation is a self-contained vertical; the auto-folder is a meaningfully larger design surface (skill convention, auto-fold trigger, conflict resolution) that warrants its own grill.
- **Alt-C: Keep GLOSSARY.md but reduce it to a redirect/pointer file.** Rejected as a half-measure. Either it's consolidated (single source of truth) or it's tiered (with on-demand-read discipline burden). A pointer file is the worst of both.
- **Alt-D: Move the glossary to a new `vocabulary/` directory with one file per term.** Rejected as over-engineered for a ~25-entry corpus. File-per-term works for hundreds of entries; this glossary is two orders of magnitude smaller.
- **Alt-E: Replace the prose-Markdown glossary with a JSON-schema-validated YAML file.** Rejected as out-of-scope and overkill. The glossary is human-read and human-written; Markdown is the right tool.
- **Alt-F: Keep the entry-cap at ~25 and reject the "hamburger method" entry as the only-tier moves to CLAUDE.md.** Rejected because the existing key-zone has ~22 entries, leaving headroom for 3 more before the cap binds; adding 1 long-tail entry brings the count to 23, well under the existing 25. Raising the cap to ~35 (D5) just provides clean headroom for the auto-folder mechanism's eventual additions.
- **Alt-G: Tighten the inclusion threshold to require ≥5 citations.** Considered; rejected as too tight for a project this small. ≥3 across ≥2 domains is a meaningful bar that still admits genuinely-cross-domain jargon (PRD, slice, critic, etc.).
- **Alt-H: Drop the threshold entirely; let glossary-critic judge by D3's a/b/c scope categories alone.** Rejected because that's the status quo per ADR-0007 and the user wants the bar raised mechanically, not just left to critic judgment.

## Open questions deferred

- **Glossary section placement in CLAUDE.md**: user said *"It should be the last thing there"* — implementer judgment whether to move (current position is mid-document). If moved, ensure Map row's anchor still resolves.
- **Tightened threshold may be too strict for future PRDs**: if useful future entries get rejected, loosen via a future ADR or a per-entry override mechanism.
- **Whether `~35` is the right cap or should be parameterized**: the cap is informational today (glossary-critic doesn't strictly enforce it). If a future PRD makes it strict, the parameter will need a clearer source.

## Future direction

- **Skill auto-folder mechanism (D6 deferral)**: future PRD adds local-vocabulary sections to each skill body + an auto-fold trigger (reviewer rule? a new `/glossary-extract` skill? a slice-merge hook?). ADR-0013 likely.
- **Cap-enforcement mechanism if needed**: today the cap is soft; if growth becomes problematic, a reviewer rule (R-GLOSSARY-CAP) could mechanically enforce. Defer until pain.
- **Periodic glossary audit**: per ADR-0011, `/audit-subagents` doesn't scan CLAUDE.md; a future `/audit-glossary` skill could be a sibling concern (out of scope here).

## References

- [ADR-0007](0007-vocabulary-glossary-and-grill-me-extension.md) — D1 (the decision being superseded); D2–D7 (preserved, see Extends header).
- [ADR-0004](0004-bypass-prevention.md) D2 — bootstrap-mode policy cited by D7.
- [ADR-0003](0003-autonomous-pipeline-with-critics.md) D8 — macro-ADR placement at grill→PRD boundary (this ADR ships alongside PRD #98).
- [ADR-0009](0009-discipline-tightening.md) D3/D4 — default-BLOCK + paranoid mindsets preserved on glossary-critic per D4 above.
- [ADR-0011](0011-subagent-quality-framework.md) — sibling concern: mechanical/grep-only rubric philosophy aligns with this ADR's D2 numeric threshold.
- `GLOSSARY.md` — the file being deleted.
- `CLAUDE.md` — the file absorbing the merged glossary.
- `.claude/skills/glossary-add/SKILL.md` — the skill being simplified (D3).
- `.claude/agents/glossary-critic.md` — the critic whose rubric is updated (D4).
- Backlog #98 (the captured item this PRD was synthesized from; closed when PRD #98 ships).
