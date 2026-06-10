# ADR-0054: Critic output contracts + CRITIC trailer standard schema

- **Status:** Accepted
- **Date:** 2026-06-10
- **Extends:** [ADR-0037](0037-production-verification-gate.md) D2/D3 (qa-tester route policy tightened by D5 below) + [ADR-0040](0040-qa-human-residual-model.md) D2/D4 (the residual machinery the downgrade policy reuses) + [ADR-0046](0046-codebase-critic-and-parsimony-reframe.md) D1 (parsimony principle: no new critic — this ADR extends existing critics' output contracts)
- **Honors:** [ADR-0004](0004-bypass-prevention.md) D2 (bootstrap-mode policy), [ADR-0024](0024-root-cause-workflow-capture-discipline.md) D2/D3 (rule #13 unchanged), [ADR-0003](0003-autonomous-pipeline-with-critics.md) D8 (macro-ADR ships in slice 1)

---

## Context

### Measured compliance study: 0–17.5% prose-instruction vs 97.5% output-contract

PRD #651 made the declared==measured comparison computable from the GitHub artifact trail. The comparison's `E-PRDCRITIC-*`-class edges require critic verdict comments on PRD issues. A design-phase compliance study measured this repo's own compliance with **four** existing prose conventions where the *orchestrator* is told to post something:

| Convention | Compliance |
|---|---|
| prd-critic verdict comments on PRD issues | 7/40 PRDs (17.5%), decaying to 0/13 since 2026-06-05 |
| qa-plan comments on PRD issues | 1/32 PRDs (3.1%) |
| proof-posting by orchestrator | 1 PRD ever |
| `needs-human-check` issues opened | 0 issues ever |

**The single high-compliance counterexample is structural, not cultural: the reviewer posts verdicts as its own output channel — 97.5% (39/40 merged PRs).** The reviewer uses `gh pr comment <PR> --body-file <tempfile>` as a terminal output-contract step in its own prompt. The four low-compliance conventions are orchestrator-prose instructions ("the main agent should post X after Y"), which decay to 0% over time.

Conclusion: prose instructions executed by the main agent decay; output-contract actions executed by the subagent itself persist.

### Forensics P1/P2/P5/P6 (process-retrospective findings)

- **P1 (fixture contamination):** synthetic data entered production data stores (`.claude/logs/`) and was used as passing QA evidence; no fixture rule blocked it.
- **P2 (verification-route silent downgrade):** the #639 crash shipped through a silent browser→command-run route downgrade; no policy required explicit route-change disclosure or PROVISIONAL routing.
- **P5 (system-level skeleton never walked):** individual PRDs used walking-skeleton discipline for 5 consecutive PRDs while no REAL datum traversed the full multi-PRD pipeline in production; per-PRD walking-skeleton rule existed but no system-skeleton rule.
- **P6 (shape-gated verification):** verification gates checked artifact shape, not truth; a fixture-shaped log file passed hooks verification with no check that the data was real or the environment was fresh.

Today the comparison's `E-PRDCRITIC-*`-class edges report `not-exercised`/`missing (discipline)` — honest, but the loop stays open. The 97.5% reviewer pattern is the mitigation template.

---

## Decisions

### D1: Critic verdict provenance via output contracts

Verdict-posting is part of each ≤3-round critic's **own output contract**: after rendering a verdict (every round, BLOCK and APPROVE alike), the critic posts its full verdict body with the fenced CRITIC trailer as a `gh issue comment` on the artifact under review. Specifically: `prd-critic`, `adr-critic`, `slicer-critic`, and `codebase-critic` (per-PRD mode) post to the parent PRD issue; the reviewer already posts to PRs via `gh pr comment`; backlog-critic's verdict is already posted by `/promote-to-backlog`. The comment is the critic's **existing authorized output channel** — tool boundaries do not widen (the `gh issue comment` command was already authorized in `prd-critic` and `adr-critic`; `slicer-critic`'s tool boundary is widened here to permit it).

This adopts the empirically-97.5% reviewer pattern. A BLOCK round posts too — that is what makes round counts recoverable by the collector. The critic posts the verdict it just rendered; it does not wait for APPROVE-only to post. **Backstop:** the PRD #651 comparison renders missing verdict evidence as `missing (discipline)` — loud and attributable, never silent; the collector's `E-PRDCRITIC-*`-class edges flip from `not-exercised` to `confirmed` for runs that comply.

**Whole-repo mode excluded:** `codebase-critic` whole-repo mode has no single artifact under review; its findings flow via `captured` issues per [ADR-0051](0051-whole-repo-macro-audit-cadence.md) D3. This decision covers per-PRD mode only.

### D2: CRITIC trailer standard schema

One fixed mandatory key set for every critic trailer: `VERDICT`, `REASON`, `ROUND` — per-agent extension keys allowed only after the core three. This ends the PR #559 drift class (ROUND-less trailers that silently break round-count recovery in the collector). The three keys appear in every trailer, BLOCK and APPROVE alike. A deterministic `tools/ci-checks.sh` check (per PRD #660 slice 3) will assert every critic prompt documents the mandatory keys.

Each critic's prompt documents the schema explicitly rather than delegating documentation to ADR-0005 D1 alone — this makes the requirement visible at the point of authoring a verdict (CLAUDE.md rule #9 DRY applies to documentation, not to the schema standard itself).

### D3: Fixture discipline (CLAUDE.md rule #21)

Fixture/synthetic data never enters production data stores (`.claude/logs/*`). Fixtures live in `dashboard/fixtures/` and load only behind an explicit flag. Any verification whose evidence derives from fixture-tagged data is INVALID. Mechanized via reviewer rule **R-FIXTURE** (BLOCK any PR whose code writes `.claude/logs/` paths outside `.claude/hooks/`); writer-side guards (the `WORKFLOW_LOG_DIR` sandbox and sid-pattern routing) land with capture v2 (PRD 3). **Alternative rejected:** cleanup-after-the-fact (the 2026-06-10 archive operation) — detection-based hygiene proved 20 days too slow and required manual forensics to discover the contamination.

### D4: Proof provenance (CLAUDE.md rule #20 amendment)

Every proof artifact states its **data source** (real session id / PRD / PR + timestamp, never fixture-patterned) and its **environment freshness** (e.g. dashboard restarted from merged code when server.py changed). The orchestrator checks both at wrap-up, extending [ADR-0037](0037-production-verification-gate.md) D3's orchestrator-enforced gate from artifact-presence to evidence-validity. **Alternative rejected:** keeping rule #20 shape-only — the forensics showed shape gates were satisfied by fixtures and simulations four separate ways (P1/P2/P5/P6 above).

### D5: Verification-route downgrade policy

When a declared route's tooling is unavailable in the verification environment, the verdict is **PROVISIONAL** and routes to the `needs-human-check` queue ([ADR-0040](0040-qa-human-residual-model.md) D2/D4 machinery) — never a silent PASS via a weaker route (the #639 class). The hook-fire route additionally gains a registration-liveness probe (spawn `claude -p 'noop'`, assert a fresh beacon — manual script invocation only proves script-correctness). The browser route gains data-provenance + fresh-process assertions, further tightening [ADR-0040](0040-qa-human-residual-model.md) D5's fidelity chain. **Alternative rejected:** hard-FAIL on missing tooling — punishes environment variance with pipeline stalls; PROVISIONAL preserves flow while keeping a human in the loop.

### D6: System-skeleton + live-feed rules (CLAUDE.md rules #21–#22)

**CLAUDE.md rule #22:** a feature implementing stage N of a multi-PRD pipeline must, in slice 1, demonstrate one REAL datum traversing stages 1..N in the production environment — enforced at decomposition time by `slicer-critic` (**SC-SYSTEM-SKELETON**) and at PRD-gate time by `prd-critic` (**PC-LIVE-FEED**: pipeline-consuming PRDs declare a live-feed precondition; a dead upstream feed FAILS the production check rather than PROVISIONALing). **Alternative rejected:** per-PRD walking skeletons only — that discipline held for 5 consecutive PRDs while the system-level skeleton was never walked once (forensics P5).

### D7: Bootstrap-mode (per [ADR-0004](0004-bypass-prevention.md) D2)

All mechanisms bind forward from the merge of their slice. The self-proving acceptance (prd-critic + slicer-critic verdicts posted as comments on PRD #660) applies to THIS PRD's own pipeline run and onward. Historical PRDs are not retroactively re-verified; their missing verdict evidence renders as `missing (discipline)` — honest history, no rewrite. Earlier slices of PRD #660 itself (branches cut before this ADR merged) operated under the prior rules and are grandfathered.

---

## Consequences

**Positive:**
- The `E-PRDCRITIC-*`-class comparison edges flip from `not-exercised` to `confirmed` for pipeline runs that comply — the PRD #651 measurement loop closes.
- The 97.5% pattern is mechanically reproducible: output contracts in subagent prompts are followed; prose instructions to the orchestrator are not.
- ROUND-less trailer drift (PR #559 class) is ended by the mandatory schema, making round counts recoverable from the comment trail.
- Fixture contamination and silent-downgrade verification are addressed at the rule layer, with reviewer-side mechanical enforcement landing this slice and writer-side guards landing in capture v2.

**Negative:**
- Every critic prompt gains ~8–10 lines of output-contract text — small but real LoC addition to runtime artifacts (well within R-LOC per slice).
- The PRD #651 collector must see real verdict comments on PRDs; if a critic is invoked outside the standard `/ship` pipeline (e.g., manual grill), the comment may be missing — the comparison renders it `missing (discipline)` rather than erroring.

---

## Alternatives considered

### A1: Orchestrator-relay posting ("the `/ship`-posts-it convention")
The orchestrator reads the critic's returned verdict and posts it to the PRD issue. **Measured at 0–17.5%, decaying to 0%.** This is precisely the compliance class this ADR replaces. The root cause is that orchestrator-relay is a two-step process: the critic runs and returns, then the orchestrator must remember to post. The orchestrator's "remember" step is a prose instruction that decays. Rejected: the solution is relocating the posting action into the critic's own contract, not tuning the orchestrator prose.

### A2: Per-critic free-form trailers with collector-side heuristics
Each critic uses its own trailer format; the collector applies fuzzy parsing to recover VERDICT/REASON/ROUND. **Rejected:** pushes schema drift onto every consumer forever. The PR #559 incident (a ROUND-less trailer that silently broke round-count recovery) demonstrates the cost of per-critic divergence. A single mandatory schema is cheaper to maintain and verify deterministically.

### A3: Hard-FAIL (not PROVISIONAL) on missing tooling for route downgrade
When the declared verification route's tooling is unavailable, FAIL the verification rather than routing to the human-check queue. **Rejected:** punishes environment variance (e.g., a CI runner without a browser) with pipeline stalls; PROVISIONAL preserves flow while keeping a human in the loop per [ADR-0040](0040-qa-human-residual-model.md) D2/D4.

### A4: ci-checks network-bound PRD-comment gate
A GitHub Actions check that asserts every merged PR's parent PRD carries at least one critic verdict comment. **Deferred** (not rejected): the deterministic local checks + output contracts + the collector's `missing (discipline)` visibility cover the loop; a network-bound required check is a separate decision if discipline regresses. Local determinism is preserved.

---

## References

- PRD #660 — the parent PRD that authored these decisions.
- [ADR-0053](0053-artifact-trail-as-system-of-record.md) — the comparison consuming these verdicts (D3: the `E-PRDCRITIC-*`-class edges that become `confirmed` once D1 complies).
- [ADR-0051](0051-whole-repo-macro-audit-cadence.md) D3 — whole-repo mode findings flow via captured issues, not PRD comments (why D1 excludes whole-repo mode).
- [ADR-0037](0037-production-verification-gate.md) D2/D3/D5 — the verification-route and orchestrator-enforcement model extended by D4/D5 above.
- [ADR-0040](0040-qa-human-residual-model.md) D2/D4/D5 — the residual machinery D5 above reuses.
- [ADR-0046](0046-codebase-critic-and-parsimony-reframe.md) D1 — parsimony principle: no new critic added here.
- [ADR-0004](0004-bypass-prevention.md) D2 — bootstrap-mode policy.
- [ADR-0005](0005-output-shape-and-slicing-methodology.md) D1 — the CRITIC trailer schema this ADR standardizes.
- `.claude/agents/*.md` — the critic roster; their prompts are the primary delivery artifacts of D1/D2.
- Real evidence: PRs #556/#565/#609/#617 (parseable multi-round trails), PR #559 (ROUND-less trailer drift), PR #650 (unreviewed merge).
