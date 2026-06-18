---
id: ADR-0073
status: Accepted
supersedes: []
superseded_by: []
---

# ADR-0073: CLAUDE.md as the generated brain-spec — rules-location convention + generated repo-map

- **Status:** Accepted (joint APPROVE per [ADR-0004](0004-bypass-prevention.md) D1; shipped with PRD #937 slice #938)
- **Date:** 2026-06-18
- **Extends:** [ADR-0034](0034-build-orchestrator-and-generated-docs.md) D4 (generated-docs currency model — applied here to CLAUDE.md, not just README) + D5 (`R-DOCS-CURRENT` regen-and-diff gate — extended to CLAUDE.md generated regions) + D7 (doc-generator is a tooling artifact — the repo-map reuses the same `discover_*` engine); [ADR-0043](0043-claude-md-restructure.md) D1 (CLAUDE.md section structure — the generated regions slot into it); [ADR-0064](0064-rule-layer-integrity.md) D3 (one rubric implementation: health.py as the check registry — this ADR is the analogous single-source decision for the *rules-generation* engine `tools/gen_rules.py`, first introduced unADR'd in PRD #888); [ADR-0004](0004-bypass-prevention.md) D2 (bootstrap-mode).

## Context

CLAUDE.md is auto-loaded by Claude Code on every session — it is the closest thing the project has to Claude's working memory / "brain-spec". PRD #888 added `tools/gen_rules.py`, which generates atomic rules from non-superseded ADR frontmatter into `.claude/rules/<scope>.md` — but it shipped with **no ADR**, and it generated **all 12 scopes into always-loaded `.claude/rules/` files** while CLAUDE.md merely points at them in prose. None of the rule files carry `paths:` frontmatter, so all 12 load unconditionally regardless of relevance.

The operator, in a 2026-06-18 design review, settled the intended convention: the **load-bearing, always-relevant rules belong IN CLAUDE.md** (the brain-file the model always reads); a rule **earns its own `.claude/rules/` file only when it is path-scoped** — because the single real advantage of a separate rules file is that Claude Code can load it **only when the relevant files are being edited** (`paths:` frontmatter), saving always-on context. The operator also wants CLAUDE.md to carry a **generated repo-map** (a "README-for-Claude": each skill/agent/tool/dir → link + short description), generated so it never goes stale.

## Decisions

### D1: Rules-location convention — global rules in CLAUDE.md, area rules path-scoped

Every rule scope is classified GLOBAL or AREA. GLOBAL (always-relevant) scopes are generated into CLAUDE.md (via a CLAUDE.md generated region or an `@import`-ed generated file; this PRD uses `@import`-ed generated files) so the load-bearing rules live in the always-loaded brain-file. AREA (context-specific) scopes are generated into `.claude/rules/<scope>.md` carrying `paths:` frontmatter, so Claude Code loads them only when editing matching files. **A scope earns a separate path-scoped rules file only when it is path-scoped**; unconditional rules belong in CLAUDE.md. This reshapes PRD #888 (which put every scope in an unconditionally-loaded `.claude/rules/` file). A scope is EITHER global OR area — never both (no double-load).

### D2: CLAUDE.md is the generated brain-spec — global rules + generated repo-map, drift-gated

CLAUDE.md's mechanical content (the global rules of D1, plus a **generated repo-map table** — one row per discovered skill/agent/tool/dir with a link + short description) is **generated, never hand-maintained**, applying [ADR-0034](0034-build-orchestrator-and-generated-docs.md) D4's generated-docs-currency model to CLAUDE.md. The repo-map reuses the existing `discover_*` engine behind `dashboard/server.py --generate-readme` (ADR-0034 D7 — no LLM, no new dependency). Staleness is caught by a CLAUDE.md regen-and-diff CI check mirroring the README regen-clean gate (extends [ADR-0034](0034-build-orchestrator-and-generated-docs.md) D5). Hand-written prose (how-Claude-behaves, the numbered cross-cutting constraints' intent) remains hand-authored within [ADR-0043](0043-claude-md-restructure.md) D1's section structure; only the mechanical regions are generated.

### D3: `tools/gen_rules.py` owns the scope→target classification (single source)

The GLOBAL-vs-AREA classification is an explicit declared map inside `tools/gen_rules.py` — the single source for rules-generation targeting, analogous to [ADR-0064](0064-rule-layer-integrity.md) D3 making health.py the single check-registry. `gen_rules.py --check` remains the regen-clean dry-run. This ADR is also the first ADR of record for the PRD #888 `gen_rules.py` subsystem (which previously had none).

### D4: Bootstrap-mode — forward-binding, one-time migration

Per [ADR-0004](0004-bypass-prevention.md) D2 this convention binds forward. The existing 12 scopes are migrated once across this PRD's slices (global → CLAUDE.md, area → path-scoped); it is not a retroactive sweep beyond that one migration. Future scopes adopt the convention from this ADR forward.

### D5: No rule without a check (rule #23 compliance)

The convention is mechanically enforced — not advisory: `gen_rules.py --check` plus the new CLAUDE.md regen-and-diff CI check (D2) fail any drift between ADR frontmatter and the generated CLAUDE.md regions / path-scoped rule files. The rule-id conservation invariant (no rule lost in relocation) is a checkable count assertion in the same PRD. This satisfies rule #23 (every new convention ships with a deterministic check).

**Parsimony — why a new check is needed.** The pre-existing `gen_rules.py --check` (PRD #888) validates only that the generated rule *files* match ADR frontmatter; it does NOT inspect CLAUDE.md at all, and R-DOCS-CURRENT (ADR-0034 D5) gates only `README.md`. Neither covers CLAUDE.md's newly-generated regions (the global-rules region + the repo-map). A separate CLAUDE.md regen-and-diff CI check — mirroring the README gate — is the minimal addition that closes this specific uncovered surface; no existing check spans it.

**Shadow it guards.** The anti-pattern this enforcement prevents is *context-overload drift*: an AREA-scoped rule file shipping without its `paths:` gate (so it loads unconditionally, re-creating the exact PRD #888 starting condition), or a load-bearing GLOBAL rule silently absent from the always-loaded CLAUDE.md brain-file, or the repo-map silently going stale against the filesystem. The regen-and-diff check turns each of these silent drifts into a loud CI failure.

## Consequences

- The load-bearing rules are where the model actually reads them (CLAUDE.md), while area rules stop consuming always-on context and surface only when their files are edited — better signal-to-noise in every session's working memory.
- CLAUDE.md gains a drift-proof repo-map; "what skill/agent does X" is answerable from the always-loaded brain-file without grepping.
- Drift becomes mechanically impossible for CLAUDE.md's generated content (regen-and-diff gated at CI), as it already is for README.
- CLAUDE.md must stay skimmable (official <200-line guidance): large generated tables are `@import`-ed rather than inlined if the line budget is threatened.
- Editing a rule's content still means editing the source ADR's frontmatter + regenerating — unchanged from #888; only the generation TARGET (CLAUDE.md vs path-scoped file) is newly differentiated.

## Alternatives considered

- **Keep #888 as-is (all scopes always-loaded in `.claude/rules/`).** Rejected: ignores the operator's decided convention; wastes always-on context on rules irrelevant to the current edit; the brain-file (CLAUDE.md) does not actually contain the load-bearing rules, only pointers.
- **Put ALL rules back inline in CLAUDE.md (no `.claude/rules/` at all).** Rejected: loses path-scoped loading (the one genuine advantage of separate files) and bloats CLAUDE.md past the skimmable budget.
- **Hand-maintain the repo-map.** Rejected: the exact drift problem ADR-0034 D4 solved for README; a generated table is drift-proof.
- **A queryable ADR/effective-decision resolver instead of generated-into-CLAUDE.md.** Deferred (operator: "too big") — orthogonal long-term upgrade, not a substitute for the always-loaded brain-file.

## References

- PRD #888 (gen_rules.py + `.claude/rules/` — the subsystem this ADR documents + reshapes)
- [ADR-0034](0034-build-orchestrator-and-generated-docs.md) D4/D5/D7 — generated-docs currency model + regen-and-diff gate + shared generator engine
- [ADR-0043](0043-claude-md-restructure.md) D1 — CLAUDE.md section structure
- [ADR-0064](0064-rule-layer-integrity.md) D3 — health.py as the single check registry (the analogous single-source decision)
- [ADR-0004](0004-bypass-prevention.md) D1 (joint-APPROVE gate) + D2 (bootstrap-mode)
- code.claude.com/docs/en/memory — CLAUDE.md auto-load, `@import`, `.claude/rules/` `paths:` scoping
