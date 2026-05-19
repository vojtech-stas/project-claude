# ADR-0009: Discipline tightening — universal rule #10, mandatory rule #11, asymmetric-default-BLOCK + distinct mindsets across all critics

- **Status:** Accepted
- **Date:** 2026-05-19
- **Extends:** [ADR-0008](0008-workflow-autolog-bootstrap-and-naming.md) D2 (asymmetric-default-BLOCK pattern, generalized to all critics)
- **Supersedes:** [ADR-0004](0004-bypass-prevention.md) D4 (rule #10 scope: enumerated → universal); [ADR-0006](0006-backlog-and-session-continuity.md) D4 (rule #11 strength: discretionary → mandatory)

## Context

After 6 PRDs shipped end-to-end through the autonomous pipeline, the user reviewed the foundational `CLAUDE.md` template (which is also used as the starter for other projects) and surfaced 17 distinct concerns about the project's discipline, structure, and conventions. The grill on 2026-05-19 triaged the concerns into four themes — discipline-tightening, CLAUDE.md restructure, naming/terminology, workflow additions — and this PRD addresses the discipline-tightening theme exclusively (the other three themes are queued for subsequent sessions).

Three specific concerns drove this ADR:

1. **Rule #10 (main-agent meta-output discipline) is too narrow.** ADR-0004 D4 codified rule #10 with an enumerated list of paths (`decisions/`, `.claude/agents/`, `.claude/skills/`, `CLAUDE.md`, `README.md`). The enumeration has drifted as new tracked artifacts shipped: `GLOSSARY.md` (ADR-0007), `bootstrap.sh` (ADR-0008), `.githooks/*` (PRD-B), `decisions/branch-protection-config.json`. The 2026-05-16 trivial-lane PR for `branch-protection-config.json` reconciliation slipped through with no R-META check because the rule didn't enumerate that path. Every new artifact creates a fresh gap.

2. **Rule #11 (surface deferred work as backlog issues) is too soft.** ADR-0006 D4 made the surfacing convention discretionary — agents *should* capture deferred work. The autopilot mechanism (ADR-0008) added downstream quality filtering via `backlog-critic`, which means the original rationale for discretionary capture (avoid backlog noise) is now obsolete — noise is filtered by the critic, not by agent self-restraint at capture time. Discretionary capture now lets real items slip uncaptured.

3. **Critics are too lenient.** Across the 2026-05-16 session, every critic invocation APPROVED on round 1 — 7 PR-reviews, 2 PRD reviews, 2 ADR reviews, 3 autopilot runs (with one BLOCK from `backlog-critic` on #73's trivial-lane-sized case). Either the work was genuinely high-quality (probably partially true) or critics are systematically biased toward APPROVE (probably also partially true). The pattern needs tightening. `backlog-critic` already has an explicit asymmetric-default-BLOCK clause per ADR-0008 D2; the other 5 critics do not.

## Decisions

### D1: Rule #10 scope universal

The full rewritten rule reads:

> **Main-agent meta-output discipline.** Main agent never hand-authors ANY tracked file. All edits to tracked files flow through the PRD/slice/PR pipeline via `/to-prd`, `/to-issues`, `/ship`, an implementer Agent invocation, the trivial-lane (I3) workflow, or any other reviewer-gated PR channel.

The universal scope subsumes all current tracked artifacts (`decisions/*`, `.claude/agents/*`, `.claude/skills/*`, `CLAUDE.md`, `README.md`, `GLOSSARY.md`, `bootstrap.sh`, `.githooks/*`, `decisions/branch-protection-config.json`, `LICENSE`, `.gitignore`, `.gitattributes`, etc.) and any future tracked artifact without enumeration drift.

The list of valid pipeline channels is non-exhaustive (note the trailing "or any other reviewer-gated PR channel") so new channels (e.g., a future `/triage-captured` skill, or post-PRD reflection skills from backlog #47 / #70) can be added without re-amending this rule.

**Supersedes [ADR-0004](0004-bypass-prevention.md) D4** which enumerated specific paths. The enumeration is no longer used; the universal scope replaces it.

### D2: Rule #11 mandatory

The full rewritten rule reads:

> **Surface deferred work as captured issues.** Every agent MUST capture every deferred or follow-up item it encounters as a `captured`-labeled GitHub issue (per [ADR-0006](0006-backlog-and-session-continuity.md) D4 as amended forward by [ADR-0008](0008-workflow-autolog-bootstrap-and-naming.md) D8). The autopilot's `backlog-critic` filters quality downstream per [ADR-0008](0008-workflow-autolog-bootstrap-and-naming.md) D2 — agents are not the bouncer. When in doubt about whether an item is worth capturing, capture it; the autopilot will BLOCK noise into the captured-tier graveyard where lazy human review can cull.

The change from "should" (discretionary) to "MUST" (mandatory) shifts the per-decision threshold. The autopilot makes this safe: under discretionary capture, false-negatives (uncaptured items) were the dominant error mode and unrecoverable; under mandatory capture, false-positives (over-captured items) are the dominant error mode and the autopilot filters them.

**Supersedes [ADR-0006](0006-backlog-and-session-continuity.md) D4's discretionary phrasing.** The enumerated list of agents (grill-me, slicer, slicer-critic, prd-critic, adr-critic, reviewer, qa-plan) and the target-tier amendment from ADR-0008 D8 are preserved unchanged; only the strength changes.

### D3: Asymmetric-default-BLOCK universal across critics

Extend [ADR-0008](0008-workflow-autolog-bootstrap-and-naming.md) D2's asymmetric-default-BLOCK rationale to all 6 critics. Only **4 critics need the clause added** (`prd-critic`, `adr-critic`, `slicer-critic`, `reviewer`); `glossary-critic` already has it (per ADR-0007's drafting — see `glossary-critic.md` line 16: *"Default conservative: when uncertain about any rule, BLOCK"*), and `backlog-critic` already has it (per ADR-0008 D2).

Each critic's rubric section gains an explicit clause near the top:

> **Default conservative: when uncertain about any rule, BLOCK.** A false-positive APPROVE puts unverified work on `main` (or into the curated backlog, or into a published PRD/ADR) — high friction to undo. A false-negative BLOCK creates a revision cycle the implementer can address — low friction to recover. Conservative-default is the asymmetric correct choice.

The exact wording adapts per critic to the relevant artifact (PR vs PRD vs ADR vs slice vs glossary entry), but the asymmetric-cost rationale is shared.

**Generalizes [ADR-0008](0008-workflow-autolog-bootstrap-and-naming.md) D2** from `backlog-critic` to all critics. The original D2 framing (false-APPROVE pollutes curated tier; false-BLOCK leaves item in recoverable tier) maps to every critic's verdict surface.

### D4: Distinct adversarial mindsets per critic

Each of the 6 critics receives a named adversarial role/framing in its prompt:

| Critic | Mindset framing | What this mindset is skeptical about |
|---|---|---|
| `prd-critic` | **paranoid product manager** | Value claims; scope creep; vague success criteria; "we should improve X" non-goals; rabbit-holes that drift into the body |
| `adr-critic` | **paranoid architect** | Hidden coupling between decisions; supersession hygiene (D-ID accuracy); bootstrap-mode lacuna; cross-ADR consistency drift |
| `slicer-critic` | **paranoid project manager** | Ordering risks; risk burying (biggest risk at the end); cascade-doc gaps; INVEST shape; LoC cap proximity |
| `reviewer` | **paranoid SRE** | Scope drift; missing tests for behavior; secret leaks; hidden behavior changes; ADR conflicts; LoC cap; provenance gaps |
| `glossary-critic` | **paranoid linguist** | Scope category misalignment; authority anchoring drift; definition tightness; duplicate hunting; cross-reference accuracy |
| `backlog-critic` | **paranoid triager / editor** | Actionability gaps; PRD-vs-trivial-lane scope mismatch; duplicate captures; clarity for future-self grilling |

The framing appears as a short heading in each critic's prompt (e.g., a 2-3 line block titled "Adversarial mindset" near the top of the file), with concrete examples of what THIS critic's mindset catches that others wouldn't.

**Rationale:** different mindsets catch different failure modes. The current shared "adversarial reviewer" framing across critics produces correlated APPROVE patterns — they ask similar questions. Distinct mindsets reduce correlation; each critic looks for what its specialty would catch first. The mindset framing also serves as a self-description for new contributors reading the critic file.

### D5: Bootstrap-mode acknowledgment (per [ADR-0004](0004-bypass-prevention.md) D2)

The new rule shapes (D1, D2) and critic prompt updates (D3, D4) bind FORWARD from the slice that ships them. Earlier slices/PRDs and earlier critic invocations are grandfathered — neither retroactive sweeps of prior PR diffs nor retrofitting of past critic verdicts.

Specifically:
- **Rule #10 universal scope (D1)** applies to PRs opened from the merge of the slice that rewrites the rule onward. Open PRs at merge-time use whichever rule shape their loaded `CLAUDE.md` had at PR-open.
- **Rule #11 mandatory (D2)** applies to agent invocations from the merge of the slice that rewrites the rule onward. In-flight invocations at merge-time use the discretionary shape they loaded.
- **Default-BLOCK clause (D3)** applies to critic invocations from the merge of the slice that adds the clause to each critic. Per-critic merging means each critic's prompt changes are scoped per-slice (e.g., `prd-critic` gets default-BLOCK in the walking-skeleton slice; `reviewer` gets it in the propagation slice).
- **Distinct mindsets (D4)** apply identically — per-critic prompt edits bind forward from per-critic merges.
- **R-META reviewer rule update** (to mechanically enforce the broadened rule #10 scope) ships in the same slice as the rule #10 rewrite; R-META binds forward from its merge.

This ADR introduces no retroactive critique of prior APPROVE verdicts and no rewriting of merged PRs to comply with the new rule shape. The "every critic APPROVE'd round 1 in 2026-05-16 session" evidence motivating D3/D4 is acknowledged as the asymmetric-default-pattern's pre-state; the post-state will accumulate evidence to be evaluated when sufficient PRDs have shipped under the new pattern.

## Consequences

**Positive:**
- Zero enumeration drift on rule #10 — any future tracked artifact is auto-covered.
- The 2026-05-16-style "trivial-lane PR slips past R-META because the path wasn't enumerated" failure mode is eliminated.
- Mandatory capture (D2) removes the agent-judgment bottleneck on item surfacing; autopilot filtering replaces it. Items previously lost to under-surfacing are now captured + filtered.
- Default-BLOCK (D3) across all critics shifts the per-decision threshold toward catching real issues; the asymmetric-cost rationale is empirically supported by the `backlog-critic` precedent on #73.
- Distinct mindsets (D4) reduce critic-output correlation; each critic looks for its specialty's failure modes first.
- The rule rewrites are template-friendly: forks of this repo inherit the universal/mandatory shapes without per-fork enumeration upkeep.

**Negative:**
- D2's mandatory capture WILL increase captured-tier issue volume; the autopilot's BLOCK path will catch noise but the user's lazy-review burden on captured-tier grows roughly with agent activity. Mitigation: the BLOCK path keeps noise OUT of the curated backlog; only the captured graveyard grows. If captured-tier growth becomes unmanageable, the future `/triage-captured` sweep skill (ADR-0008 Open Questions) or a cull mechanism becomes the response.
- D3's default-BLOCK risks over-blocking real-good-work — critics may BLOCK on cases the human would have APPROVED. Mitigation: the single-revision-loop pattern (≤3 rounds for most critics; once for autopilot) absorbs most false BLOCKs; the failure mode at scale would be measurable as "rounds-per-PR" climbing — a metric we'll watch.
- D4's distinct mindsets require careful prompt engineering to avoid theatrical critique (a "paranoid SRE" reviewer that invents fake security issues to satisfy its role). The mindset framing must be a lens, not a personality. Mitigation: the prompts cite the existing rubric as the primary judgment surface; the mindset is the *order in which rubric items are scrutinized*, not a license to invent new failure modes.
- 4 critic prompts need the default-BLOCK clause added (D3) and 5 critic prompts need the distinct mindset framing block added (D4) — overlapping but distinct edit sets. `glossary-critic` already has D3's clause but needs D4's mindset block; the 4 default-BLOCK-needing critics also need D4's mindset block. `backlog-critic` needs neither edit (already compliant on both). Total: 5 critic files edited; 4 of them get two edits, 1 gets one edit.
- This PRD's slices are written under the OLD rule shapes (since they ship the new shapes); the bootstrap-mode policy (D5) makes this explicit.

**Neutral:**
- `backlog-critic` requires zero edit (already has both default-BLOCK and a domain-specific framing).
- No new subagents (D7 of ADR-0008's 6-critic-cap meta-rule unaffected; this PRD adds 0 critics).
- No CI / branch-protection changes (deferred to PRD-CI).
- R-META reviewer rule needs a narrow broadening to mechanically enforce D1; one rule edit in `reviewer.md`.

## Alternatives considered

- **Alt-A: Expanded enumerated rule #10** (add missing paths to the enumerated list rather than going universal). Rejected at grill Q2: still drifts every time a new tracked artifact ships; explicit user ask was "all files".
- **Alt-B: Status quo rule #10** (leave enumerated list as-is, accept gaps). Rejected at grill Q2: the gap is real and shown by the 2026-05-16 branch-protection-config.json incident.
- **Alt-C: Rule #11 strongly-recommended-with-skip-justification** (mandatory by default, but agent may skip a single item with explicit `NOT_CAPTURING: <reason>`). Rejected at grill Q3: more complex rule, audit-trail vector for sneaky non-capture, harder to enforce at scale.
- **Alt-D: Rule #11 conditional-mandatory** (mandatory for high-signal agents; discretionary for low-signal agents like grill-me). Rejected at grill Q3: enumeration drift, judgment-call on signal density.
- **Alt-E: Status quo rule #11 discretionary**. Rejected at grill Q3: explicit user ask was tightening; current discretionary lets items slip.
- **Alt-F: Default-BLOCK only (no distinct mindsets)** for D3/D4. Rejected at grill Q4: doesn't address the "different context and purpose" part of the user's ask; critics still feel generic-adversarial.
- **Alt-G: Distinct mindsets only (no default-BLOCK)** for D3/D4. Rejected at grill Q4: doesn't directly address the BLOCK-prone ask; default-PASS continues producing round-1 APPROVE.
- **Alt-H: Force minimum 2 rounds per critic invocation** (no round-1 APPROVE allowed; critics must always raise at least one revision item). Rejected at grill Q4: HIGH risk of theatrical critique; wastes rounds on good work; opposite of YAGNI.
- **Alt-I: Add a 7th meta-critic that reviews other critic verdicts** (catches lenient-APPROVE patterns). Rejected implicitly: would breach ADR-0008 D7's meta-rule on critic count without justification; over-engineering for what should be a per-critic prompt tightening.

## Open questions deferred

- Whether the captured-tier growth from D2's mandatory capture will require a cull / stale-close mechanism. Defer until we have post-merge data on captured-tier accumulation rates. Already tracked as future direction in ADR-0008 Open Questions.
- Whether rounds-per-PR will climb under D3's default-BLOCK pattern and by how much. No instrumentation today; observe over the next 3-5 PRDs and revisit if rounds visibly bloat.
- Whether the mindset framings (D4) need per-critic tuning after exposure (e.g., paranoid-SRE turns out too aggressive on reviewer for docs-only PRs). Defer to retrospective; framings are not load-bearing on the rule semantics.
- Whether the R-META reviewer rule needs full broadening to universal-tracked-file scope, or whether the narrower "NEW files in any tracked path" works equally well. Slicer decides during implementation; both interpretations honor D1's spirit.

## Future direction

- If captured-tier accumulation outpaces lazy human review under D2's mandatory capture, ship `/triage-captured` (the sweep skill noted in ADR-0008 Open Questions) to batch-process the graveyard.
- If rounds-per-PR climbs visibly under D3's default-BLOCK, revisit the asymmetric-default in a future ADR with the accumulated data.
- The CLAUDE.md restructure theme (queued for the next session) will revisit where rule text and ADR cross-references live; this ADR's rule-text changes may need to move to a different file or section then. The supersession path for that future move is: this ADR D1/D2 stay authoritative on the rule SUBSTANCE; the location of the rule text is the restructure ADR's concern.

## References

- [ADR-0001](0001-foundational-design.md) — foundational rules including the early shape of rules #10/#11 lineage.
- [ADR-0003](0003-autonomous-pipeline-with-critics.md) D2 (critic per generation stage), D4 (no human gates between stages — context for why critic quality matters), D8 (ADR placement at grill→PRD boundary — why this ADR is drafted alongside).
- [ADR-0004](0004-bypass-prevention.md) D2 (bootstrap-mode policy that D5 follows); D4 (the rule #10 enumeration this ADR supersedes).
- [ADR-0005](0005-output-shape-and-slicing-methodology.md) D1 (canonical critic verdict template — unchanged by this ADR; the default-BLOCK clause is additive to the rubric section not the output template).
- [ADR-0006](0006-backlog-and-session-continuity.md) D4 (rule #11 enumeration this ADR supersedes the strength of, not the content).
- [ADR-0007](0007-vocabulary-glossary-and-grill-me-extension.md) Negative Consequences (6-critic-cap meta-rule's predecessor — the *"a 6th would warrant explicit pushback"* clause that became ADR-0008 D7's formal meta-rule; this ADR adds 0 critics).
- [ADR-0008](0008-workflow-autolog-bootstrap-and-naming.md) D2 (asymmetric-default-BLOCK pattern this ADR generalizes); D7 (6-critic-cap meta-rule — observed and respected); D8 (bootstrap-mode acknowledgment pattern D5 follows).
- Grill session: PRD-discipline-tightening Q2–Q4 (2026-05-19).
- `decisions/README.md` — ADR conventions including immutability and supersession-via-new-ADR.
