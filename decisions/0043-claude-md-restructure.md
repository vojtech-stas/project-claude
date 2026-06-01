# ADR-0043: CLAUDE.md restructure — constraint-framed, grouped, de-duplicated (rules stay; numbers are anchors)

- **Status:** Accepted
- **Date:** 2026-06-01
- **Supersedes:** [ADR-0024](0024-root-cause-workflow-capture-discipline.md) D1's *placement* directive ("add cross-cutting rule #13 to CLAUDE.md" as a **standalone** rule) — rule #13 is **retained** (number kept as a stable anchor) but **co-located** with rule #11 under one "Capture discipline" heading with a de-duplicated body. ADR-0024 D2 (complementarity) + D3 (3-part body shape) are **unchanged**.
- **Extends / honors (presentation only — none of these decisions change):** [ADR-0006](0006-backlog-and-session-continuity.md) D4 + [ADR-0009](0009-discipline-tightening.md) D2 (capture-discipline, mandatory — restatement trimmed), [ADR-0008](0008-workflow-autolog-bootstrap-and-naming.md) D5 (descriptive backlog titles — moved into a Naming section, the codename-rationale essay trimmed), [ADR-0036](0036-worktree-isolation-all-dispatches.md) D1–D3 (parallel isolated dispatch — rule #8 corrected to match it), [ADR-0038](0038-skill-vs-agent-rule.md) D1 (skill-vs-subagent — promoted from a prose section to a numbered rule), [ADR-0013](0013-slicer-n3-contract-refined.md) (the slicer's decomposition contract — primary source for how-many-slices / where-boundaries-fall) + [ADR-0005](0005-output-shape-and-slicing-methodology.md) D3 (the slicer's cascade-doc-identification responsibility at decomposition time) — together the basis for promoting slice-decomposition ownership from Hierarchy prose to a numbered rule, [ADR-0037](0037-production-verification-gate.md) D1 (production-verify — rule #15 trimmed to a pointer), [ADR-0015](0015-claude-code-hooks-adoption.md) (hooks scope — rule #12 trimmed to a pointer). Honors [ADR-0008](0008-workflow-autolog-bootstrap-and-naming.md) D7 (no new critic) and the `decisions/README.md` ADR-immutability convention (the reason this is an ADR recording the change, not silent edits to prior ADRs).

## Context

CLAUDE.md is auto-loaded every session — it is the single most-read artifact in the project. Over ~43 ADRs it accreted: duplicated capture rules (#11 forward-work + #13 root-cause, each re-explaining the captured→backlog mechanism that already lives in ADR-0008 + the `promote-to-backlog` skill), explanatory essays inside behavioral rules (#12 hooks, the codename-title rationale), a stale rule (#8 "one thing at a time" — contradicted by [ADR-0036](0036-worktree-isolation-all-dispatches.md), which enables parallel independent slices), a load-bearing rule misfiled as descriptive prose (slice-decomposition ownership sat in the Hierarchy section, so agents — including the main agent — under-weighted it vs. the numbered rules), scattered naming conventions, and pure-noise sections ("Where to look for more"). The owner's review (2026-06-01) asked for a constraint-framed, grouped, de-duplicated rewrite where every rule has one home.

**The hard constraint that shapes the whole change:** the numbered rules are referenced **~180 times across ~30 files**, ~15 of them **immutable ADRs** (e.g., ADR-0024's entire subject is rule #13; #11/#13/#10 alone carry ~110 references). Renumbering would silently misdirect every one of those references. Therefore the rules **keep their existing numbers as stable anchors**; the restructure is grouping + body-trimming + presentational co-location, not renumbering. (Grill 2026-06-01, Q1–Q6.)

## Decisions

### D1: CLAUDE.md is reorganized into four sections; rule numbers are preserved as stable anchors

CLAUDE.md is restructured into: **(1) Cross-cutting constraints** (the numbered rules, constraint-voiced where natural), **(2) Naming** (commits, branches, issue titles, files — consolidated), **(3) Hierarchy + workflow conventions** (the 3-tier hierarchy with I1–I6 folded in, trimmed), **(4) Map + Glossary** (unchanged). Every existing rule **keeps its number** (`#1`…`#13`, `#15`; `#14` stays retired) so all ~180 references — including those in immutable ADRs — keep resolving. Numbers are anchors, not an ordered list; grouping (not numbering) provides the clean reading. Each rule body is trimmed to a one-line behavioral constraint plus its governing-ADR citation; the explanation lives in the ADR, not here (DRY, rule #9).

### D2: Rule #8 is corrected to match ADR-0036 (parallel work is allowed)

Rule #8's "One thing at a time / one in-progress todo" framing is **stale** — [ADR-0036](0036-worktree-isolation-all-dispatches.md) D1–D3 enable **parallel independent slice waves** via worktree isolation. Rule #8 is corrected to: *one PR per slice (1:1); independent slices may run in parallel; only dependent work serializes.* This reconciles a long-standing contradiction; the "one PR per slice" invariant is preserved.

### D3: Rules #11 and #13 are co-located under one "Capture discipline" heading (both numbers retained)

Rules #11 (capture forward/deferred work) and #13 (root-cause workflow capture) are **presented together** under a single "Capture discipline" subheading: both keep their numbers (anchors for their ~96 combined references), both bodies are de-duplicated (the captured→backlog mechanism is stated once and cited to [ADR-0008](0008-workflow-autolog-bootstrap-and-naming.md) + the `promote-to-backlog` skill, not re-explained in each). The two **shapes** stay distinct per [ADR-0024](0024-root-cause-workflow-capture-discipline.md) D2 (#11 = open forward-work; #13 = 3-part symptom/cause/proposed-fix). This is a presentation consolidation, not a discipline change. (Supersedes ADR-0024 D1's standalone-placement directive only.)

### D4: Two load-bearing rules are promoted from prose into the numbered cross-cutting constraints

(a) **Slice-decomposition ownership** ("how many slices / where boundaries fall / the walking-skeleton cut belong to the slicer + slicer-critic; the grill/PRD phase never decides slicing") moves from the descriptive Hierarchy section into the numbered rules — the owner observed it was bypassed precisely because it sat in prose, not in the binding rule list. Cites [ADR-0013](0013-slicer-n3-contract-refined.md) (decomposition contract — primary) + [ADR-0005](0005-output-shape-and-slicing-methodology.md) D3 (cascade-doc identification at decomposition time). (b) The **skill-vs-subagent litmus** ("only the main agent dispatches subagents; subagents never dispatch subagents") moves from a standalone prose section into a one-line numbered rule citing [ADR-0038](0038-skill-vs-agent-rule.md) D1. Both take new rule numbers (≥#16, continuing the sequence past the retired #14) so no existing anchor shifts.

### D5: Explanatory cruft is trimmed; the underlying decisions are untouched

Removed from CLAUDE.md (the decisions remain authoritative in their ADRs): the "Where to look for more" section (noise — discovery is the Map + ADR index); the codename-title **rationale essay** under the naming convention (decision stays as a one-line Naming rule citing [ADR-0008](0008-workflow-autolog-bootstrap-and-naming.md) D5; the 2026-05-16 #47/#57 cleanup detail is historical). Rule #7 ("practices colocated") is **demoted** from a behavioral rule to a one-line Map note (it states *where things live*, not *what not to do*). Rules #12 (hooks) and #15 (production-verify) are trimmed to one-line pointers — their enforcement is mechanical ([ADR-0015](0015-claude-code-hooks-adoption.md); `/build` step 5 + `/ship` step 6 per [ADR-0037](0037-production-verification-gate.md) D1), so CLAUDE.md needs only the constraint, not the mechanism. A **crosswalk** (former-rule-#N → new home) is recorded in §References below for any reader following an old reference.

### D6: Bootstrap-mode (per [ADR-0004](0004-bypass-prevention.md) D2)

Binds forward from merge. The live consumers (skills/agents) that reference reorganized rules are updated in the same change where they're mutable; immutable-ADR references become historical and resolve via this ADR's crosswalk. No retroactive ADR edits.

## Consequences

**Positive:**
- The most-read file in the project becomes a clean, grouped, constraint-framed list — easier for every agent (and human) to load and obey.
- One semantic bug fixed (rule #8 vs. parallel dispatch); one load-bearing rule made binding (slicing ownership was being bypassed *because* it was prose).
- Duplication removed (#11/#13 mechanism stated once); the decision-vs-restatement split is clean (CLAUDE.md = constraint, ADR = why).

**Negative:**
- Numbers stay non-sequential (anchors, not 1..N) — a cosmetic cost accepted to protect ~180 references.
- A reader of a superseded/old ADR following a co-located/demoted rule takes one hop through this ADR's crosswalk.

**Neutral:**
- No new critic, no new dependency, no discipline change. CLAUDE.md (runtime-adjacent) + the live skill/agent references update; `decisions/0043-*.md` + `decisions/README.md` record it.

## Alternatives considered

- **Alt-A (chosen):** keep numbers as anchors; group + trim + co-locate; ADR-0043 records it.
- **Alt-B: renumber to a clean 1..N + sweep all references.** Rejected (Q4): ~15 of the referencing files are immutable ADRs that can't be edited; renumbering silently misdirects ~180 references (incl. 96 to #11/#13). Self-defeating.
- **Alt-C: edit CLAUDE.md directly, no ADR.** Rejected (Q3): changing governance rules that ~12 ADRs cite is a governance change; the reviewer's R-ADR-CONFLICT would BLOCK a CLAUDE.md edit contradicting existing ADRs without a superseding ADR. Also silent governance drift.
- **Alt-D: move the rules out of CLAUDE.md into the ADR.** Rejected (Q3): CLAUDE.md is the auto-loaded surface agents read every session; the rules must live there. The ADR holds only the decision/why/crosswalk — no rule duplication (DRY).

## References

- Grill 2026-06-01 Q1–Q6 (number-stability / consolidation-ADR / co-locate-not-delete / defer-capture-skill / constraint-voice). Owner review 2026-06-01.
- **Crosswalk (former presentation → new home):** rule #13 → co-located with #11 under "Capture discipline" (both numbers retained); rule #7 → demoted to a Map note; the slice-decomposition rule → promoted from Hierarchy prose to numbered rule; the skill-vs-subagent litmus → promoted from a prose section to a numbered rule; the codename-title rationale essay → removed (decision = ADR-0008 D5, one-line Naming rule); "Where to look for more" → removed.
- [ADR-0024](0024-root-cause-workflow-capture-discipline.md) D1 (superseded — placement only), D2/D3 (unchanged). [ADR-0006](0006-backlog-and-session-continuity.md) D4 + [ADR-0009](0009-discipline-tightening.md) D2 (capture mandatory). [ADR-0008](0008-workflow-autolog-bootstrap-and-naming.md) D5 (naming) + D7 (cap). [ADR-0036](0036-worktree-isolation-all-dispatches.md) D1–D3 (parallel). [ADR-0038](0038-skill-vs-agent-rule.md) D1. [ADR-0013](0013-slicer-n3-contract-refined.md) + [ADR-0005](0005-output-shape-and-slicing-methodology.md) D3. [ADR-0037](0037-production-verification-gate.md) D1. [ADR-0015](0015-claude-code-hooks-adoption.md). The `decisions/README.md` ADR-immutability convention. [ADR-0004](0004-bypass-prevention.md) D2 (bootstrap-mode).
