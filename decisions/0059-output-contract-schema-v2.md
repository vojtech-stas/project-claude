# 0059 — Output-contract schema v2: attributable verdicts, disclosed doubts, named confusion

- **Status:** Accepted
- **Date:** 2026-06-12
- **Extends:** ADR-0054 D2 (CRITIC trailer standard schema — gains an attribution field)

## Context

Output contracts are this repo's only reliably-followed convention (ADR-0054's own study: ~97.5% trailer compliance vs ~0–17% for prose obligations) — so v2 invests in the contract layer. Measured gaps: (a) critic verdicts are parsed from comment trails by fragile author-string heuristics — the trailer itself never names which critic produced it, blocking the per-critic health metrics the dashboard needs; (b) generators have no sanctioned channel to disclose doubts, so risk either rides silently or leaks as claims that anchor reviewers (the channel the co-submitted blind-dispatch ADR closes); (c) when an agent hits contradictory instructions it guesses — a wrong guess costs a full implement+review round (#618's nondeterminism class). (The sibling concern — rule-#13 capture shape — is decided by the co-submitted capture-shape ADR in this wave's slice-1 PR, not here: captures are GitHub-issue artifacts, not trailers.)

## Decisions

### D1 — CRITIC trailer gains a `CRITIC:` field

Every critic verdict trailer adds `CRITIC: <agent-name>` (e.g. `CRITIC: reviewer`). This replaces author-string heuristics as the attribution mechanism for all downstream evaluators. Per ADR-0004 D2 (bootstrap-mode), the field binds forward from the merge of the slice that updates the critic prompts; historical verdicts are parsed best-effort and reported as `unattributed`.

### D2 — GENERATOR trailer gains `DIDNT_TOUCH:` and `CONCERNS:` fields

Generators (implementer, slicer, qa-tester) add: `DIDNT_TOUCH:` — files/areas deliberately left alone (scope-discipline evidence the reviewer can audit against the diff); `CONCERNS:` — self-disclosed risk entry points (doubts, not claims: "the cache path is untested under X"). CONCERNS is the sanctioned self-disclosure channel that survives the co-submitted blind-dispatch contract — reviewers may read doubts, never self-assessments of success. Per ADR-0004 D2, binds forward from the prompt-update slice; both fields are optional-empty but must be present as keys.

### D3 — Third RESULT enum: `CONFUSION`

GENERATOR trailers' `RESULT:` gains `CONFUSION` alongside SUCCESS/BLOCKED/INVALID_INPUT: the agent names the specific conflict (two contradictory instructions, an impossible acceptance criterion) plus 2–3 resolution options, and STOPS without guessing. The orchestrator routes CONFUSION to `needs-human` or back to the design step — never silently picks an option on the agent's behalf without recording the choice in the dispatch trail. Per ADR-0004 D2, binds forward from the prompt-update slice.

## Consequences

- Per-critic health metrics become computable from the trail alone; confusion stops costing silent wrong-guess rounds.
- Every agent prompt carrying a trailer template needs a one-time update (one slice's sweep).

### Enforcement (rule #23)

Deterministic: a trailer-field compliance evaluator — parses fenced trailers from the GitHub trail, per-field presence rates per agent (dashboard evaluator); CI CHECK 10's trailer-key grep extends to the new keys. Parsimony: no existing mechanism covers field-level presence — CHECK 10 today greps only the three ADR-0054 D2 mandatory keys, and no evaluator attributes verdicts per critic; this extends the existing contract and check rather than adding a new agent or artifact type. Shadow: unattributable verdicts and silent interpretation-guessing.

## Alternatives considered

- **Derive critic identity from comment authorship:** rejected — all agents post via the same identity; author heuristics already produced misattribution in collector code.
- **Free-prose concerns sections instead of a trailer field:** rejected — prose decays (the 0–17% finding); fields hold.
- **Bundling the capture-shape contract here:** rejected — captures are GitHub-issue artifacts with a different lineage (ADR-0024 D3) and different enforcement surface; decided in the co-submitted capture-shape ADR instead.
- **Letting the orchestrator resolve confusion inline:** rejected — the orchestrator guessing is the same defect one level up; routing + recording is the contract.

## References

- ADR-0054 (trailer standard + compliance study), ADR-0004 D2 (bootstrap-mode), issue #618 (verdict nondeterminism), workflow-v2 synthesis §B10 (2026-06-12).
