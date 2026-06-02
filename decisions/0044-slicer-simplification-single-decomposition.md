# ADR-0044: Slicer simplification — single decomposition + critic-iterate (retire N=3 batch)

- **Status:** Accepted
- **Date:** 2026-06-02
- **Supersedes:** [ADR-0003](0003-autonomous-pipeline-with-critics.md) D3 (the "Multi-option exploration at the slicer stage (N=3)" lock — the slicer no longer generates three alternative decompositions) + [ADR-0013](0013-slicer-n3-contract-refined.md) D1/D2/D3/D4 (the degenerate-N=1 detection + N-value machinery — vacuous once the slicer always produces exactly one decomposition; ADR-0013 D5 cascade-docs + D6 bootstrap-mode are housekeeping, untouched).
- **Extends / honors:** [ADR-0005](0005-output-shape-and-slicing-methodology.md) D2 (slicing-methodology canonical location — preserved; `slicer.md` stays the home of the SPIDR/hamburger/walking-skeleton methodology, only the N-default changes) + [ADR-0005](0005-output-shape-and-slicing-methodology.md) D3 (cascade-doc check as a formal slicer responsibility — preserved; unaffected by this simplification), [ADR-0011](0011-subagent-quality-framework.md) (the critic-rubric framework the slicer-critic keeps), [ADR-0008](0008-workflow-autolog-bootstrap-and-naming.md) D7 (6-critic cap — honored; no new/removed critic, slicer-critic stays), [ADR-0004](0004-bypass-prevention.md) D2 (bootstrap-mode).

## Context

[ADR-0003](0003-autonomous-pipeline-with-critics.md) D3 locked **N=3** at the slicer: the slicer generates three alternative decompositions, the slicer-critic scores all three and picks the best, then iterates on the chosen one. [ADR-0013](0013-slicer-n3-contract-refined.md) then refined it with a degenerate-N=1 carveout (D1–D4) for cases where the three alternatives would be bit-identical.

The premise was that N=3 surfaces genuine design diversity. In practice it does not: all three alternatives come from **one agent context with shared assumptions**, so the "diversity" is bounded — what actually varies is **execution shape** (slice count, seam placement, bundling, commit ordering), not design. The original observation (user, 2026-05-16: *"how is it better than just asking one slicer to create 3 options?"*) was confirmed empirically across **five N=3 runs in a single session (2026-06-02: PRDs #479, #485, #488, #496, #503)**:
- the three alternatives were consistently execution-shape variation, not deep design exploration;
- on atomic PRDs (#503 CHECK-6, #496 CLAUDE.md restructure) the slicer padded to three and the critic collapsed to degenerate-N=1 — pure ceremony;
- the genuine value was the **slicer-critic's rubric scoring + pick + revision**, which does not require three inputs — a single well-prompted slicer plus the critic's iterate loop reaches the same decomposition with less overhead.

The slicer-critic is also the only critic running a bespoke best-of-N shape; the other four (prd, adr, glossary, backlog) use a single-artifact APPROVE/BLOCK iterate loop. Grill (2026-06-02, Q1–Q5) resolved: **simplify to Pattern B — one decomposition + perspective-prompting + the standard critic-iterate loop, keeping the slicer-critic's quality rubric.**

## Decisions

### D1: The slicer produces ONE decomposition (supersedes ADR-0003 D3)

`.claude/agents/slicer.md` is restructured: the slicer outputs a **single, well-justified decomposition** of the PRD. The prompt explicitly directs it to **weigh multiple internal perspectives** before committing — e.g. *minimize-slice-count* vs *front-load-risk* vs *minimize-churn* vs *walking-skeleton-first* — and to enumerate the **"alternatives considered"** inline as one line each (the trade-off it rejected and why), NOT as full drafts. The N=3-alternatives demand and the "three side-by-side decompositions" output are removed. The degenerate-N "detection" rule (ADR-0013 D1) is removed — there is no batch to collapse; the slicer simply produces the right decomposition (which may be one slice or several) with its rationale.

### D2: The slicer-critic scores the single decomposition with a standard iterate loop (supersedes ADR-0013 D1–D4)

`.claude/agents/slicer-critic.md` **keeps its full quality rubric** (INVEST, walking-skeleton, SPIDR-splitability, no-non-goals, no-rabbit-holes, dep-ordering, slice-count/LoC, risk-front-loading, cascade-docs-covered, cross-PR-collision) and applies it to the **one** decomposition it receives — but drops the **best-of-N machinery** (score-all-three, pick-the-best, tiebreak) and the **degenerate-N=1 verification** (ADR-0013 D2/D3). It becomes a standard **APPROVE / BLOCK + ≤3-round revision loop**, identical in shape to prd-critic / adr-critic / glossary-critic / backlog-critic. The rubric (the real quality bar) is unchanged; only the multi-candidate selection is removed.

### D3: Output shape — drop the N-batch trailer fields

The slicer emits one decomposition + a canonical GENERATOR trailer ([ADR-0005](0005-output-shape-and-slicing-methodology.md) D1c); the `DECOMPOSITION_COUNT` per-agent extension is dropped (always 1 — uninformative). The slicer-critic emits a canonical CRITIC trailer (VERDICT/REASON/ROUND); the scoring-matrix output is replaced by the standard verdict + findings.

### D4: `/to-issues` + `/ship` describe the single-decomposition shape

`.claude/skills/to-issues/SKILL.md` and `.claude/skills/ship/SKILL.md` drop their "N=3 block" / "three alternatives" references and describe the Pattern-B shape (slicer drafts one decomposition; slicer-critic iterates). No stale N=3 prose remains.

### D5: Revert trigger (the simplification is reversible by evidence)

Roll back to N=3 (or upgrade to a genuine **ensemble** of differently-prompted slicers, per the 2026-05-16 2B/2C analysis) if ANY of:
- **T1** — ≥2 PRDs where the single-output slicer commits to a decomposition that later proves wrong (mid-implementation rework, or a QA-caught shape problem, that a different decomposition the slicer didn't consider would have avoided);
- **T2** — ≥2 PRDs hitting slicer-critic round-3 persistent BLOCKs (single-output anchoring too strong);
- **T3** — direct user observation that decomposition quality degraded vs the pre-simplification baseline.

The PRD that revives N=3 / introduces an ensemble cites the fired trigger. This honors the pure-YAGNI principle (*"if it worsens the result we can always go back"*) with recorded, evidence-based criteria rather than re-litigation from memory.

### D6: Bootstrap-mode (per [ADR-0004](0004-bypass-prevention.md) D2)

Binds forward from merge. PRDs in flight at change time may be sliced under either pattern with no retroactive impact; the new shape applies to slicing from this ADR's slices onward.

## Consequences

**Positive:**
- Less overhead (one decomposition drafted, not three) for the same outcome — the session evidence shows the critic's pick+revision, not the batch, carried the value.
- The slicer-critic becomes the standard single-artifact iterate shape, so all five critics are consistent (one mental model).
- No more N=3 theater on atomic PRDs; the slicer just produces the right shape with rationale.
- The slicer-critic's quality rubric — the part that actually caught bad decompositions — is fully preserved.

**Negative:**
- Loses the "surface multiple options to explicitly reject" step. Mitigated by (a) the inline "alternatives considered" (D1) which keeps the reasoning visible, and (b) the D5 revert trigger.
- Single-output anchoring could in principle be stronger than batch exploration; T1/T2 are the tripwires.

**Neutral:**
- No new/removed critic (6-critic cap honored). Runtime touch: slicer.md, slicer-critic.md, to-issues + ship SKILLs. ADR-0013's degenerate-N machinery is retired (D1–D4); its D5/D6 housekeeping stand.

## Alternatives considered

- **Alt-A (chosen): Pattern B — single decomposition + perspective-prompting + critic-iterate, keep the rubric.**
- **Alt-B: keep N=3.** Rejected (Q1): five same-session runs showed execution-shape variation + atomic-PRD theater; ~3× drafting overhead; the only bespoke-shaped critic.
- **Alt-C: hybrid — single by default, N>1 when the slicer judges genuine diversity.** Rejected (Q1): a fuzzy "when is diversity genuine?" fork re-introduces the complexity; two code paths.
- **Alt-D: drop the slicer-critic rubric too (light holistic check).** Rejected (Q2): the rubric is the real quality bar (it caught #496's broken intermediate, #485's walking-skeleton fail); the N=3 batch and the rubric are independent — only the batch is the waste.
- **Alt-E: genuine ensemble (differently-prompted parallel slicers).** Deferred (not rejected): the D5 revert-path upgrade target if single-output proves too thin; YAGNI now.

## References

- Grill 2026-06-02 Q1–Q5. Backlog [#62](https://github.com/vojtech-stas/project-claude/issues/62) (the capture, with its original revert-trigger analysis). Empirical evidence: same-session N=3 runs on PRDs #479/#485/#488/#496/#503.
- [ADR-0003](0003-autonomous-pipeline-with-critics.md) D3 (superseded — N=3 lock). [ADR-0013](0013-slicer-n3-contract-refined.md) D1–D4 (superseded — degenerate-N machinery), D5/D6 (housekeeping, unchanged). [ADR-0005](0005-output-shape-and-slicing-methodology.md) D2 + D3 + D1c (slicing-methodology canonical location + cascade-doc slicer responsibility + GENERATOR trailer — all preserved). [ADR-0011](0011-subagent-quality-framework.md) (critic-rubric framework). [ADR-0008](0008-workflow-autolog-bootstrap-and-naming.md) D7 (6-critic cap). [ADR-0004](0004-bypass-prevention.md) D2 (bootstrap-mode).
- `.claude/agents/slicer.md`, `.claude/agents/slicer-critic.md`, `.claude/skills/to-issues/SKILL.md`, `.claude/skills/ship/SKILL.md`.
