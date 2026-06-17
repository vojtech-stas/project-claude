---
id: "ADR-0034"
status: "accepted"
supersedes: []
superseded_by: []
scope: "docs"
rule_ids:
  - "DOC-001"
  - "DOC-002"
---
# ADR-0034: Unified `/build` orchestrator + generated-docs currency model

- **Status:** Accepted
- **Date:** 2026-05-30
- **Supersedes:** none
- **Extends:** [ADR-0003](0003-autonomous-pipeline-with-critics.md) D7 (`/ship` orchestrator skill — `/build` is the full-lifecycle evolution per D1 below; `/ship` preserved as the autonomous-middle sub-skill); [ADR-0003](0003-autonomous-pipeline-with-critics.md) D2 (five-stage pipeline — `/build` provides a single entry point spanning all five stages; the stages themselves are unchanged); [ADR-0003](0003-autonomous-pipeline-with-critics.md) D6 (skills for human-facing stages, subagents for autonomous stages — `/build` straddles both by conducting HITL + autonomous stages through one command); [ADR-0003](0003-autonomous-pipeline-with-critics.md) D8 (macro-ADR placement — this ADR ships in PRD #348 slice 1 per D8's grill→to-prd-boundary convention); [ADR-0010](0010-implementer-subagent-auto-pipeline.md) D2 (`/ship` auto-invokes implementer — preserved; `/build` wraps `/ship` which still does this); [ADR-0004](0004-bypass-prevention.md) D3 (workflow enforcement stack — extended with R-DOCS-CURRENT reviewer rule + pre-commit doc-generation check per D5/D6 below); [ADR-0002](0002-autonomous-merge-policy.md) (autonomous merge — R-DOCS-CURRENT joins the reviewer's hard-block rule set); [ADR-0008](0008-workflow-autolog-bootstrap-and-naming.md) D7 (6-critic-cap meta-rule — preserved per D8: R-DOCS-CURRENT is a rule, not a critic); [ADR-0004](0004-bypass-prevention.md) D2 (bootstrap-mode policy — cited by D9); [decisions/README.md](README.md) "What an ADR is" (ADR immutability — preserved; extension via supersession mechanism)

## Context

This project's autonomous pipeline (ADR-0003) exposes three commands the human invokes in sequence: `/grill-me` (define the what — HITL), `/ship` (autonomous middle — to-prd → critics → to-issues → slicer → implementer → reviewer → merge), `/qa-plan` (verify — HITL). Two human touch-points, autonomous middle.

Two recurring pains, surfaced repeatedly during the 2026-05-29 session:

1. **Fragmented UX.** The human manually transitions between `/grill-me` → `/ship` → `/qa-plan`. The user wants ONE command that drives the full lifecycle, deciding internally when to grill vs skip, running the autonomous pipeline, and surfacing QA — without manual re-engagement at each boundary. (User mandate: "one orchestrator and all other skills... replace the ship so we have all in one.")

2. **Documentation drift.** README and other human-facing docs drift from reality because they're hand-maintained in parallel with the canonical sources (`.claude/agents/`, `.claude/skills/`, `.claude/hooks/`, `decisions/`). Concrete instance: PR #333 fixed a README that had gone stale relative to the T6 CLAUDE.md slim + the ADR-0028/0029/0030/0031 wave. The drift sat undetected because no mechanism re-derives README from sources or blocks stale README from merging.

Research (2026-05-29 grill + web search) converged on established patterns:
- **Skill chaining / Command→Skill orchestration**: a thin orchestrator command owns workflow logic; sub-skills stay atomic; Claude is the coordinator ([MindStudio skill-collaboration pattern]; [shanraisshan/claude-code-best-practice orchestration-workflow]). *"A common pattern is a ship skill that calls qa, review, then deploy in sequence."*
- **Generate-and-embed docs**: derive mechanical doc content (diagrams, maps, counts) from a single source (the filesystem) + a template with static prose + injection points (terraform-docs, doctoc, Hugo, Sphinx, mkdocs). Output is a build artifact, regenerate-and-diff-gated.
- **Karpathy compiler insight** (cited throughout the session): the artifact a human reads should be COMPILED from canonical sources, not hand-maintained in parallel.

The 2026-05-29 design grill (5 questions, all resolved) locked the architecture this ADR codifies.

## Decisions

### D1: Unified `/build` orchestrator — thin Command→Skill wrapper spanning the full lifecycle

A new skill `/build` is the single everyday entry point for "implement or grill something." It is a **thin orchestrator** (~60-80 LoC) that invokes the existing atomic skills in sequence via the Skill tool, checking each result before proceeding:

1. **Ensure dashboard running** (idempotent) — reuse the dashboard auto-start mechanism (`.claude/hooks/dashboard-autostart.sh`, shipped by PRD #345 slice 2): check `localhost:8765`, spawn the dashboard if not running, no-op if already up. This guarantees the dashboard's Live tab is available to watch the build in real time when `/build` runs — even in a session where SessionStart's spawn failed or was bypassed. (SessionStart *also* auto-starts the dashboard per PRD #345/ADR-0033; this step is the orchestrator-coupled guarantee per the 2026-05-29 dashboard-trigger decision — "both triggers, same idempotent mechanism.")
2. **Assess + grill** (conditional per D3) — `/grill-me` if the input is vague
3. **Ship** — `/ship` (the existing autonomous middle per ADR-0003 D7 + ADR-0010 D2; unchanged)
4. **Regenerate docs** — run the doc-generator (per D4) as a pipeline step so the PR arrives doc-current
5. **QA** — `/qa-plan` (HITL acceptance)

Because step 1 reuses `dashboard-autostart.sh`, the implementing PRD sequences AFTER PRD #345 slice 2 (which ships that script) — consistent with the broader sequencing in Alt-I.

`/build` owns ONLY the chaining logic + HITL-checkpoint transitions. It does NOT reimplement grill/ship/qa logic. This is the Command→Skill architecture: the orchestrator conducts; the sub-skills are the atomic players. Extends ADR-0003 D7 (`/ship` was the lightweight-v1 orchestrator; `/build` is the full-lifecycle conductor that wraps it).

### D2: Sub-skills remain atomic and individually invocable

`/grill-me`, `/ship`, `/qa-plan` are NOT absorbed or deleted. They remain standalone skills, individually invocable for direct/advanced use (e.g., re-running just `/qa-plan` on a merged PRD, or `/ship`-ing a pre-grilled spec). `/build` is the convenience conductor layered on top; the atomic skills are the substrate. This honors the research's "keep each skill atomic, single-purpose" principle and avoids the fat-orchestrator anti-pattern.

### D3: Grill-conditional — auto-assess + announce + proceed (no blocking question)

`/build` judges input concreteness (Claude as coordinator): is there enough to write a mechanically-verifiable PRD §2 without more questions? It STATES its call ("Input is captured issue #X with symptom+root-cause+proposed-fix — concrete; skipping grill, proceeding to PRD") and proceeds **without a blocking confirmation question**. The human may redirect mid-flow. This honors BOTH the project's "skip grill for fully-concrete captures" convention (CLAUDE.md autonomy-cadence memory) AND "never ask 'should I continue?'" — Claude makes the reasonable call, announces it, keeps going, accepts redirection.

### D4: Generated-docs currency model — README is a build artifact

The README (and any future human-facing doc with mechanical content) is **generated**, not hand-maintained:

- **Source of truth**: `docs/readme.template.md` — static hand-written prose (intro, "what's the idea", FAQ — the human voice) + `{{GENERATED:*}}` injection points for mechanical content (pipeline diagram, component map, counts).
- **Mechanical content**: derived from the filesystem (`.claude/agents/`, `.claude/skills/`, `.claude/hooks/`, `.claude/settings.json`, `decisions/`) by the doc-generator (D7). Re-derived every run → cannot drift.
- **Output**: `README.md` — a build artifact. Committed (so GitHub renders it) but never hand-edited. Carries a header comment: `<!-- AUTO-GENERATED from docs/readme.template.md — edit the template, run the generator. -->`.
- **Dashboard**: the workflow dashboard (PRD #345) renders the same generator output → also self-current.

This is the generate-and-embed pattern (terraform-docs/Hugo/Sphinx family). Mechanical doc content becomes drift-proof by construction.

### D5: `R-DOCS-CURRENT` reviewer rule — the unbypassable currency gate

A new reviewer hard-block rule: on every PR, the reviewer regenerates `README.md` from `docs/readme.template.md` + the filesystem, then runs `git diff --exit-code README.md`. If the committed README differs from the freshly-generated one → **BLOCK**. This catches both drift modes: (a) someone hand-edited README.md, (b) a source changed but README wasn't regenerated. Because branch protection (ADR-0004 D3 R1+R2) forces everything through a reviewer-gated PR, this rule **guarantees** no stale README reaches `main`. Extends ADR-0002 (reviewer's hard-block rule set) + ADR-0004 D3 (workflow enforcement stack).

### D6: Pre-commit doc-generation check — fast local catch

`.githooks/pre-commit` (the server-side enforcement layer per ADR-0004 D3) is extended: on commit, regenerate README from template + filesystem; if it changed, block the commit with a message ("README out of sync — run the generator + re-stage"). This gives fast local feedback before PR time. It is the `.githooks/pre-commit` layer (server-side per ADR-0004 D3, runs for human + agent commits alike), NOT a Claude Code `.claude/hooks/` hook — so it is unrelated to ADR-0015 D2's hook scope policy.

Defense-in-depth (D5 + D6): pre-commit is the fast local catch; R-DOCS-CURRENT is the unbypassable gate (pre-commit can be `--no-verify`'d; the reviewer rule cannot).

### D7: Doc-generator is a tooling artifact

The doc-generator lives under `tools/` (e.g., `tools/generate-readme.py`) OR as a CLI mode of the dashboard server (`dashboard/server.py --generate-readme`) — implementer judgment, since the dashboard already contains the filesystem-reading engine (PRD #345 slice 1) and DRY favors sharing it. Either way it is a **tooling artifact**, non-runtime per `r-loc.md` omission semantics (the established treatment of `tools/*` and `dashboard/*` — files not in the runtime-artifact path set). It makes no LLM API calls; it reads files and emits Markdown.

### D8: 6-critic-cap honored per ADR-0008 D7

This ADR introduces no critic. `R-DOCS-CURRENT` (D5) is a RULE added to the existing `reviewer` subagent's rule set, not a new critic. The doc-generator (D7) is a tool, not a subagent. `/build` (D1) is a skill, not a critic. Critic count remains 6 (`reviewer`, `prd-critic`, `adr-critic`, `slicer-critic`, `glossary-critic`, `backlog-critic`).

### D9: Bootstrap-mode acknowledgment per ADR-0004 D2

The unified-orchestrator + generated-docs model binds **forward** from this ADR's merge. The existing README is migrated into `docs/readme.template.md` one time (implementing PRD slice 1); not a retroactive sweep. `/grill-me`, `/ship`, `/qa-plan` continue working standalone. Future docs that adopt the generate-and-embed model do so from this ADR forward.

### D10: Relationship to the dashboard tooling-spawn pattern — distinct, no overlap

The dashboard (PRD #345) introduces a *hook-spawned* observation-only background process (the dashboard server, auto-started on SessionStart). This ADR's doc-generator (D7) is fundamentally different: it is NOT hook-spawned and NOT long-running — it is invoked synchronously as a one-shot subprocess by the orchestrator step (D1.3), the pre-commit hook (D6), and the reviewer rule (D5). It runs, emits Markdown, exits. The two mechanisms do not overlap or conflict. ([ADR-0033](0033-tooling-spawn-hook-scope.md) — shipped via PRD #345 slice 2 (PR #350) — formalizes the dashboard's hook-spawn tooling carveout; this ADR's doc-generator is subprocess-invoked, not hook-spawned, so the two remain distinct and non-overlapping.)

## Consequences

### Positive

- **One command** (`/build`) drives the full lifecycle — the unified UX the user wanted
- **Drift becomes mechanically impossible** for generated doc content: re-derived from sources every run, regenerate-and-diff-gated at commit (D6) AND merge (D5). A stale README literally cannot merge — the structural drift-prevention sought across the entire 2026-05-29 session
- **Sub-skills stay atomic** (D2) — no fat-orchestrator anti-pattern; individually re-runnable when a stage needs a redo
- **Dashboard + README share one generator** (D7) — DRY; both self-current
- **Two human touch-points preserved** (ADR-0003 D2/D4 intent) — grill + qa become orchestrator checkpoints, not separate commands
- **6-critic-cap preserved** (D8)
- **Bootstrap-mode honored** (D9)

### Negative / Accepted

- **Hand-written prose in the template can still drift** — only the `{{GENERATED:*}}` regions are drift-proof; the static intro/FAQ prose is human-maintained. Accepted: this is the irreducible human-voice content; the cascade-finder/audit-meta verify-check (a future upgrade, the "1D" option from the grill) can be added later to catch stale prose references without rework.
- **README becomes a build artifact** — contributors must edit `docs/readme.template.md`, not `README.md`. Footgun (direct README edits get regenerated away) mitigated by D4's header comment + D5/D6's diff-gate + optionally a `PreToolUse(Edit)` warning redirecting README edits to the template.
- **Generator is a new maintenance surface** — when `.claude/` structure changes, the generator's discovery logic may need updating. Mitigated by sharing the dashboard's already-maintained engine (D7).
- **`/build` adds a skill to the inventory** — but a thin one (~60 LoC); the 4 atomic skills it wraps are unchanged.
- **Migration effort** — current README → template is a one-time slice-1 task; some hand-tuning to mark the generated regions.

## Alternatives considered

- **Alt-A: Expand `/ship` in place to span the full lifecycle (grill Q3 = 3A).** Rejected: produces a fat "god skill"; research is unanimous that orchestrators stay thin + players stay atomic.
- **Alt-B: Auto-chain skill transitions without a new orchestrator (grill Q3 = 3C).** Rejected: doesn't deliver the single-entry-point UX; human still starts at `/grill-me`.
- **Alt-C: Verify-only docs currency — cascade-finder/audit-meta blocking, no generator (grill Q1 = 1B).** Rejected: drift can land in a branch; duplication remains (README + dashboard diagrams compared, not unified); doesn't eliminate the hand-maintenance burden.
- **Alt-D: Dashboard is the sole source of truth; README points to it (grill Q1 = 1C).** Rejected: breaks the client-reads-README-on-GitHub use case (dashboard is localhost-only).
- **Alt-E: Marked-region injection into a hand-written README (grill Q2 = 2A).** Considered strong; user chose full-template (2B) for maximal drift-proofing of the whole document.
- **Alt-F: Frontmatter-driven README assembly (grill Q2 = 2C).** Rejected: adds `readme_summary` frontmatter to 24 files + doesn't handle the pipeline diagram.
- **Alt-G: Orchestrator-only currency enforcement (grill Q4 = 4D).** Rejected: only enforces currency for `/build`-driven PRs; manual hotfixes/trivial-lane escape — the exact gap that produced PR #333's drift.
- **Alt-H: Grill-conditional via explicit flag or input-routing (grill Q5 = 5C/5D).** Rejected: rigid; binds concreteness to flag/shape rather than content. 5A (auto-assess + announce) honors both autonomy preferences.
- **Alt-I: Build the orchestrator before finishing the in-flight KB collapse (PRD #341).** Originally deferred (the instinct was to build on the simplified post-#341 foundation); **chosen on 2026-05-30 per explicit user direction.** Safe because the doc-generator (D4/D7) reads only `.claude/{agents,skills,hooks,settings.json}` + `decisions/` — NOT `docs/current/` — so it has **zero dependency** on the KB layer PRD #341 deletes. One cross-constraint follows: when #341's teardown slice deletes `docs/`, it MUST preserve `docs/readme.template.md` (this ADR's new source-of-truth — a sibling of, not part of, the deleted KB). PRD #345 slice 2 (`dashboard-autostart.sh`, reused by D1 step 1) is already merged (PR #350), so that dependency is satisfied.

## Open questions deferred

- **OQ-1**: Doc-generator placement — `tools/generate-readme.py` vs `dashboard/server.py --generate-readme` mode — implementing PRD slice-1 implementer judgment (DRY favors sharing the dashboard engine).
- **OQ-2**: Whether to add the cascade-finder/audit-meta prose-verify check (the grill's "1D" upgrade) for hand-written template prose — future PRD if prose drift becomes a problem.
- **OQ-3**: Whether `/grill-me`, `/ship`, `/qa-plan` eventually get demoted to "internal — use `/build`" in docs while remaining invocable — defer; D2 keeps them first-class for now.
- **OQ-4**: `PreToolUse(Edit)` warning redirecting direct `README.md` edits to the template — optional hardening; implementing PRD slice judgment.
- **OQ-5**: Whether other generated docs (e.g., a future `ARCHITECTURE.md`) adopt the same template+generator model — forward-compatible; out of scope here.
- **OQ-6**: `/build` naming — `/build` vs `/work` vs `/do` vs keeping `/ship` as the name and adding the wrapper logic — implementing PRD picks; `/build` is the working name.

## Future direction

- Implementing PRD ships the 6 components (generator, template, `/build`, R-DOCS-CURRENT, pre-commit extension, this ADR) across ~4-5 slices
- The generate-and-embed model extends to any future human-facing doc with mechanical content
- The prose-verify upgrade (OQ-2) closes the last drift gap (hand-written prose) if needed
- Once `/build` is the everyday entry, the standalone sub-skills may be documented as "advanced/direct use" (OQ-3)

## References

- 2026-05-29 design grill — 5 questions resolved (Q1=1A, Q2=2B, Q3=3B, Q4=4C, Q5=5A); decisions captured in this ADR's D1-D6
- Web research (2026-05-29): [MindStudio skill-collaboration pattern](https://www.mindstudio.ai/blog/claude-code-skill-collaboration-pattern), [shanraisshan/claude-code-best-practice orchestration-workflow](https://github.com/shanraisshan/claude-code-best-practice), [Claude Code Dynamic Workflows docs](https://code.claude.com/docs/en/workflows)
- [ADR-0003](0003-autonomous-pipeline-with-critics.md) D2/D6/D7 — pipeline + orchestrator (extended)
- [ADR-0010](0010-implementer-subagent-auto-pipeline.md) D2 — `/ship` auto-invoke (preserved)
- [ADR-0004](0004-bypass-prevention.md) D2 (bootstrap), D3 (enforcement stack — extended), D4 (meta-output discipline — relevant to README-as-build-artifact)
- [ADR-0002](0002-autonomous-merge-policy.md) — reviewer hard-block rule set (extended with R-DOCS-CURRENT)
- [ADR-0008](0008-workflow-autolog-bootstrap-and-naming.md) D7 — 6-critic-cap (preserved)
- [ADR-0033](0033-tooling-spawn-hook-scope.md) (Accepted, PR #350, PRD #345 slice 2) — formalizes the dashboard's hook-spawn tooling carveout; distinct from this ADR's subprocess-invoked generator per D10
- PR #333 — the README staleness incident that motivates the currency model
- PRD #345 (dashboard) — shares the filesystem-reading engine per D7
- PRD #341 (workflow-only KB collapse) — originally sequenced before this ADR (Alt-I); reordered 2026-05-30 per user direction; #341's teardown slice must preserve `docs/readme.template.md`
