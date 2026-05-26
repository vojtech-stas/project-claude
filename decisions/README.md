# Architecture Decision Records (ADRs)

This directory holds the project's design decisions — the *why* behind structural choices that aren't obvious from the code.

## What an ADR is

An ADR captures **one architectural decision** along with the context that drove it, the alternatives that were considered and rejected, and the consequences accepted. Originated in Michael Nygard's *"Documenting Architecture Decisions"* (2011); now standard practice at Spotify, AWS, ThoughtWorks, HashiCorp, Kubernetes, and many open-source projects.

An ADR is a **historical record**, not a living spec. Once accepted, it's frozen at the moment of decision. If the decision is later reversed or refined, a *new* ADR supersedes the old one — the old one is never edited (only its `Status` may flip to `Superseded`).

## Why one file per decision

- **Immutability.** Each ADR is the snapshot of a decision in its moment. Editing it retroactively destroys the audit trail of "what was true *when*."
- **Granular supersession.** A new ADR can supersede *one specific decision* from an older one without invalidating the rest.
- **Git history per decision.** `git log decisions/0042-*.md` tells you exactly when that decision changed and why.
- **Stable links.** PRs, code comments, and CLAUDE.md can link to one specific ADR — the link doesn't rot when an unrelated decision changes.
- **Discoverability.** `ls decisions/` is your changelog — chronological order, decision titles visible.

The unit isn't quite "one tiny decision per file" — it's **one architectural pattern or coherent design move per file**. If a pattern has 5 inter-dependent rules (e.g., "autonomous pipeline with critics" has rules about stages, critics, options, gates, orchestrator), those go in one ADR. If a decision is independent ("use library X over Y for date parsing"), it gets its own ADR.

This project's [ADR-0001](0001-foundational-design.md) (13 decisions in one file) is intentionally a mega-ADR because the decisions were the *foundational set* — they're a coherent pattern, not 13 separate moves. ADR-0002 and ADR-0003 follow the same one-pattern-per-file rule.

## Conventions

- **Filename:** `NNNN-<kebab-case-slug>.md`, sequentially numbered.
- **Status values:** `Proposed`, `Accepted`, `Superseded by ADR-NNNN`, `Deprecated`.
- **Required sections:** Status / Date / Context / Decisions / Consequences / Alternatives considered.
- **Optional sections:** Open questions deferred, Future direction, References.

## When to write an ADR

Heuristic — write one when at least one of these is true:

- The decision was **hard to make** (real trade-offs surfaced; multiple valid paths existed).
- The decision **constrains future work** (other decisions depend on this one).
- A future maintainer would ask **"why did they do it this way?"** without explanation.

Don't write one for trivial choices (naming a variable, picking a CSS color). Those belong in the code or commit message.

## When in the pipeline ADRs are written

Per [ADR-0003](0003-autonomous-pipeline-with-critics.md) D8:

- **Macro-ADRs** — at the `grill-me → to-prd` boundary. The grill session surfaces architectural decisions; `to-prd` drafts both the PRD and any warranted ADRs. They ship together in slice 1 of the implementation.
- **Micro-ADRs** — during implementation. If an implementer hits an unexpected design decision mid-build, it writes an ADR inline with that slice. The `reviewer` subagent enforces.

## Index

| ADR | Title | Status |
|---|---|---|
| [0001](0001-foundational-design.md) | Foundational design | Accepted (D3 and D6 partially superseded by 0003; D9 superseded by 0002) |
| [0002](0002-autonomous-merge-policy.md) | Autonomous merge policy with QA-level human checkpoint | Accepted |
| [0003](0003-autonomous-pipeline-with-critics.md) | Autonomous multi-stage pipeline with adversarial critics | Accepted (supersession-header D-ID error, D4/D6 contradiction on `to-prd` semantics, missing bootstrap-mode policy, and undocumented implementer-stage incremental rollout corrected by [ADR-0004](0004-bypass-prevention.md) D5; D3 partially superseded by [ADR-0013](0013-slicer-n3-contract-refined.md) — N=3 default + N=1 degenerate-case carveout) |
| [0004](0004-bypass-prevention.md) | Bypass prevention — workflow enforcement, adr-critic, and meta-output discipline | Accepted |
| [0005](0005-output-shape-and-slicing-methodology.md) | Output-shape standard for subagents + slicing methodology depth | Accepted |
| [0006](0006-backlog-and-session-continuity.md) | Backlog queue + session continuity (live-state reconstruction, no formal handoff) | Accepted |
| [0007](0007-vocabulary-glossary-and-grill-me-extension.md) | Universal vocabulary mechanism — two-tier glossary + /grill-me extension | Accepted (D1 superseded by 0012, D5 partially superseded by 0012 D4) |
| [0008](0008-workflow-autolog-bootstrap-and-naming.md) | Workflow polish — auto-log captured→backlog autopilot + bootstrap.sh + naming convention | Accepted (D2 asymmetric-default-BLOCK generalized to all critics by [0009](0009-discipline-tightening.md) D3) |
| [0009](0009-discipline-tightening.md) | Discipline tightening — universal rule #10, mandatory rule #11, asymmetric-default-BLOCK + distinct mindsets across all critics | Accepted (supersedes [0004](0004-bypass-prevention.md) D4 and [0006](0006-backlog-and-session-continuity.md) D4; rule #11 forward-work scope preserved, rule #13 root-cause-shape scope added per [ADR-0024](0024-root-cause-workflow-capture-discipline.md) D2 division of labor) |
| [0010](0010-implementer-subagent-auto-pipeline.md) | Implementer subagent + /ship auto-invoke closes ADR-0003 D4's autonomy gap | Accepted |
| [0011](0011-subagent-quality-framework.md) | Subagent-quality framework — `/audit-subagents` skill + mechanical/grep rubric | Accepted |
| [0012](0012-glossary-consolidation-single-tier.md) | Glossary consolidation — single-tier in CLAUDE.md (supersedes 0007 D1, partial 0007 D5) | Accepted (D6 superseded by 0014 — skill-local vocab + /glossary-fold) |
| [0013](0013-slicer-n3-contract-refined.md) | Slicer N=3 contract refined — N=1 reserved for degenerate end-state cases (partial supersession of [ADR-0003](0003-autonomous-pipeline-with-critics.md) D3) | Accepted |
| [0014](0014-skill-local-vocabulary-and-auto-fold.md) | Skill-local vocabulary sections + `/glossary-fold` auto-fold (supersedes [ADR-0012](0012-glossary-consolidation-single-tier.md) D6 deferral) | Accepted |
| [0015](0015-claude-code-hooks-adoption.md) | Claude Code hooks adoption + walking-skeleton PostToolUse logging hook | Accepted (D6 partially fulfilled by ADR-0023 — validation + SessionStart additions; D2 scope policy preserved unchanged) |
| [0016](0016-workflow-event-log-jsonl.md) | Workflow event log — JSONL via hooks (3 events: agent/bash/stop; extends [ADR-0015](0015-claude-code-hooks-adoption.md)) | Accepted |
| [0017](0017-audit-meta-consolidation.md) | Audit-meta consolidation — `/audit-meta` skill with subcommand architecture (sibling to `/audit-subagents`) | Accepted |
| [0018](0018-boy-scout-reviewer-rule.md) | R-BOY-SCOUT reviewer rule — per-PR drift detection on audit-relevant files (extends [ADR-0002](0002-autonomous-merge-policy.md) reviewer rubric; consumes [ADR-0011](0011-subagent-quality-framework.md) + [ADR-0017](0017-audit-meta-consolidation.md) rubrics inline) | Accepted |
| [0019](0019-best-practices-kb-pattern.md) | External-content ingestion pattern + `docs/best-practices/` doc tree (extends [ADR-0001](0001-foundational-design.md) D8 orientation artifacts, [ADR-0005](0005-output-shape-and-slicing-methodology.md) D3 cascade-doc check, [ADR-0008](0008-workflow-autolog-bootstrap-and-naming.md) D6 bootstrap.sh, [ADR-0011](0011-subagent-quality-framework.md) D5 single-Markdown-report precedent) | Accepted (D3 superseded by ADR-0022 D11) |
| [0020](0020-qa-automation-writer-executor.md) | QA automation Tier 1 — writer/executor split + `qa-tester` subagent (extends [ADR-0003](0003-autonomous-pipeline-with-critics.md) D4 terminal human checkpoint, [ADR-0005](0005-output-shape-and-slicing-methodology.md) D1c GENERATOR trailer, [ADR-0008](0008-workflow-autolog-bootstrap-and-naming.md) D7 6-critic-cap honored) | Accepted (D3 narrowed by ADR-0025 D1 — dual bash-mode + ui-mode) |
| 0021 | _Skipped — see note below_ | — |
| [0022](0022-docs-first-kb-pattern.md) | Docs-first per-topic best-practice skills + Phase 2' audit pattern (supersedes [ADR-0019](0019-best-practices-kb-pattern.md) D3 yt-dlp-only; extends [ADR-0011](0011-subagent-quality-framework.md) D2/D5, [ADR-0008](0008-workflow-autolog-bootstrap-and-naming.md) D7 6-critic-cap honored) | Accepted |
| [0023](0023-validation-and-notification-hooks-extension.md) | Validation and notification hooks extension — SessionStart state injection + PreToolUse blocking (partially fulfills [ADR-0015](0015-claude-code-hooks-adoption.md) D6) | Accepted |
| [0024](0024-root-cause-workflow-capture-discipline.md) | Root-cause workflow capture discipline — CLAUDE.md cross-cutting rule #13 (extends [ADR-0009](0009-discipline-tightening.md) D2 rule #11 with sibling backward/root-cause-shape rule; honors [ADR-0008](0008-workflow-autolog-bootstrap-and-naming.md) D3/D4/D7) | Accepted |
| [0025](0025-qa-tester-ui-mode-playwright.md) | qa-tester subagent extension — Playwright MCP ui-mode for screenshot-judged acceptance testing (partial supersession of [ADR-0020](0020-qa-automation-writer-executor.md) D3) | Accepted |
| [0026](0026-knowledge-architecture-truth-docs.md) | Knowledge architecture — per-topic materialized truth-docs + current-state-reader subagent + topic-aware UserPromptSubmit hook + R-TRUTH-DOC reviewer rule (extends [ADR-0023](0023-validation-and-notification-hooks-extension.md) D5/D7, [ADR-0011](0011-subagent-quality-framework.md) D4, [ADR-0008](0008-workflow-autolog-bootstrap-and-naming.md) D7 6-critic-cap honored) | Accepted |
| [0027](0027-subagent-model-selection.md) | Subagent model selection — Sonnet 4.6 / Haiku two-tier assignment policy + capability truth-doc (extends [ADR-0001](0001-foundational-design.md) D6, [ADR-0008](0008-workflow-autolog-bootstrap-and-naming.md) D7 6-critic-cap honored, [ADR-0026](0026-knowledge-architecture-truth-docs.md) D7 bootstrap-mode forward) | Accepted |
| [0028](0028-pretooluse-spec-gate.md) | PreToolUse spec-existence gate — artifact-gated tracked-file edits (extends [ADR-0023](0023-validation-and-notification-hooks-extension.md) D3, [ADR-0026](0026-knowledge-architecture-truth-docs.md) R-TRUTH-DOC, [ADR-0008](0008-workflow-autolog-bootstrap-and-naming.md) D7 6-critic-cap honored) | Accepted |
| [0029](0029-stop-reviewer-signoff-gate.md) | Stop hook reviewer-signoff gate — block session-stop if in-flight PR lacks reviewer APPROVE (extends [ADR-0002](0002-autonomous-merge-policy.md), [ADR-0010](0010-implementer-subagent-auto-pipeline.md) D2+D3, [ADR-0026](0026-knowledge-architecture-truth-docs.md) R-TRUTH-DOC, [ADR-0008](0008-workflow-autolog-bootstrap-and-naming.md) D7 6-critic-cap honored) | Accepted |
| [0030](0030-windows-gitbash-hardening.md) | Cross-platform Windows Git Bash hardening — jq + Playwright install + hook allowlist fix + SessionStart warning (extends [ADR-0008](0008-workflow-autolog-bootstrap-and-naming.md) D6, [ADR-0023](0023-validation-and-notification-hooks-extension.md) D2+D3, [ADR-0025](0025-qa-tester-ui-mode-playwright.md) D7 completion, [ADR-0026](0026-knowledge-architecture-truth-docs.md) R-TRUTH-DOC, [ADR-0028](0028-pretooluse-spec-gate.md) D1+D2 preserved, [ADR-0008](0008-workflow-autolog-bootstrap-and-naming.md) D7 6-critic-cap honored) | Accepted |
| [0031](0031-knowledge-architecture-v2.md) | Knowledge architecture v2 — Karpathy compiler + atomic notes + typed edges + LLM-as-maintainer (supersedes [ADR-0026](0026-knowledge-architecture-truth-docs.md) D1+D3; preserves [ADR-0026](0026-knowledge-architecture-truth-docs.md) D2+D5+D6; extends [ADR-0017](0017-audit-meta-consolidation.md) D7 + [ADR-0018](0018-boy-scout-reviewer-rule.md) D7 cadence question; honors [ADR-0008](0008-workflow-autolog-bootstrap-and-naming.md) D7 6-critic-cap + [ADR-0004](0004-bypass-prevention.md) D2 bootstrap-mode) | Accepted |

> **Note on ADR-0021:** Drafted alongside PRD #171 (Phase 1.5 video synthesis) which was closed without merging on 2026-05-22 (strategic pivot to docs-first KB, realized as [ADR-0022](0022-docs-first-kb-pattern.md)). ADR-0021 was never committed; the numbering gap is intentional residue. Next-unused ADR after ADR-0020 is ADR-0023 (ADR-0021 remains permanently skipped per [ADR-0001](0001-foundational-design.md) D8 numbering-at-acceptance).
