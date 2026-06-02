# ADR-0045: ADR-citation consult discipline + systematized adr-critic D-ID verification

- **Status:** Accepted
- **Date:** 2026-06-02
- **Extends / honors (additive — no prior decision is overridden, so no `Supersedes:` header):** [ADR-0004](0004-bypass-prevention.md) D1 (the adr-critic rubric this ADR refines the *application shape* of, without adding a criterion) + D2 (bootstrap-mode policy), [ADR-0011](0011-subagent-quality-framework.md) (the subagent-quality framework the adr-critic's rubric lives in — unchanged), [ADR-0043](0043-claude-md-restructure.md) D1 (CLAUDE.md's four-section structure + rule-numbers-as-stable-anchors — the new rule takes the next free anchor #18) + D4 (the precedent for adding numbered cross-cutting rules ≥#16), [ADR-0042](0042-github-actions-ci-gate-r4.md) D1 (the CI gate `tools/ci-checks.sh` whose CHECK 6 ships the complementary *mechanical* half), [ADR-0017](0017-audit-meta-consolidation.md) (the DOCS-7 dangling-link/allowlist mechanic CHECK 6 mirrors), [ADR-0008](0008-workflow-autolog-bootstrap-and-naming.md) D7 (6-critic cap — honored; no new critic, no 7th AC criterion).

## Context

Agents drafting ADRs and PRDs from memory cite ADR decision-IDs (`ADR-NNNN D<n>`) that **exist but mean something else** — the **misattribution** class (backlog [#206](https://github.com/vojtech-stas/issues/206), consolidated under [#502](https://github.com/vojtech-stas/issues/502)). The `adr-critic`'s `AC-SUPERSEDES-BY-D-ID` criterion already substance-matches cited D-IDs and caught this class **three times in a single session (2026-06-02)** — ADR-0040 (ADR-0020 D10 mischaracterized), ADR-0041 (the `git --git-common-dir` idiom miscited to ADR-0016/0040), ADR-0042 (ADR-0008 D6's own R3/R4 reversal undisclosed) — but **each catch costs a BLOCK round**, and earlier instances (#489/#497) shipped to `main` before being caught (e.g. "ADR-0001 D8" cited for immutability when D8 is "Orientation artifacts").

[ADR-0042](0042-github-actions-ci-gate-r4.md)'s CI gate gained **CHECK 6** (shipped via PR #505) which mechanically catches **dangling** D-IDs (a cited `D<n>` with no matching `### D<n>` heading). But **misattribution** — the cited D-ID *exists*, its meaning is wrong — a mechanical grep **cannot** judge; only reading the heading text and judging the characterization can.

Two gaps remained after CHECK 6:
1. **No pre-emptive discipline** tells a drafting agent to *read the actual heading before citing*. CLAUDE.md's Map row for `decisions/` points only at `decisions/NNNN-*.md` files ("immutable; supersede rather than edit") and never names `decisions/README.md` as the **index** an agent should consult to find the right ADR + D-ID.
2. **The adr-critic's verification is ad-hoc.** `AC-SUPERSEDES-BY-D-ID` substance-matches, but applies the check opportunistically rather than as a systematic per-cite enumeration of *every* `ADR-NNNN D<n>` reference in the draft.

Grill (2026-06-02, Q1–Q4 — surfaced while grilling [#62](https://github.com/vojtech-stas/issues/62)) resolved: **add a pre-emptive consult discipline (a numbered CLAUDE.md rule + a Map index pointer) and lightly systematize the existing adr-critic check into an explicit per-cite citation-ledger pre-step — no new AC criterion, no new mechanical ci-check (a grep can't judge meaning).**

## Decisions

### D1: New CLAUDE.md cross-cutting rule #18 — never cite an ADR decision-ID from memory

CLAUDE.md §1 (Cross-cutting constraints) gains **rule #18**: *before citing `ADR-NNNN D<n>` in any drafted ADR / PRD / doc, open the cited ADR and read the actual `### D<n>` heading — the citation's characterization must match that heading's text; `decisions/README.md` is the decision index, consult it to find the right ADR.* The body is a **one-line behavioral constraint + the ADR-0045 citation**, per [ADR-0043](0043-claude-md-restructure.md) D1's body-trim discipline (the mechanism lives here, not in CLAUDE.md). `#18` is the next free stable anchor — past `#17`, with `#14` retired — so no existing rule-number reference shifts ([ADR-0043](0043-claude-md-restructure.md) D1 numbers-as-anchors invariant + D4 add-new-numbered-rule precedent).

### D2: The CLAUDE.md Map names `decisions/README.md` as the decision index

CLAUDE.md §4 (Map) is strengthened so the `decisions/` entry **names `decisions/README.md` as the index to consult before citing a D-ID** — closing the gap that the Map pointed only at the immutable `decisions/NNNN-*.md` files and never at the index that lists every ADR + its decision summaries. This is the discoverability half of the consult discipline: rule #18 states the constraint, the Map tells the agent *where the index lives*.

### D3: The adr-critic's D-ID verification is systematized into an explicit per-cite citation-ledger pre-step (refines AC-SUPERSEDES-BY-D-ID's application; adds no criterion)

`.claude/agents/adr-critic.md` gains a **mandatory citation-ledger pre-step**: before applying the 6-criterion rubric, the critic **enumerates every `ADR-NNNN D<n>` citation across all sections of the draft** (not only `Supersedes:` / `Extends:` headers) into a ledger, reads each cited heading via `gh api` (origin/main, per the existing stale-worktree mitigation), and records *exists* + *substance-match* per row. The ledger **feeds the existing `AC-SUPERSEDES-BY-D-ID` and `AC-CROSS-ADR-CONSISTENCY` criteria**, making the per-cite verification **exhaustive-by-construction** rather than opportunistic. This **refines the application shape** of the rubric defined under [ADR-0004](0004-bypass-prevention.md) D1; it does **NOT add a 7th AC criterion** (the rubric stays exactly six: `AC-CONVENTION-COMPLIANCE`, `AC-CROSS-ADR-CONSISTENCY`, `AC-SUPERSEDES-BY-D-ID`, `AC-NO-SCOPE-CREEP`, `AC-BOOTSTRAP-MODE-ACKNOWLEDGED`, `AC-IMMUTABILITY-RESPECTED`) and does **NOT** weaken any of them.

### D4: Division of labor recorded — mechanical vs LLM vs pre-emption

Three complementary, non-overlapping layers now defend the D-ID-citation surface:
- **Mechanical (CHECK 6, [ADR-0042](0042-github-actions-ci-gate-r4.md) D1's `tools/ci-checks.sh`):** catches **dangling** D-IDs (cited `D<n>` with no matching `### D<n>` heading) deterministically at CI time.
- **LLM judgment (the adr-critic, D3):** catches **misattribution** (cited D-ID exists, characterization wrong) — a grep cannot judge meaning, so misattribution stays adr-critic-only; **no new mechanical ci-check is added**.
- **Pre-emption (rule #18 + the Map index pointer, D1/D2):** stops both classes at *draft* time, before either gate fires.

### D5: Bootstrap-mode (per [ADR-0004](0004-bypass-prevention.md) D2)

Binds forward from merge. Rule #18 and the systematized adr-critic ledger apply to ADRs / PRDs drafted from this ADR's ship slice onward. Existing ADRs are grandfathered — their historical citations are not retroactively swept (the immutable record stands; CHECK 6's baseline allowlist already handles any historical dangling refs). No retroactive ADR edits.

## Consequences

**Positive:**
- Pre-empts the D-ID-drift class at draft time (it cost three adr-critic BLOCK rounds in one session; #489/#497 shipped before catch).
- Makes `decisions/README.md` discoverable as the decision index from the most-read file (CLAUDE.md), instead of being an unadvertised convention.
- The adr-critic's verification becomes exhaustive-by-construction (a ledger over *every* cite), not opportunistic — fewer misattributions slip past round 1.
- Closes #502's misattribution half (#206); together with CHECK 6 (dangling half) the consolidation is fully addressed.

**Negative:**
- Adds one more cross-cutting rule to the most-read file. Mitigated: one line + citation, per [ADR-0043](0043-claude-md-restructure.md) D1's trim discipline.
- The citation-ledger pre-step adds a small amount of adr-critic work per ADR. Mitigated: it is the verification the critic *should already* perform under `AC-SUPERSEDES-BY-D-ID`; D3 only makes it structured and complete.

**Neutral:**
- No new critic (6-critic cap honored, [ADR-0008](0008-workflow-autolog-bootstrap-and-naming.md) D7), no 7th AC criterion, no new mechanical ci-check, no new dependency. Runtime touch: `.claude/agents/adr-critic.md` + `CLAUDE.md`. `decisions/0045-*.md` + `decisions/README.md` record it.

## Alternatives considered

- **Alt-A (chosen): consult discipline (rule #18 + Map index pointer) + systematize the existing adr-critic check.** Pre-empts at draft time and tightens the gate without inflating the rubric.
- **Alt-B: add a mechanical ci-check for misattribution.** Rejected (Q1): a grep cannot judge whether a cited D-ID's *meaning* matches the heading; CHECK 6 already covers the mechanically-decidable (dangling) half. A "misattribution check" that can't decide misattribution is theater.
- **Alt-C: add a 7th AC criterion (`AC-DID-SUBSTANCE`).** Rejected (Q1): `AC-SUPERSEDES-BY-D-ID` already substance-matches; a new criterion duplicates it and pressures the rubric-count discipline. Systematize the existing criterion's application instead.
- **Alt-D: Map index pointer only, no numbered rule.** Rejected (Q2): a Map note is descriptive prose; the load-bearing constraint belongs in the numbered cross-cutting rules where agents weight it — the exact [ADR-0043](0043-claude-md-restructure.md) D4 lesson (slice-decomposition ownership was bypassed *because* it sat in prose).
- **Alt-E: inject a pre-draft "read decisions/README" mechanical step into the `/to-prd` ADR-drafting path.** Deferred (not rejected): the numbered rule + the critic ledger cover the need; a skill-path step is YAGNI now. Revisit if misattribution recurs post-merge.

## References

- Grill 2026-06-02 Q1–Q4 (the ADR-consistency forks, surfaced while grilling [#62](https://github.com/vojtech-stas/issues/62)). Backlog [#502](https://github.com/vojtech-stas/issues/502) (the D-ID-drift consolidation — dangling half shipped via CHECK 6 / PR #505; this ADR ships the misattribution half, [#206](https://github.com/vojtech-stas/issues/206)). Session evidence: adr-critic BLOCK rounds on ADR-0040 / ADR-0041 / ADR-0042; #489/#497 (shipped before catch).
- [ADR-0004](0004-bypass-prevention.md) D1 (adr-critic rubric — application refined, not superseded) + D2 (bootstrap-mode). [ADR-0011](0011-subagent-quality-framework.md) (subagent-quality framework). [ADR-0043](0043-claude-md-restructure.md) D1 (four-section structure + numbers-as-anchors) + D4 (numbered-rule-add precedent). [ADR-0042](0042-github-actions-ci-gate-r4.md) D1 (CI gate / CHECK 6 home). [ADR-0017](0017-audit-meta-consolidation.md) (DOCS-7 dangling-link/allowlist precedent CHECK 6 mirrors). [ADR-0008](0008-workflow-autolog-bootstrap-and-naming.md) D7 (6-critic cap). `decisions/README.md` (immutability + index conventions).
- `.claude/agents/adr-critic.md`, `CLAUDE.md`.
