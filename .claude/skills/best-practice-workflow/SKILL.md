---
name: best-practice-workflow
description: On-demand authoritative guidance for Claude Code workflow questions — slash-commands, skill invocation, settings hierarchy, sub-agent vs skill choice, project structure. Auto-loads when the user asks "should I use a slash-command or a skill here?", "where do project settings go?", "how does Claude pick which skill to load?", "is this a subagent or a skill job?", "what belongs in CLAUDE.md vs in a skill?", or any similar workflow-shape question. Distilled from `docs.claude.com/en/docs/claude-code/{slash-commands,sub-agents,settings,skills,hooks-guide,overview}` per ADR-0022 D1 (4-section shape) with mechanical Grep+Target audit hooks per ADR-0022 D1's audit-consumability schema for future `/audit-against-best-practices` (PRD-D).
tools: Read, Grep, Glob
---

This skill is the docs-first authoritative reference for Claude Code workflow questions. It encapsulates the rules Anthropic publishes at `docs.claude.com` so the project doesn't re-derive them per session or per critic round. On-demand-loaded per ADR-0022 D2 Tier-1 source priority — zero CLAUDE.md bloat per the rationale in ADR-0022 Context.

**Authority chain.** Tier 1 is `docs.claude.com` (canonical, Anthropic-maintained). Tier 3 is `docs/best-practices/*.md` video distillations (PRD #147 artifacts, Anthropic-authored channels). The Authoritative-guidance section below cites Tier 1; the Supplementary section points to Tier 3 for the same topics so a curious reader can audit Anthropic's positioning across both surfaces.

**Default conservative.** When a workflow question has no rule below that obviously applies, answer "load the canonical page directly: `<URL>`" rather than guessing. The cost of a wrong rule-projection is a downstream slice built on a false premise; the cost of an honest "go read the source" is one extra navigation step.

## Authoritative guidance

The 6 numbered rules below distill the workflow-relevant guidance from the 5 distinct docs.claude.com pages fetched 2026-05-22 (the `slash-commands` URL currently redirects server-side to the `skills` page; both project to Rules 1+2 below). Rules 1, 2, 3, and 4 carry `**Grep:**` + `**Target:**` audit hooks consumable by the future PRD-D `/audit-against-best-practices` skill per ADR-0022 D1; Rules 5 and 6 are judgment-only.

### Rule 1: Every skill MUST declare a description that explains both what it does AND when to use it

**Rule:** Each `SKILL.md` frontmatter `description:` field must enumerate both the skill's purpose and the user-intent triggers that should load it (e.g., "Use when the user asks what changed, wants a commit message, or asks to review their diff"). Claude reads this field — and only this field — when deciding whether to auto-load the skill into context.
**Why:** Auto-activation is description-matching; an under-specified description means the skill either fires on every loosely-related query (context bloat) or never fires when needed (dead skill).
**Grep:** `^description:.*[Uu]se (when|for)`
**Target:** `.claude/skills/*/SKILL.md`
**Authority:** `https://docs.claude.com/en/docs/claude-code/skills` — "Frontmatter reference" + "the description helps Claude decide when to load the skill automatically" + the 1,536-character cap on combined description+when_to_use surface.

### Rule 2: Skill body content stays in context for every subsequent turn — keep it concise

**Rule:** A loaded `SKILL.md` body persists in the conversation across all subsequent turns. Every line is a recurring token cost; state what to do, not why or how (rationale and history belong in ADRs).
**Why:** Skill content is not lazy-loaded per turn — it joins the conversation context the moment the skill activates and stays there. Verbose prose multiplies every later turn's prompt token count.
**Grep:** `^## (Process|Instructions|When invoked|Authoritative guidance)`
**Target:** `.claude/skills/*/SKILL.md`
**Authority:** `https://docs.claude.com/en/docs/claude-code/skills` — "Once a skill loads, its content stays in context across turns, so every line is a recurring token cost. State what to do rather than narrating how or why, and apply the same conciseness test you would for CLAUDE.md content."

### Rule 3: Subagents are for context isolation; use one when a task would flood the main thread with bytes you won't reference again

**Rule:** Spawn a subagent when a side task (search, log dump, large file scan, multi-step research) would push intermediate output into the main context that you won't refer to after the summary. The subagent runs in its own context window and returns only the final summary.
**Why:** Subagent isolation is a context-window-hygiene mechanism, not a parallelism mechanism — the primary win is keeping intermediate exploration out of the parent thread.
**Grep:** `^tools:`
**Target:** `.claude/agents/*.md`
**Authority:** `https://docs.claude.com/en/docs/claude-code/sub-agents` — "Subagents are specialized AI assistants that handle specific types of tasks. Use one when a side task would flood your main conversation with search results, logs, or file contents you won't reference again: the subagent does that work in its own context and returns only the summary."

### Rule 4: Subagents and skills MUST limit tool access to the minimum needed for their job

**Rule:** Both `SKILL.md` (`allowed-tools:`) and subagent frontmatter (`tools:`) must enumerate the smallest tool set the artifact requires. Defaulting to "inherit all tools" inflates the blast radius if Claude misroutes a request to the agent/skill.
**Why:** Restricted tools constrain the failure modes the artifact can produce. A reviewer subagent with `Edit`/`Write` can accidentally rewrite the code it was meant to read; a skill granted `Bash(*)` can run arbitrary commands the user thought were behind permission prompts.
**Grep:** `^(tools:|allowed-tools:)`
**Target:** `.claude/agents/*.md`
**Authority:** `https://docs.claude.com/en/docs/claude-code/sub-agents` — "Best practices: ... Limit tool access: grant only necessary permissions for security and focus" + `https://docs.claude.com/en/docs/claude-code/skills` "Frontmatter reference / allowed-tools" + "For a read-only reviewer, deselect everything except Read-only tools."

### Rule 5: Settings live in a 4-scope precedence hierarchy — choose the scope deliberately

**Rule:** Configuration lives at four scopes, in descending priority: Managed (IT/org policy) > Project (`.claude/settings.json`, checked into git) > Local (`.claude/settings.local.json`, gitignored) > User (`~/.claude/settings.json`). Pick the scope that matches who owns the setting: team-wide rules → project; personal preferences → user; per-machine overrides → local. Permission `allow`/`deny` arrays merge across scopes (do not override); scalar settings override.
**Why:** Choosing the wrong scope either leaks personal config into the team repo (project-when-should-have-been-user) or hides team-wide policy behind a per-developer toggle (user-when-should-have-been-project).
**Authority:** `https://docs.claude.com/en/docs/claude-code/settings` — "Available scopes" + "When the same setting appears in multiple scopes, Claude Code applies them in priority order: Managed (highest) > User > Project > User (lowest)" + "Permission rules behave differently because they merge across scopes rather than override."

### Rule 6: CLAUDE.md is for cross-cutting standards; skills are for repeatable workflows; hooks are for deterministic mechanical actions

**Rule:** Use CLAUDE.md for project-wide rules every session must respect (coding standards, architecture, review checklists, glossary). Use a skill (`.claude/skills/<name>/SKILL.md`) for a repeatable workflow that needs its own description + invocation surface (e.g., `/review-pr`, `/deploy-staging`). Use a hook (`.claude/settings.json` + `.claude/hooks/`) for deterministic shell-command actions tied to specific Claude Code lifecycle events (auto-format after every edit, run lint before a commit).
**Why:** Conflating the three causes drift — putting workflow procedures in CLAUDE.md bloats the auto-loaded context; putting deterministic actions in a skill makes them prompt-conditional instead of mechanical; putting cross-cutting standards in a hook makes them invisible at read-time.
**Authority:** `https://docs.claude.com/en/docs/claude-code/overview` — "CLAUDE.md is a markdown file you add to your project root that Claude Code reads at the start of every session. Use it to set coding standards, architecture decisions, preferred libraries, and review checklists. ... Create skills to package repeatable workflows your team can share, like /review-pr or /deploy-staging. Hooks let you run shell commands before or after Claude Code actions, like auto-formatting after every file edit or running lint before a commit."

## Supplementary

Tier-3 supplementary references per ADR-0022 D2 and D9 — Anthropic-authored video distillations under `docs/best-practices/` covering adjacent workflow material. These are supplementary to the Tier-1 rules above, not replacements:

- [`docs/best-practices/what-is-claude-code-fl1DSmwQKKY.md`](../../../docs/best-practices/what-is-claude-code-fl1DSmwQKKY.md) — Claude Code 101 framing (agent-not-chat-box, context window, permission model). Most relevant to Rule 3 (when to delegate vs. handle inline) and Rule 4 (tool-restriction discipline).
- [`docs/best-practices/installing-claude-code-0kILa02vKuI.md`](../../../docs/best-practices/installing-claude-code-0kILa02vKuI.md) — install paths across surfaces (CLI, IDE, Desktop, web). Most relevant to Rule 5 (where User-scope settings live: `~/.claude/`).
- [`docs/best-practices/what-are-skills-bjdBVZa66oU.md`](../../../docs/best-practices/what-are-skills-bjdBVZa66oU.md) — explainer matching Rules 1+2 + the "write a skill the moment you find yourself explaining the same thing to Claude twice" trigger heuristic.
- [`docs/best-practices/what-are-subagents-jKErNxuxPXg.md`](../../../docs/best-practices/what-are-subagents-jKErNxuxPXg.md) — explainer matching Rules 3+4 + the "treat each subagent as a specialized assistant with a bounded job" specialization principle.
- [`docs/best-practices/code-with-claude-london-2026-opening-keynote-6amLO7I9xdg.md`](../../../docs/best-practices/code-with-claude-london-2026-opening-keynote-6amLO7I9xdg.md) — keynote with the "build for emerging capabilities, not just what works today" architectural framing relevant to Rule 6 (scaffolding survives model upgrades).

## How to apply to this project

Concrete checks against current project files (run these when authoring a new skill / subagent, or when this skill is invoked for a workflow audit):

- **Rule 1 check:** every existing `.claude/skills/*/SKILL.md` already has a `description:` field whose prose narrates use-triggers (verified against `audit-subagents`, `glossary-add`, `to-prd`, `to-issues`, `ship`, `qa-plan`, `promote-to-backlog`, `distill-video`, `audit-meta`, `grill-me`, `glossary-fold`). New skills must continue this pattern.
- **Rule 2 check:** SKILL bodies in this repo stay roughly under 200 LoC (R-LOC is 300 for runtime artifacts but most skills sit well below). When a SKILL.md approaches 300 LoC, split per [ADR-0005](../../../decisions/0005-output-shape-and-slicing-methodology.md) D2 SPIDR-Interface hint rather than letting the per-turn token cost grow.
- **Rule 3 check:** the 8 existing subagents under `.claude/agents/` (`reviewer`, `prd-critic`, `adr-critic`, `slicer-critic`, `glossary-critic`, `backlog-critic`, `slicer`, `implementer`, `qa-tester`) are all bounded-job specialists per the docs.claude.com framing. New subagent proposals should be challenged: would a skill in the parent context suffice?
- **Rule 4 check:** every subagent file already declares an explicit `tools:` frontmatter line (per [ADR-0001](../../../decisions/0001-foundational-design.md) D6 and audited by `/audit-subagents` ALL-1). New subagents must enumerate the smallest tool set; default-to-inherit is rejected at PR time by `reviewer`.
- **Rule 5 check:** the project uses `.claude/settings.json` (project scope, committed) for hooks per [ADR-0015](../../../decisions/0015-claude-code-hooks-adoption.md). No `.claude/settings.local.json` is committed (correct — Local scope is gitignored by convention). User-scope settings are out-of-repo per developer.
- **Rule 6 check:** the CLAUDE.md / skill / hook split is already disciplined here — cross-cutting rules in CLAUDE.md (rule 1-11), repeatable workflows as skills under `.claude/skills/`, deterministic event-triggered actions as hooks under `.claude/hooks/` (per ADR-0015 + ADR-0016).

## Common pitfalls

Anti-patterns drawn from the docs + project history:

- **Under-specified skill description.** A description that only says "summarizes changes" without listing triggers ("Use when the user asks what changed, wants a commit message, or asks to review their diff") will either never auto-load or load on every loosely-related query. Always include explicit "Use when ..." trigger phrases.
- **Skill body that narrates rationale instead of stating procedure.** Long "this exists because ..." prose belongs in an ADR or commit message, not in the loaded skill context. The skill body is per-turn token cost; the ADR is read-once.
- **Subagent used for parallelism instead of context isolation.** Spawning N subagents to "go faster" misses the docs.claude.com framing: the primary purpose is keeping intermediate bytes out of the main thread. Parallelism is a side-effect, not the goal. Project's `/ship` DAG-batching per [ADR-0010](../../../decisions/0010-implementer-subagent-auto-pipeline.md) D3 is parallel because the slices are independent — not because subagents inherently parallelize.
- **Inheriting all tools by default.** A subagent or skill that omits `tools:` / `allowed-tools:` and inherits everything has the same blast radius as the main thread. Always enumerate the minimum tool set.
- **Putting project policy in User-scope settings.** A rule meant to bind the team must live in `.claude/settings.json` (committed Project scope), not `~/.claude/settings.json` (per-developer User scope). Personal preferences (themes, editor mode) belong in User scope.
- **Drifting CLAUDE.md into a procedure manual.** Step-by-step workflows ("how to ship a slice") belong in a skill body (`/ship`, `/grill-me`, this skill), not in CLAUDE.md. CLAUDE.md is for invariant standards every session must respect, not for procedural recipes.

## Tool boundaries

Allowed: `Read`, `Grep`, `Glob` — the skill is a reference text; it reads project files only to answer "is this rule honored here?" when asked. It does not edit anything.

Forbidden: `Edit`, `Write` (no project mutations from a best-practice reference); `Bash` (no shell execution from a doc skill — if a user wants to run the rule's Grep, they can copy it themselves; this skill is reference, not actuator); `Agent` (no recursive subagent invocation — this is a leaf reference skill); any `gh` / `git` operation (no GitHub mutations from a doc skill).

## References

- [ADR-0022](../../../decisions/0022-docs-first-kb-pattern.md) — D1 (4-section skill shape + Grep/Target audit-hook schema), D2 (Tier-1/2/3 source priority), D3 (`.claude/skills/best-practice-<topic>/` location convention), D5 (hand-curated curl-based ingest), D9 (existing video distillations preserved as Tier 3 supplementary), D11 (surgical supersession of ADR-0019 D3 yt-dlp bits only).
- [ADR-0019](../../../decisions/0019-best-practices-kb-pattern.md) — D1 (fetch-distill-store pipeline; in-force) and D2 (`docs/best-practices/` tree; in-force) preserved per ADR-0022 D11.
- [ADR-0011](../../../decisions/0011-subagent-quality-framework.md) — D2 (mechanical/grep-only rubric pattern extended into ADR-0022 D1's Grep/Target schema), D5 (advisory-only single-Markdown-report precedent).
- [ADR-0001](../../../decisions/0001-foundational-design.md) D6 — canonical subagent frontmatter convention (sources Rule 4's project-side enforcement).
- `https://docs.claude.com/en/docs/claude-code/skills` — Rules 1, 2, 4.
- `https://docs.claude.com/en/docs/claude-code/sub-agents` — Rules 3, 4.
- `https://docs.claude.com/en/docs/claude-code/settings` — Rule 5.
- `https://docs.claude.com/en/docs/claude-code/overview` — Rule 6 + CLAUDE.md/skill/hook delineation.
- `https://docs.claude.com/en/docs/claude-code/hooks-guide` — adjacent Tier-1 page; future `best-practice-hooks` skill (PRD-C per ADR-0022 D8) is the canonical home for hook-specific rules; not duplicated here per ADR-0022 D3 per-topic-skill convention.
- `https://docs.claude.com/en/docs/claude-code/slash-commands` — currently redirects to the skills page; covered by Rules 1+2 above.
