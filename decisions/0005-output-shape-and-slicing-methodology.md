---
id: ADR-0005
status: accepted
supersedes: []
superseded_by: []
scope: slicing
rule_ids:
  - SLI-001
  - SLI-002
  - SLI-003
---
# ADR-0005: Output-shape standard for subagents + slicing methodology depth

- **Status:** Accepted (drafted by `/to-prd` alongside PRD-A; reviewed jointly by `prd-critic` and `adr-critic` per ADR-0004 D1)
- **Date:** 2026-05-14
- **Extends:** ADR-0003 D2 (refines critic-loop output shape into a canonical template); ADR-0003 D6 (skill/subagent allocation unchanged; shape standard now applies)
- **Supersedes:** none
- **Decided in:** Grill session "PRD-A from ADR-0004 backlog" (2026-05-14)

---

## Context

PRD #3 shipped the 5-stage autonomous pipeline with 5 subagents emitting structured outputs. PRD #15 added `adr-critic` (a 6th subagent on the same critic pattern). Across these 5 subagents (`reviewer`, `prd-critic`, `adr-critic`, `slicer`, `slicer-critic`) and 2 output-emitting skills (`qa-plan`, `ship`), three drift problems are now visible:

1. **Critic verdict bodies diverge.** `prd-critic` has an "Understood PRD intent" section that `reviewer` lacks. `slicer-critic` has a scoring matrix unique to it. Recommendation sections exist in some critics and not others. The drift is small per file but compounding — by the time `implementer` ships (deferred to its own PRD), there's no canonical reference for what a critic's body looks like.

2. **Return-value trailer field names diverge.** `reviewer` emits `VERDICT / REASON / COMMENT_URL / MERGE_STATUS`. `prd-critic` and `adr-critic` emit `VERDICT / REASON / ROUND / FAILED_RULES / FINDINGS_COUNT`. `qa-plan` emits `QA_PLAN_URL / COVERAGE_GAPS / RECOMMENDATION` — same semantic role (machine-parseable return) but different field names. `/ship` reads these trailers programmatically; cross-agent interop requires a shared schema.

3. **`slicer` doesn't internalize slicing methodology.** It asks for N=3 decompositions with INVEST tags and walking-skeleton flag, but the *methodology* — SPIDR vocabulary for splits, hamburger method for verticalization, Lawrence's story-splitting flowchart — lives only in the model's general knowledge. The `slicer-critic` has a "SPIDR splitability" rubric check but the *generator* doesn't internalize the same vocabulary. Result: the critic catches bad splits after the fact, not the generator avoiding them up front.

A small secondary problem visible from PRD-B's run: **the README is stale relative to current workflow state.** No agent currently has a responsibility to identify "files that should be updated to reflect the new feature, even when not strictly required by acceptance criteria." Cascade-docs drift.

ADR-0005 records the architectural response to all three drift problems plus the cascade-doc gap.

---

## Decisions

### D1: Canonical output-shape standard

A new section in `CLAUDE.md` titled **"Output-shape standard for subagents and output-emitting skills"** defines the canonical shape. It contains three sub-specifications:

**(a) Verdict template (required for the 4 critics — `reviewer`, `prd-critic`, `adr-critic`, `slicer-critic`).** The critic's emitted output body has 5 required sections, in order:

```
## <critic-name> verdict: [APPROVE | BLOCK] (round N/3)

### Subject of review
<2–4 sentences. What is being judged. The critic's restated spec contract.>

### Rubric
<Each criterion: [PASS/FAIL] + reason. Per-rule line items; numbered.>

### Findings (if BLOCK)
<Itemized, mechanically-actionable. Rule + section + diagnosis + concrete fix.
On APPROVE: "None.">

### Summary
<One paragraph. The synthesis the human reads first.>

<CRITIC trailer>
```

Permitted critic-specific extensions (appended *after* Summary, *before* the trailer): Recommendations (non-blocking), Scoring matrix (for multi-option critics like `slicer-critic`), Tiebreak path, Final approved output, Merge status. Extensions are explicitly named in the critic's own body file; this template doesn't enumerate them.

**(b) CRITIC trailer (required for the 4 critics).** Fenced code block at end of verdict output:

```
VERDICT: APPROVE | BLOCK
REASON: <one sentence>
ROUND: <N>/<max>
# On BLOCK additionally:
FAILED_RULES: <comma-separated rule identifiers>
FINDINGS_COUNT: <integer>
# On round-max BLOCK additionally:
ESCALATE: needs-human
```

**(c) GENERATOR trailer (required for `slicer`, `qa-plan`, `ship`; and for the "Final approved decomposition" output of `slicer-critic`).** Fenced code block at end of generator output:

```
RESULT: SUCCESS | STOPPED | INVALID_INPUT
REASON: <one sentence>
ARTIFACTS: <URLs or paths the agent produced, comma-separated>
# Per-agent extensions (e.g., COVERAGE_GAPS for qa-plan, SLICE_COUNT for slicer) follow ARTIFACTS
```

Generator output **bodies** are NOT standardized — each generator's body shape serves its domain (decompositions for `slicer`, test plans for `qa-plan`, chain reports for `ship`). Only the trailer is canonical.

Rationale for the body-vs-trailer split (per grill 3C): critic bodies have actual cross-agent drift; generator bodies legitimately differ in domain function. Forcing one generator-body template would over-engineer for marginal benefit.

### D2: Slicing methodology canonical location

The slicing methodology is canonically split across **two locations**:

**(a) `CLAUDE.md` "Slicing logic" section** gets a brief overview (5–10 lines): names hamburger method as the vertical-slice principle (slice 1 cuts through all layers), names SPIDR vocabulary (Spike / Path / Interface / Data / Rules) for split-fallback hints, notes that **S / I / R are the most applicable to our agent-workflow domain** (Path and Data don't map well — no end-user paths in agent infra; no rich data variation), references Lawrence's story-splitting flowchart externally without inlining.

**(b) `.claude/agents/slicer.md`** gets the actionable application checks:
- Explicit hamburger-vertical check for slice 1 generation (slice 1 must touch every layer, even if crudely)
- SPIDR vocabulary applied as split-fallback hints when any slice approaches the LoC cap (focus on S/I/R)
- (See D3 below for the cascade-doc check responsibility)

The split is intentional: CLAUDE.md is reference (cross-agent visibility); `slicer.md` is operational (the generator needs the methodology inline during generation). This matches the I4 LoC-cap pattern from PRD-B (canonical in `reviewer.md`, cross-ref in CLAUDE.md).

### D3: Cascade-doc check as formal slicer responsibility

The `slicer` subagent's prompt is extended with an explicit check during decomposition generation:

> **For each candidate decomposition**, identify files that *should* be updated to reflect the new feature even when not strictly required by the PRD's §2 acceptance criteria. These are "cascade-docs" — documentation that drifts out of sync if not actively updated. Examples: `README.md` if the feature changes the user-facing workflow; CLAUDE.md Map rows if the feature adds a new artifact; ADR index rows if the feature adds a new ADR. **Add a slice (or merge into an existing slice) to cover each identified cascade-doc.** When no cascade-docs are identified, state so explicitly in the decomposition's cross-decomposition summary.

The `slicer-critic`'s rubric is extended with a corresponding check: "Cascade-docs identified and covered." Rejection on FAIL is at the critic's discretion (this is a WARN if minor cascade-docs are missing; FAIL if a load-bearing doc — README, CLAUDE.md — is left to drift).

Rationale: the cascade-doc gap is a generation-time problem (the slicer either sees it or doesn't). Adding it as a critic-only check would catch it after generation; making it a generator responsibility prevents it.

### D4 (bootstrap): Bootstrap-mode acknowledgment for D1 and D3 enforcement

D1 (canonical templates the critics + generators conform to) and D3 (new `slicer-critic` cascade-doc rubric check) are **new enforcement mechanisms**. Per **ADR-0004 D2 bootstrap-mode policy**, each applies *forward from the moment the slice that ships it merges*; earlier slices of PRD-A are grandfathered.

Specifically:

- **D1 (canonical templates):** apply to a subagent / skill file from the moment its alignment slice merges. Slice 1 ships the spec + aligns `prd-critic.md` as the exemplar — after slice 1, `prd-critic.md` is canonical and any future PR touching it must preserve the canonical structure. Subsequent slices align the remaining 6 artifacts (`reviewer`, `adr-critic`, `slicer-critic`, `slicer`, `qa-plan`, `ship`) — each gains canonical status at its respective merge. PRD-A's own implementation slices that precede a given file's alignment slice are not bound by D1 for that file.
- **D3 (cascade-doc rubric on `slicer-critic`):** applies to slicer runs from the moment the `slicer.md` / `slicer-critic.md` alignment slice merges. Earlier PRD-A slices (e.g., the walking-skeleton slice that drafts ADR-0005 itself) ran before the cascade-doc rubric existed and are not subject to it.
- **From PRD-A merge forward:** all future PRDs satisfy D1 (subagent/skill files conform to canonical templates) and D3 (slicer identifies cascade-docs) from slice 1. The bootstrap exemption ends with PRD-A's last slice merging, exactly as ADR-0004 D2 prescribes — one-way, one-time per mechanism.

D5 (post-PRD audit stage + per-PR boy-scout-rule deferral, below) does not introduce enforcement; ADR-0004 D2 does not apply to that decision.

### D5: Post-PRD audit stage and per-PR boy-scout-rule both deferred

Two mechanisms surfaced in the grill that PRD-A explicitly does NOT ship:

**(a) Post-PRD audit stage.** A new pipeline stage between final-slice-merge and qa-plan, where an `auditor` subagent (or `/simplify` skill, already installed at user-scope) reviews the post-PRD codebase state for cumulative improvements — DRY opportunities across slices, stale references, logic improvements suggested by the new feature.

**(b) Per-PR boy-scout-rule inside `implementer` prompt.** An extension to the (deferred) `implementer` subagent's prompt: after acceptance criteria are met, scan diff for local simplification before opening PR.

Both are deferred to a separate future PRD (provisionally **PRD-C**). Rationale for deferral: each is a real new pipeline mechanism (new subagent, new stage, new behavior) that warrants its own grill session to settle scope, rubric, and integration points. Bundling either into PRD-A would balloon scope and mix themes (output-shape standardization is about *form*; audit/refactor is about *content quality*).

**Backlog-seed for PRD-C:** both mechanisms are captured here as ADR-0005 D5 (this decision); PRD-C's grill will resolve where the audit stage lives (post-merge stage vs in-reviewer-loop vs new orchestrator), the audit rubric, and whether the boy-scout-rule is co-shipped or grilled separately.

---

## Consequences

### Positive

- **Cross-agent interop preserved.** With the canonical CRITIC and GENERATOR trailers, `/ship` and future orchestrators can consume any agent's return-value via a shared schema. No per-agent parser logic needed.
- **Critic bodies converge.** The 5-required-section verdict template eliminates the body drift that was visible across `reviewer`, `prd-critic`, `adr-critic`, `slicer-critic`. Future critics (including any post-PRD-C audit critic) inherit the shape.
- **Slicer internalizes methodology.** Hamburger explicit check + SPIDR vocabulary inline means bad splits are avoided at generation, not retroactively caught by the critic. Lower iteration cost.
- **Cascade-docs stop drifting.** The slicer responsibility for cascade-doc identification is preventive. README and CLAUDE.md staleness becomes a slicer-critic failure mode rather than a discovered-too-late symptom.
- **ADR-0005 itself ships through the joint critic gate** (`prd-critic` + `adr-critic`). First real test of PRD-B slice 4's joint-APPROVE gate.

### Negative / accepted trade-offs

- **Audit work is large.** Full retroactive alignment of 7 in-scope files plus CLAUDE.md + README + ADR-0005 = ~10 file edits. Bigger PRD than PRD-B. Mitigation: most edits are mechanical section-renames + trailer-field-renames; SPIDR-split fallback documented in PRD §6 OQ#3 if any slice exceeds cap.
- **Two trailer types is a tiny cognitive cost.** Agents that read critic outputs use CRITIC trailer fields; agents that read generator outputs use GENERATOR trailer fields. Mitigation: each agent only ever reads one type; the split is along the same lines as the natural critic/generator distinction.
- **SPIDR's Path and Data techniques are explicitly excluded.** A future feature that *does* benefit from Path or Data splits (e.g., an agent with user-facing workflow paths) would need to re-add them to `slicer.md`. Mitigation: deferred not rejected; CLAUDE.md notes the exclusion is domain-fit, not principled.
- **Lawrence's flowchart is external-reference-only.** A user reading `slicer.md` who wants the full flowchart must click through. Mitigation: it's a one-page reference; inlining would bloat `slicer.md` by ~200 lines for marginal benefit.
- **`reviewer.md`'s verdict-vs-trailer split (per PRD-A §6 OQ#1) is genuinely open.** Two interpretations are both acceptable. The implementer picks one and documents in `reviewer.md` body.

---

## Alternatives considered

### Alt-A: JSON-schema or Pydantic validation
Rejected per grill 1A. LLMs are unreliable at strict JSON; the validation infra is not justified for a markdown-only repo with no runtime code; the standard is documented in markdown templates instead. LLM-native pattern; matches Anthropic's own guidance for natural-language outputs.

### Alt-B: One unified template for both critics and generators
Rejected per grill 3C/4A. Critics and generators serve fundamentally different semantics (judging vs producing). Forcing one template adds empty/N/A sections per agent and over-engineers for marginal interop benefit.

### Alt-C: One unified trailer type
Rejected per grill 5A. Same logic as Alt-B — judgment trailers (`VERDICT`) and generator trailers (`RESULT`) have different semantic flavors. Each trailer's required fields are right for its members; forcing one trailer adds N/A fields.

### Alt-D: Forward-only standardization (no retroactive audit)
Rejected per grill 7A. Shipping the "output-shape standardization" PRD without applying the standard to the existing artifacts is performative — the standard exists but is unenforced on day one. Full audit is the right precedent.

### Alt-E: Forward-only + R-SHAPE reviewer rule for future drift detection
Rejected per grill 7D. Adds yet another reviewer rule (R-LOC, R-CLOSES, R-META, R-SHAPE — getting crowded). Heuristic shape-detection via grep is fragile (false positives/negatives). Full audit + ordinary review of future subagent-touching PRs is mechanically sufficient.

### Alt-F: Bundle cascade-doc check into the `to-prd` skill (PRD authoring time, not slicing time)
Considered. Rejected — by PRD-authoring time, the cascade-doc question is "what *will* drift if this PRD ships" which is hard to answer before knowing the slice list. Slicer is where the decomposition exists; cascade-docs are slices of their own. Slicer is the right responsibility holder.

### Alt-G: Inline Lawrence's full story-splitting flowchart in `slicer.md`
Rejected per grill 6C. ~200 LoC of methodology textbook content; bloats `slicer.md` significantly; external link suffices.

### Alt-H: Skip Item 4 (slicing methodology depth) entirely; ship Item 1 only
Considered. Rejected — Item 4 is small in delta (a CLAUDE.md section expansion + slicer.md additions; ~80-100 LoC total). The combined PRD-A maintains theme coherence (both items are about "polishing the generated outputs" — Item 1 polishes critic outputs; Item 4 polishes slicer's). Bundling is right-sized.

### Alt-I: Defer cascade-doc check to PRD-C alongside the audit stage
Considered. Rejected — cascade-doc is preventive (slicer responsibility, applies at generation); audit stage is corrective (reviews after the fact). They're complementary but distinct; cascade-doc fits naturally in PRD-A's slicer-methodology scope.

### Alt-J: Bundle the audit stage (concern 2) and per-PR boy-scout-rule into PRD-A
Considered. Rejected per grill 8C. Two distinct themes (output-shape vs codebase-audit); PRD-A balloons; the audit stage needs its own design grill. PRD-C cleanly handles both.

---

## Open questions deferred

| Question | Deferred to |
|---|---|
| Whether the post-PRD audit stage uses an `auditor` subagent, wires `/simplify` against cumulative diff, or extends `qa-plan` | PRD-C grill |
| Whether the per-PR boy-scout-rule lives in `implementer` prompt, in a new pre-merge skill, or in reviewer's Recommendations section | PRD-C grill |
| Whether `reviewer.md`'s verdict-comment and return-block are two parallel canonical instances or one canonical + a derived summary | Slice implementation; document choice inline in `reviewer.md` |
| Whether SPIDR's Path and Data techniques should re-enter `slicer.md` when/if a future feature has end-user workflow paths or rich data variation | Reopen if/when such a feature arises |
| Whether `ship`'s terminal report content beyond the canonical trailer should be templated or stay free-form narrative | Slice implementation; recommend free-form narrative + canonical trailer |
| Whether retroactive `adr-critic` passes against ADR-0001 and ADR-0002 should ship (deferred from ADR-0004 Future direction) | Independent of PRD-A; possibly a small follow-up issue |
| Whether ADR-0003 should retroactively gain a `Future direction` line pointing to ADR-0005 — currently rejected by immutability rule | No — leave ADR-0003 untouched; readers see ADR-0005 via the `decisions/` index |

---

## Future direction

- **PRD-C** — post-PRD audit stage + per-PR boy-scout-rule. Resolves concern 2 from the PRD-A grill. Likely shape: new pipeline stage between final-slice-merge and qa-plan; reviews cumulative diff for DRY/staleness/logic-improvement opportunities; proposed changes become trivial-lane PRs or get bundled into a final cleanup slice. Per-PR boy-scout-rule may or may not co-ship.
- **`implementer` subagent build** — separate future PRD; the 5th stage of ADR-0003 D2's pipeline becomes runtime. Output-shape standard from ADR-0005 D1 applies on day one to implementer.
- **Branch protection R3 + R4 + bot identity + CI/Actions** — separate future PRD bundling the four together (they're co-dependent: R3 needs bot identity to satisfy "can't approve own PR"; R4 needs CI infra; both together close the API-level bypass gap acknowledged in ADR-0004).
- **Ensemble critics at every stage** — already framed as future direction in ADR-0003 and ADR-0002. ADR-0005's canonical templates make ensemble runs straightforward: N parallel critics emit conformant verdicts; an aggregator subagent reads trailers to compute unanimous/split.

---

## References

- [ADR-0001](0001-foundational-design.md) — foundational design; agent topology (D6) which this ADR extends
- [ADR-0002](0002-autonomous-merge-policy.md) — `reviewer` subagent; its verdict shape is now standardized by D1
- [ADR-0003](0003-autonomous-pipeline-with-critics.md) — extended by this ADR (D2 critic-loop pattern refined into canonical template; D6 skill/subagent allocation unchanged)
- [ADR-0004](0004-bypass-prevention.md) — `adr-critic` exists per D1; this ADR is the first one drafted with `adr-critic` in the joint-APPROVE gate
- [`decisions/README.md`](README.md) — ADR conventions; immutability invariant; "When to write an ADR" heuristic
- PRD-A issue (TBD — to be created by `/to-prd` after this ADR is jointly approved with PRD-A by `prd-critic` and `adr-critic`)
- Grill session "PRD-A from ADR-0004 backlog" — 2026-05-14 (this conversation)
- Slicing methodology external references: Mike Cohn — SPIDR; Gojko Adzic — hamburger method; Richard Lawrence — story-splitting flowchart
