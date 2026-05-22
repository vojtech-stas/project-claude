# ADR-0024: Root-cause workflow capture discipline (CLAUDE.md cross-cutting rule #13)

- **Status:** Accepted
- **Date:** 2026-05-22
- **Supersedes:** none.
- **Extends:** [ADR-0009](0009-discipline-tightening.md) D2 (rule #11 mandatory-capture for forward-work — preserved unchanged; this ADR adds rule #13 for backward/root-cause analyses without touching #11's scope); [ADR-0008](0008-workflow-autolog-bootstrap-and-naming.md) D3 (`/promote-to-backlog` inline-firing convention — applies to both rule #11 and rule #13 captures uniformly); [ADR-0008](0008-workflow-autolog-bootstrap-and-naming.md) D4 (backlog-critic 4-criterion rubric — applies to both shapes; no rubric extension needed); [ADR-0008](0008-workflow-autolog-bootstrap-and-naming.md) D7 (6-critic-cap meta-rule — honored, no new critic added); [ADR-0004](0004-bypass-prevention.md) D2 (bootstrap-mode policy cited in D5 below). CLAUDE.md cross-cutting rule #11 (forward-work mandatory capture) is the sibling rule this ADR's rule #13 complements.

## Context

The 2026-05-22 autonomous mega-session repeatedly encountered workflow defects and **patched each one as a symptom** in the in-flight work without capturing the root-cause workflow change. Five concrete instances:

1. **Stale-worktree false-alarm** hit twice in two sessions (#173 + this session). The agent in-session fixed the immediate symptom (drafted PRDs against wrong base) without capturing the layer-2 + layer-3 systematic fixes (#195 was needed; opened only after user prompt).
2. **PRD-V dangling D-ID refs** (D10 referenced when ADR-0015 only has D1-D6) caught in round 1 prd-critic + adr-critic BLOCK. Symptom-fixed by revision. The root cause (drafting from memory + revision-scope-too-narrow + no pre-critic verification step) only captured as #192 after user prompt.
3. **Personal `/to-prd` shadowing project `/to-prd`** caused manual orchestration bypass. Symptom-fixed (manual draft) in-session. Root cause (skill-name collision + personal-precedence rule) only captured as #191 after user prompt.
4. **Pre-commit vs commit-msg git-hook-type mismatch** caught in PRD-V round 1 prd-critic BLOCK. Symptom-fixed by renaming target file. Root cause (git hook taxonomy gap in `/best-practice-hooks` skill) only captured as #193 after user prompt.
5. **Parallel sibling cascade-doc rebase conflict** (PR #186 vs PR #183 both edited best-practice-workflow/SKILL.md References) needed manual rebase resolution. Root cause (slicer-critic rubric lacks cross-PR cascade-doc collision check + no sibling-cascade-doc convention) only captured as #194 after user prompt.

The user articulated the missing discipline (verbatim 2026-05-22):

> *"all the mistakes you're finding right now you have to address as core mistakes that are done in the workflow. So you have to figure out not to do this again. And this should be logic as well that whenever you find some mistake in the workflow or maybe anywhere that you put it into the backlog so that we address the problem not from the results but from the cost that the problem came from."*

The 6th capture, [#196](https://github.com/vojtech-stas/project-claude/issues/196), is itself the meta-level instance — proposes this very ADR mandating root-cause-shape captures for all future workflow defects.

The project already has rule #11 (mandatory forward-work capture per ADR-0009 D2), but its scope is "deferred or follow-up items" — agents (correctly) interpret it as covering features-not-yet-shipped but NOT as covering "I hit a workflow defect; the systematic fix is X" findings. The result: strong autopilot for forward work, weak autopilot for backward root-cause analyses. Each session re-discovers the same workflow defects without compounding the prevention work.

## Decisions

### D1: Add cross-cutting rule #13 to CLAUDE.md — root-cause workflow capture discipline

CLAUDE.md gains a new cross-cutting rule (appended after the existing rule #12) with the following load-bearing intent (exact wording is implementer's call; substance must include):

> **#13. Root-cause workflow capture (Symptoms ≠ causes).** When an agent encounters a workflow mistake — a recurring failure pattern, a critic round that should have been one round shorter, a manual orchestration bypass, a cascade-doc conflict, or any "I had to work around this" moment — it MUST capture a `captured`-labeled GitHub issue naming (a) the symptom observed, (b) the root cause analyzed, and (c) the proposed workflow change that prevents recurrence. Symptom-only fixes in the in-flight PR are necessary but insufficient; the workflow change is the deliverable. Per backlog-critic 4-criterion rubric (per ADR-0008 D4), "actionable / scoped / not duplicate / clear" applies to root-cause captures as much as forward-work captures. Per ADR-0024.

Rule #13 binds every agent (main + subagents) at every stage of the pipeline (per the cross-cutting rules' standard scope, mirroring rule #11's phrasing).

### D2: Rule #13 complements rule #11 (forward-work) — division of labor explicit

ADR-0009 D2 made rule #11 mandatory for forward-work captures ("Surface deferred work as captured issues"). Rule #13 has a DIFFERENT surface (backward/root-cause analyses, not forward-work) and a DIFFERENT body-shape requirement (3-part symptom/cause/proposed-change vs rule #11's open shape).

Both rules use the SAME downstream mechanism:
- Same label (`captured`)
- Same inline-firing convention (ADR-0008 D3 — invoke `/promote-to-backlog` after `gh issue create --label captured`)
- Same backlog-critic 4-criterion rubric (ADR-0008 D4 — actionable / scoped / not duplicate / clear)
- Same captured-tier graveyard semantics on BLOCK (ADR-0008 D2)

The division of labor is by **input trigger**:
- **Rule #11** fires when the agent encounters a deferred or follow-up item (forward-pointing: "thing not yet done")
- **Rule #13** fires when the agent encounters a workflow mistake (backward-pointing: "thing that went wrong, here's why")

An agent encountering both kinds of finding in one session captures both kinds of issue. Neither rule overrides the other; they're additive.

`decisions/README.md` ADR-0009 row Status will be amended to note the division of labor (cascade-doc per D6 below).

### D3: Root-cause capture body MUST contain 3 named sections

The 3-part body shape is:

1. **Symptom observed** — concrete: what happened, when, what artifact suffered. Cite issue numbers / PR numbers / commit SHAs / file paths.
2. **Root cause analyzed** — why the mistake was possible (system property, not blame). May cite docs.claude.com / git-scm.com / etc. for authoritative reference.
3. **Proposed workflow change** — mechanical or convention-level; named files / rules to change; prevents recurrence. May propose alternatives (A/B/C) with recommendation.

backlog-critic evaluates the same 4-criterion rubric (per ADR-0008 D4) on root-cause captures: "actionable" naturally maps to whether the proposed workflow change names concrete artifacts; "scoped" maps to whether the proposed change fits a PRD/slice/trivial-lane appetite; "not duplicate" maps to whether other root-cause captures already covered the same defect class; "clear" maps to whether the 3 sections stand alone for future grilling.

No rubric extension needed for slice 1. If differential evaluation proves valuable in practice, a future ADR may add it.

### D4: Mechanical /audit-meta reinforcement deferred to separate PRD

Backlog-critic round-1 verdict on #196 recommended treating the rule-text slice as walking-skeleton and the `/audit-meta` workflow-events.jsonl scan (for "had to bypass / had to manually" pattern surfacing) as an explicit second slice/PRD once jsonl coverage matures.

This ADR honors that recommendation: D1's rule #13 is the load-bearing decision; the mechanical /audit-meta extension is future direction (named in §"Future direction" below). Slice-1 ships the rule; mechanical reinforcement ships when warranted.

### D5: Bootstrap-mode acknowledgment (per ADR-0004 D2)

Rule #13 binds **forward from the slice that ships it**. No retroactive sweep:

- Past sessions ran without the rule; their captured issues are grandfathered (whether or not they follow the 3-part shape).
- The 6 captures from the 2026-05-22 session (#191-#196) are explicitly the canonical seed examples — they follow the 3-part shape by author intent, predating the rule.
- Past PRs and commits are not retroactively scanned for "should have been a root-cause capture" findings.
- Existing 22 ADRs, 12 skills, 10 subagents are UNCHANGED by this ADR (modulo the documented cascade-doc edits per D6 below).

Forward binding starts at slice-1 merge: every new session from that moment forward applies rule #13 when encountering workflow defects. The 6-critic-cap meta-rule (ADR-0008 D7) is unaffected — no new critic added.

### D6: Cascade-doc updates

- `CLAUDE.md` — new rule #13 inserted after rule #12 in the "Cross-cutting rules" section (D1 specifies the load-bearing substance).
- `decisions/README.md` — new ADR-0024 index row.
- `decisions/README.md` — ADR-0009 row Status column amended to note rule #11 + #13 division of labor per D2 (mirrors the documented pattern of ADR-0013 D5 updating ADR-0003 row and ADR-0012 updating ADR-0007 row).
- `README.md` — NOT updated. Root-cause discipline is orthogonal to README's "Workflow enforcement" section (which enumerates the 3+1 bypass-prevention layers per ADR-0004 D3 + ADR-0023). Slicer may revisit if a natural surface emerges.

### D7: 6-critic-cap honored

Per ADR-0008 D7, the project currently runs 6 critics (reviewer, prd-critic, adr-critic, slicer-critic, glossary-critic, backlog-critic). This ADR adds NO new critic — backlog-critic's existing 4-criterion rubric covers root-cause captures the same way it covers forward-work captures. The 6-critic-cap meta-rule is honored by design.

If a future PRD introduces R-CAPTURED-SHAPE as a reviewer rule (forcing PRs to ship a root-cause capture when an in-PR workflow defect was observed), that PRD extends the existing reviewer (no 7th critic) — but is explicitly out of scope here (per parent PRD §6 OQ-3).

## Consequences

### Positive

- **Compounding workflow improvement.** Every observed workflow defect now produces a backlog item proposing a workflow change; the project's workflow improves from its own observed mistakes rather than re-discovering them session-after-session.
- **Cheap to author, cheap to evaluate.** The 3-part body shape is small; backlog-critic's existing rubric handles it; the `/promote-to-backlog` autopilot fires inline per ADR-0008 D3.
- **Recursive meta-defense.** When an agent forgets rule #13 itself, that forgetting is itself a workflow defect — captured per rule #13 as a meta-observation. The 2026-05-22 session's #196 capture is the canonical demonstration.
- **Honors existing conventions.** No new critic (ADR-0008 D7 honored). No new label (uses `captured`). No new autopilot (uses ADR-0008 D3). No rule #11 modification. Pure additive layering.
- **Separates concerns from rule #11.** Forward-work (rule #11) vs backward-cause (rule #13) — each rule single-responsibility per the project's existing cross-cutting-rules discipline.

### Negative / Accepted

- **Discipline is still advisory like all CLAUDE.md rules.** Agents may forget; the rule itself can't enforce its own application. Mitigation: D4 future-direction `/audit-meta` scan for "had to bypass" patterns; future R-CAPTURED-SHAPE reviewer rule per parent PRD §6 OQ-3.
- **3-part body shape adds 30-90 seconds of authoring time per capture.** Accepted as the cost of compounding workflow improvement.
- **Risk of over-capture.** Agents may interpret every minor friction as a workflow defect, flooding the captured tier. Mitigation: backlog-critic's default-conservative rubric already filters noise to the captured-tier graveyard per ADR-0008 D2; the same filtering applies to root-cause captures.
- **Rule #13's 3-part shape is enforced by convention, not by a reviewer rule.** If non-conforming root-cause captures appear, they go through the captured tier the same way — graveyard if low-quality, backlog if backlog-critic APPROVEs. The rule is advisory because forcing shape would push the discipline toward bureaucracy.
- **No `/promote-to-backlog` rubric change** — backlog-critic uses identical evaluation for both shapes. If differential evaluation proves valuable in practice, a future ADR adds it.

## Alternatives considered

- **Alt-A: Don't add rule #13; extend rule #11 with root-cause-shape clause.** Rejected per parent PRD §3 — rule #11's surface (forward-work) is distinct from rule #13's surface (backward analyses); separate rules keep each single-responsibility. backlog-critic Rec on #196 also flagged this option as worth considering; weighed it and chose new rule for clarity.
- **Alt-B: Ship the rule + mechanical /audit-meta scan in the same slice.** Rejected per backlog-critic Rec on #196 — rule-text walking-skeleton first; mechanical reinforcement second once jsonl coverage matures. Avoids slice-1 LoC bloat.
- **Alt-C: Add a new reviewer rule R-CAPTURED-SHAPE that BLOCKs PRs where an observed workflow defect lacks a paired root-cause capture.** Rejected for slice 1 (per parent PRD §6 OQ-3) — too aggressive at start; rule should mature as advisory first, then potentially become reviewer rule once usage patterns stabilize.
- **Alt-D: Don't write an ADR; just edit CLAUDE.md.** Rejected per `decisions/README.md` "When to write an ADR" heuristic — the decision constrains future work (every future agent inherits the discipline), a future maintainer would ask "why?" without explanation, so ADR is warranted. ADRs back rules #10/#11/#12 the same way.
- **Alt-E: Add a backlog-critic rubric extension for root-cause-shape differential evaluation.** Rejected per D3 — existing 4-criterion rubric covers both shapes naturally; differential evaluation is YAGNI until a real differentiation need surfaces.
- **Alt-F: Make rule #13 apply only to main agent (not subagents).** Rejected — workflow defects can be observed by any agent (e.g., implementer hits a stale-worktree mid-PR); restricting to main agent leaves subagent observations un-captured. Mirrors rule #11's "every agent" scope.
- **Alt-G: Use a new label `root-cause` (instead of reusing `captured`).** Rejected — uses the same autopilot (`/promote-to-backlog` per ADR-0008 D3) and the same downstream rubric (backlog-critic per ADR-0008 D4); a separate label would force a second autopilot. Reusing `captured` keeps the mechanism simple.
- **Alt-H: Defer entirely to a future PRD when workflow-events.jsonl reaches some threshold.** Rejected per parent PRD §1 — the discipline is independent of mechanical reinforcement; agents can apply rule #13 by hand starting day-one, and the mechanical scan can layer on later.

## Open questions deferred

- **OQ-1: Canonical capture-template file** (`.claude/issue-templates/captured-root-cause.md`) — defer per parent PRD §6 OQ-1; implementer may add if zero LoC cost.
- **OQ-2: `/promote-to-backlog` skill body mention** of the 3-part shape — defer per parent PRD §6 OQ-2; implementer may add if trivial.
- **OQ-3: R-CAPTURED-SHAPE reviewer rule** — deferred to future PRD per parent §6 OQ-3.
- **OQ-4: /audit-meta workflow-events.jsonl "had to bypass / had to manually" scan** — deferred to separate PRD per D4.
- **OQ-5: Differential evaluation criteria in backlog-critic** for root-cause vs forward-work captures — defer until a real need surfaces.
- **OQ-6: Cross-skill documentation** (mentioning rule #13 in `/grill-me`, `/ship`, etc. skill bodies) — defer; CLAUDE.md auto-load is the canonical reminder.

## Future direction

- **`/audit-meta` workflow-events.jsonl scan** per D4 — once jsonl logs accumulate enough "had to bypass / had to manually" patterns to be useful as a surfacing mechanism.
- **R-CAPTURED-SHAPE reviewer rule** per OQ-3 — once rule #13 has been advisory for N sessions and the value/cost trade-off is clear.
- **Differential backlog-critic evaluation** per OQ-5 — only if real differentiation needs emerge in practice.
- **Capture-template file** per OQ-1 — natural ergonomic improvement once the 3-part shape is the dominant capture form.
- **Cross-skill mention propagation** per OQ-6 — when /audit-meta surfaces drift in how agents apply rule #13 across different skill contexts.
- **Migrate the 6 canonical-seed captures (#191-#196) to a "Root-cause workflow improvements" section in `decisions/README.md` or a new `decisions/workflow-improvements/README.md`** — once enough root-cause captures land to warrant a curated index. Out of slice-1 scope.

## References

- docs.claude.com/en/docs/claude-code/best-practices — *"Hooks are deterministic and guarantee the action happens"* (related framing — but this ADR is about advisory rules not deterministic hooks; cited for the discipline ethos).
- [ADR-0001](0001-foundational-design.md) — D12 original 7 cross-cutting rules (rule #13 is the 6th rule added post-foundational).
- [ADR-0003](0003-autonomous-pipeline-with-critics.md) D8 — macro-ADR placement (this ADR drafted alongside parent PRD).
- [ADR-0004](0004-bypass-prevention.md) D2 — bootstrap-mode policy cited in D5.
- [ADR-0004](0004-bypass-prevention.md) D4 — rule #10 origin (the first post-foundational rule); now superseded for scope by ADR-0009 D1.
- [ADR-0006](0006-backlog-and-session-continuity.md) D4 — rule #11 origin (discretionary); now superseded by ADR-0009 D2.
- [ADR-0008](0008-workflow-autolog-bootstrap-and-naming.md) D3 — `/promote-to-backlog` inline-firing convention (shared mechanism with rule #11).
- [ADR-0008](0008-workflow-autolog-bootstrap-and-naming.md) D4 — backlog-critic 4-criterion rubric (covers both shapes per D3 above).
- [ADR-0008](0008-workflow-autolog-bootstrap-and-naming.md) D7 — 6-critic-cap meta-rule (honored, no new critic added per D7 above).
- [ADR-0009](0009-discipline-tightening.md) D1 — current rule #10 scope (universal main-agent meta-output discipline).
- [ADR-0009](0009-discipline-tightening.md) D2 — current rule #11 wording (mandatory forward-work capture); rule #13 explicitly complements without modifying.
- [ADR-0015](0015-claude-code-hooks-adoption.md) D2 — Claude Code hooks scope policy (the discipline analog: deterministic enforcement layer); rule #13 is the advisory analog at the agent-behavior layer.
- [ADR-0023](0023-validation-and-notification-hooks-extension.md) — PRD-V validation hooks (mechanical enforcement complement; this ADR's rule #13 is the advisory side of the same broader principle).
- `CLAUDE.md` "Cross-cutting rules" section — the file modified by D1.
- Captured-issue seed cluster: [#191](https://github.com/vojtech-stas/project-claude/issues/191), [#192](https://github.com/vojtech-stas/project-claude/issues/192), [#193](https://github.com/vojtech-stas/project-claude/issues/193), [#194](https://github.com/vojtech-stas/project-claude/issues/194), [#195](https://github.com/vojtech-stas/project-claude/issues/195), [#196](https://github.com/vojtech-stas/project-claude/issues/196) — 2026-05-22 session demonstration of the discipline.
- `~/.claude/projects/F--project-claude/memory/feedback_root_cause_capture.md` — the user-memory file written 2026-05-22 codifying the discipline pre-rule-#13 (becomes redundant once this ADR lands; still useful for cross-project portability).
