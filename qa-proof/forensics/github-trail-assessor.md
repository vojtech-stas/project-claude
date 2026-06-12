# github-trail-assessor

## SUMMARY
# GitHub-trail measurement feasibility — VERDICT: HYPOTHESIS CONFIRMED (with mapped gaps)

A per-PRD "measured" pipeline flow **can** be reconstructed from GitHub artifacts + git log with zero runtime-hook dependency. One batched GraphQL query per PRD returns the entire trail (PRD issue + comments + native sub-issues + their timelines + closing PRs + PR comments with critic verdicts) in **0.816s / 46.6KB / ~1 GraphQL point** — well under the <2s target. But coverage is partial by design: artifact-recorded stages are the *outputs* of pipeline stages, not the stages themselves; everything that happens in-conversation (grill, prd-critic rounds, slicer-critic rounds, qa-tester runs) leaves no artifact unless an agent chooses to post one.

## Reconstructed measured flow for PRD #640 (every timestamp verified via gh)

```
14:39:47Z  PRD #640 posted (label prd)
14:51:13-20Z  slices #641 #642 #643 posted (native sub-issues, label slice)   [+11m26s gap = slicer+slicer-critic in-conversation]
  #641: PR #644 (feat/641-hook-fire-beacon) opened 14:59:04 → APPROVE r1 @15:04:22 → merged 15:04:31 → slice closed 15:04:32
  #642: PR #645 (feat/642-telemetry-badge)  opened 15:09:56 → APPROVE r1 @15:14:39 → merged 15:14:51 → slice closed 15:14:53
  #643: PR #646 (feat/643-unified-viewer)   opened 15:21:44 → APPROVE r1 @15:29:09 → merged 15:29:18 → slice closed 15:29:20
15:30:59Z  PRD completion comment (claims browser-verify per slice)
15:31:00Z  PRD closed.  Total idea-posted→closed: 51m13s
```
Slices ran strictly serialized (each PR opens ~5-7min after previous merge). Multi-round review trails ARE recoverable: PR #556 shows opened 23:12:48 → BLOCK @23:17:34 → APPROVE @23:22:15 → merged 23:22:21; PRs #565/#609/#617 likewise show BLOCK→round-2→APPROVE.

## Per-declared-stage recoverability table

| Declared stage | Artifact | Recoverable? | Source + caveat |
|---|---|---|---|
| ship start | none | NO | in-conversation only |
| grill-me session | none | NO | in-conversation only |
| to-prd / prd-critic rounds | usually none | PARTIAL (2/15 PRDs) | "Joint prd+adr-critic gate: PASSED" comment exists only on macro-ADR PRDs (#552, #574); round counts in those comments |
| prd_issue posted | issue createdAt + label `prd` | YES, fully | timestamped |
| to-issues / slicer / slicer-critic rounds | none on slices (sampled #641: 0 comments) | OUTPUT ONLY | slice createdAt measures slicer *completion*; round count lost; gap PRD→slice createdAt (11m26s) is the only duration signal |
| slice_issues posted | sub-issue createdAt + label `slice` | YES, fully | native subIssues GraphQL field gives PRD→slice linkage deterministically |
| implementer dispatch→PR | PR createdAt, headRefName (encodes slice #), commit Co-Authored-By trailer | YES (end-anchored) | dispatch start not recorded; first-commit authorDate is best start proxy; trailer "Co-authored-by: Claude Opus 4.8" proves agent provenance |
| pr_opened | PR createdAt | YES, fully | |
| reviewer verdict(s) + rounds | PR issue-comments: "## reviewer verdict" heading + fenced CRITIC trailer (VERDICT/REASON/ROUND/ESCALATE/MERGE_STATUS) | YES, mostly | parseable by regex; 38/40 recent merged PRs have ≥1 verdict comment; BUT trailer schema drifts (PR #559 lacks ROUND field) and PR #650 (merged 2026-06-10) has ZERO verdict comments |
| merge | PR mergedAt + squash commit in git log | YES, fully | git log cross-checks (`(#644)` suffix in subject) |
| slice closed | ClosedEvent + `referenced` commit event | YES, fully | |
| qa-tester / production-verify | inconsistent | PARTIAL | PRD #557 has a "Browser-route production-verify — PASS" comment; PRD #640's proof is prose inside the completion comment; `needs-human-check` label exists but **zero issues ever carried it** |
| codebase-critic | `captured` issues (harvested findings) | WEAK | no verdict artifact; only side-effects |
| prd closed | closedAt + completion comment | YES, fully | |

## Slice→PR disambiguation (critical implementation detail)
Timeline cross-references are NOISY — PR #644's body mentions all 3 slices so it cross-refs all of them. The deterministic mapping is GraphQL `closingIssuesReferences` on the PR: verified 644→641, 645→642, 646→643. Branch names (`feat/<slice>-...`) are a secondary check.

## Collector feasibility
- **Speed**: 1 GraphQL query/PRD, 0.816s measured. Backfilling all ~15 closed PRDs ≈ 15 queries ≈ <15s cold, trivial cached.
- **Rate limits**: core REST 5000/hr, GraphQL 5000 points/hr, search 30/min. A full-repo collector uses <1% of budget.
- **Caching**: closed PRDs are immutable → cache forever keyed on `closedAt`; only open PRDs need refresh. REST also supports ETag/If-None-Match (304s don't count against limit).
- **Reliability hazard**: ~3 of ~20 gh calls on this Windows box returned transient `HTTP 401: Requires authentication` despite healthy `gh auth status` (keyring token-retrieval flap); immediate retry always succeeded. Collector MUST retry-once on 401.

## What this means for declared==measured
The artifact trail yields a measured graph of shape `prd_issue → slice_issues → {pr_opened → verdict_rounds → merged → slice_closed}* → prd_closed` — a strict subgraph of the declared 11-stage pipeline. 7 of 11 declared stages are fully recoverable with timestamps; grill/prd-critic/slicer-critic/qa-tester are recoverable only as inter-artifact time-gaps or occasional ad-hoc comments. The cheapest way to close those gaps is NOT runtime hooks but **making the orchestrator post each critic's existing CRITIC trailer as an issue comment** (prd-critic → PRD issue, slicer-critic → PRD issue, qa-tester → PRD issue) — the pattern already exists organically on PRDs #552/#574/#557, it just isn't mandated.

## KEY FACTS
- PRD #640: createdAt 2026-06-09T14:39:47Z, closedAt 15:31:00Z, label prd, 1 comment (completion summary at 15:30:59Z). Total pipeline wall-time 51m13s.
- Native sub-issue API works: GraphQL issue(640).subIssues returns exactly #641 (created 14:51:13Z), #642 (14:51:16Z), #643 (14:51:20Z), all label slice — deterministic PRD→slice linkage, no body parsing needed.
- Slice→PR mapping via GraphQL closingIssuesReferences is exact: PR 644→#641, PR 645→#642, PR 646→#643. Timeline cross-references are noisy (PR #644 cross-refs all 3 slices because its body mentions them) — do not use xrefs for mapping.
- Full per-slice trail with timestamps verified: e.g. slice #641 posted 14:51:13Z → PR #644 (feat/641-hook-fire-beacon) opened 14:59:04Z → reviewer APPROVE round 1 comment 15:04:22Z → merged 15:04:31Z → slice ClosedEvent 15:04:32Z + referenced-commit event c168e9f.
- Reviewer verdicts live as plain PR issue-comments with a fenced CRITIC trailer (VERDICT/REASON/ROUND/ESCALATE/MERGE_STATUS) — regex 'VERDICT: (\w+)' / 'ROUND: (\d+)' parsed 38 of 40 recent merged PRs successfully via one GraphQL query.
- Multi-round review trails are recoverable with timestamps: PR #556 opened 23:12:48Z → BLOCK @23:17:34Z → APPROVE @23:22:15Z → merged 23:22:21Z. PRs #565, #609, #617 also show BLOCK→round-2→APPROVE.
- DEFECT: PR #650 (merged 2026-06-10T15:49:07Z, closes #649, no labels) has ZERO reviewer-verdict comments — the reviewer gate left no artifact, so artifact-based measurement would correctly flag it as an unreviewed merge.
- CRITIC trailer schema drifts: PR #559's trailer has BLOCK_FINDINGS/PR/SLICE/PRD/MERGE_STATUS/ESCALATE but no ROUND field; older PRs parse VERDICT but not ROUND.
- Slice issues carry zero comments (verified #641: []) — slicer-critic rounds leave NO artifact anywhere; only the 11m26s gap between PRD createdAt and slice createdAt measures the whole to-issues stage.
- prd-critic/adr-critic verdicts appear as PRD-issue comments only on macro-ADR PRDs: 'Joint prd+adr-critic gate: PASSED' found on PRD #552 and #574 (2 of 15 closed PRDs sampled). Production-verify PASS posted as PRD comment on #557 only.
- needs-human-check label exists in the repo but zero issues (open or closed) have ever carried it — the qa-plan residual artifact surface is unexercised.
- Agent provenance is recoverable from git, not GitHub: all issues/PRs/comments are authored by vojtech-stas (single token), but every agent commit carries 'Co-authored-by: Claude Opus 4.8 (1M context) <noreply@anthropic.com>' trailer (verified c168e9f, e91fca2, bef9df3).
- Performance: ONE batched GraphQL query returning the complete PRD #640 trail (issue+comments+subIssues+timelineItems+PRs+PR comments) took 0.816s real, 46,655 bytes, ~1 GraphQL point. Rate limits: REST 5000/hr (11 used), GraphQL 5000 points/hr (204 used), search 30/min.
- Reliability: ~3 of ~20 gh calls returned transient 'HTTP 401: Requires authentication' despite healthy keyring auth (Windows gh keyring flap); immediate retry always succeeded — a collector needs retry-once-on-401 logic.
- PRD #640's slices executed strictly serialized: each next PR opened ~5-7 min after the previous merge (645 opened 15:09:56 vs 644 merged 15:04:31; 646 opened 15:21:44 vs 645 merged 15:14:51).

## DEFECTS
- [major] PR #650 (vojtech-stas/project-claude, merged 2026-06-10T15:49:07Z): Merged with zero reviewer-verdict comments and no labels (not trivial-laned either) — the reviewer gate produced no artifact, violating the review-trail invariant every other recent merged PR satisfies (38/40 have verdict comments). Either the gate was bypassed or the verdict was never posted.
- [major] Pipeline stages: grill-me, prd-critic rounds, slicer-critic rounds, qa-tester runs: Leave no GitHub artifact at all in the default flow (verified: slice #641 has 0 comments; 13/15 closed PRDs have no critic-verdict comment). These stages are unmeasurable from artifacts — the declared==measured comparison can never close for them without a posting convention change.
- [minor] CRITIC trailer format across PR comments (e.g. PR #559 vs PR #645): Trailer field schema drifts between PRs: #645 has VERDICT/REASON/ROUND/ESCALATE/MERGE_STATUS, #559 has VERDICT/BLOCK_FINDINGS/PR/SLICE/PRD/MERGE_STATUS/ESCALATE with no ROUND. Round-count extraction silently fails on the older variant.
- [minor] needs-human-check label (repo label list): Label exists but has never been applied to any issue (open or closed) — the qa-plan PROVISIONAL-residual artifact path described in the skill has never produced an artifact, so qa coverage cannot be measured from it.
- [minor] gh CLI on this Windows host (keyring auth): Transient HTTP 401 on ~15% of API calls despite valid token (gh auth status healthy, immediate retry succeeds) — any collector script without retry logic will flake.

## OPPORTUNITIES
- Build tools/measured-trail.py (or dashboard/ collector): one GraphQL query per PRD — issue(n){createdAt closedAt comments subIssues{createdAt closedAt timelineItems(CLOSED_EVENT, CROSS_REFERENCED_EVENT)}} plus closingIssuesReferences per PR for the slice mapping. Verified 0.816s/PRD cold; cache closed PRDs forever (immutable, key on closedAt); retry-once on transient 401. This gives the dashboard a real 'measured' graph with zero hook dependency.
- Replace the hook-derived 'measured' topology on the Live tab with the artifact-derived per-PRD flow: prd_posted → slices_posted → per-slice (pr_opened → verdict rounds w/ BLOCK count → merged → closed) → prd_closed, including stage durations (review latency = verdict comment ts − PR createdAt; verified 5m18s for PR #644).
- Close the unmeasurable-stage gap by convention, not hooks: mandate that /ship posts each critic's existing CRITIC trailer as an issue comment (prd-critic + slicer-critic verdicts → PRD issue comment; qa-tester PASS → PRD issue comment). The pattern already exists organically on PRDs #552/#574/#557 — standardizing it raises artifact coverage from 7/11 to ~10/11 declared stages at the cost of one gh call per verdict.
- Standardize the CRITIC trailer schema (fixed key set, always include ROUND) and add a deterministic check to tools/ci-checks.sh or the reviewer rubric so collector parsing never silently drops rounds (PR #559-style drift).
- Add an 'unreviewed merge' detector to the collector: any merged PR with no VERDICT comment and no trivial label (like PR #650) is itself a workflow-violation finding the dashboard should surface.
- Use git log as the cross-check layer: squash-commit subjects carry the PR number '(#644)' and Co-Authored-By trailers carry agent identity — join git log to the GitHub trail to verify merge integrity and agent provenance per slice without any extra API calls.
