---
title: best-practices — Claude Code subagents (design)
summary: Docs-first authoritative guidance for Claude Code subagent-design questions — frontmatter fields, tool boundaries, model choice, preloaded skills, the no-nested-spawn rule, and the description-driven delegation contract. 6 numbered rules distilled from docs.claude.com/sub-agents per ADR-0022 D1 with mechanical Grep+Target audit hooks.
tags: [best-practice, subagents, docs-first, topic, claude-code]
type: topic
last_updated: 2026-05-27
sources:
  - .claude/skills/best-practice-subagents/SKILL.md
  - decisions/0022-docs-first-kb-pattern.md
  - decisions/0011-subagent-quality-framework.md
---

# best-practices — Claude Code subagents

The canonical KB-layer home of docs-first authoritative guidance for Claude Code **subagent-design questions** (frontmatter, tools, model, preloaded skills, the no-nested-spawn rule). Authority: [ADR-0022](../../../decisions/0022-docs-first-kb-pattern.md) D1 (4-section shape) and D8 (PRD-A → siblings DAG; this is the subagents-sibling). This topic page is content-equivalent to [`.claude/skills/best-practice-subagents/SKILL.md`](../../../.claude/skills/best-practice-subagents/SKILL.md) on origin/main as of 2026-05-27.

Per [ADR-0031](../../../decisions/0031-knowledge-architecture-v2.md) D10 step 5 of 9, the canonical home of this synthesis is **here in `docs/current/topics/`**, not in the skill body. T5-S8 (#315) thins the skill body to a thin dispatcher shell pointing here; until that ships, edits to either location must update both to prevent drift.

This synthesis encapsulates the rules Anthropic publishes at `docs.claude.com/en/docs/claude-code/sub-agents` so this project doesn't re-derive them per session or per critic round. Sibling to [`best-practices-workflow`](best-practices-workflow.md), which covers cross-cutting workflow questions; this topic is the **subagent-specific deep cut**.

**Authority chain.** Tier 1 is `docs.claude.com/en/docs/claude-code/sub-agents` (canonical, Anthropic-maintained). Tier 3 is `docs/best-practices/*.md` video distillations (PRD #147 artifacts, Anthropic-authored channels). The Authoritative-guidance section below cites Tier 1; the Supplementary section points to Tier 3 for the same topic.

**Default conservative.** When a subagent-design question has no rule below that obviously applies, answer "load the canonical page directly: `https://docs.claude.com/en/docs/claude-code/sub-agents`" rather than guessing. The cost of a wrong rule-projection is a downstream subagent shipped on a false premise; the cost of an honest "go read the source" is one extra navigation step.

## Authoritative guidance

The 6 numbered rules below distill the subagent-relevant guidance from `docs.claude.com/en/docs/claude-code/sub-agents` fetched 2026-05-22. Rules 1, 2, 3, 4, and 6 carry `**Grep:**` + `**Target:**` audit hooks consumable by the future PRD-D `/audit-against-best-practices` skill per ADR-0022 D1; Rule 5 is judgment-only.

### Rule 1: Design focused subagents — each subagent should excel at one specific task

**Rule:** Each subagent's `description:` and system prompt (the body) MUST narrow the subagent to one bounded job (one PR-shaped artifact, one verdict type, one mechanical sweep). Generalist "do-many-things" subagents miss the specialization that the architecture is designed for.
**Why:** Specialization is the design intent of the abstraction, not an optimization. A generalist subagent fails to gain context-window-hygiene wins (its summary must cover too much) and fails delegation routing (Claude can't reliably decide when to invoke it). The whole point of an isolated context is that the work inside it is narrow enough that only a focused summary needs to come back.
**Grep:** `^description:.{0,200}(Audit|Implement|Review|Execute|Generate|Score) `
**Target:** `.claude/agents/*.md`
**Authority:** `https://docs.claude.com/en/docs/claude-code/sub-agents` — "Best practices: Design focused subagents — each subagent should excel at one specific task" + "Specialize behavior with focused system prompts for specific domains."

### Rule 2: Limit tool access — grant only the tools the subagent's job requires

**Rule:** Every subagent MUST declare an explicit `tools:` allowlist (or use `disallowedTools:` as a denylist) in its frontmatter. Omitting `tools:` inherits ALL tools available to the main conversation including MCP tools — a blast-radius footgun. If both fields are set, `disallowedTools` is applied first, then `tools` resolves against the remaining pool; a tool listed in both is removed.
**Why:** Tool restrictions constrain the failure modes the subagent can produce. A read-only critic with `Edit`/`Write` can accidentally rewrite the artifact it was meant to judge; a researcher with `Bash` can run arbitrary commands the user thought were behind permission prompts. The docs' own code-reviewer example uses `tools: Read, Grep, Glob, Bash` precisely to deselect Edit/Write.
**Grep:** `^(tools|disallowedTools):`
**Target:** `.claude/agents/*.md`
**Authority:** `https://docs.claude.com/en/docs/claude-code/sub-agents` — "Best practices: Limit tool access — grant only necessary permissions for security and focus" + "Available tools / By default, subagents inherit all tools from the main conversation, including MCP tools. To restrict tools, use either the `tools` field (allowlist) or the `disallowedTools` field (denylist)" + "If both are set, `disallowedTools` is applied first, then `tools` is resolved against the remaining pool."

### Rule 3: Write detailed descriptions — Claude uses the description to decide when to delegate

**Rule:** Each subagent's `description:` field MUST narrate BOTH what the subagent does AND when Claude should delegate to it (explicit invocation triggers like "Use when …", "Use immediately after …", "Use proactively after …"). Claude reads the `description` — and only the `description` — to make the automatic-delegation routing decision.
**Why:** Automatic delegation is description-matching. An under-specified description means the subagent either never fires when it should or fires on every loosely-related query (context bloat from spurious spawns). The docs explicitly recommend phrases like "use proactively" to encourage active delegation.
**Grep:** `^description:.{0,400}[Uu]se (when|immediately|proactively|after|for)`
**Target:** `.claude/agents/*.md`
**Authority:** `https://docs.claude.com/en/docs/claude-code/sub-agents` — "Best practices: Write detailed descriptions — Claude uses the description to decide when to delegate" + "Understand automatic delegation / Claude automatically delegates tasks based on the task description in your request, the `description` field in subagent configurations, and current context. To encourage proactive delegation, include phrases like 'use proactively' in your subagent's description field."

### Rule 4: Choose the model deliberately — pick `sonnet`/`opus`/`haiku`/`inherit` to match the subagent's job

**Rule:** Every subagent SHOULD declare an explicit `model:` field (`sonnet`, `opus`, `haiku`, a full model ID like `claude-opus-4-7`, or `inherit`). Default-on-omission is `inherit` (parent's model), which is fine for mixed-reasoning subagents but wasteful for high-volume mechanical work (use `haiku`) and risky for deep-judgment critics (pin `opus` so a parent on `sonnet` doesn't silently downgrade the reviewer).
**Why:** The wrong model erodes either cost (deep model on a mechanical executor) or quality (cheap model on a nuanced critic verdict). Explicit pinning makes the trade-off visible in the file rather than implicit in the session.
**Grep:** `^model:`
**Target:** `.claude/agents/*.md`
**Authority:** `https://docs.claude.com/en/docs/claude-code/sub-agents` — "Choose a model / Model alias: Use one of the available aliases: `sonnet`, `opus`, or `haiku`. Full model ID: Use a full model ID such as `claude-opus-4-7`. `inherit`: Use the same model as the main conversation. Omitted: If not specified, defaults to `inherit`." + the docs' own built-in subagent table assigns Explore=Haiku, Plan=inherit, general-purpose=inherit — model choice is a deliberate per-job decision.

### Rule 5: Preload skills via the `skills:` field when the subagent needs domain knowledge at startup

**Rule:** Use the `skills:` frontmatter field to inject full skill content into a subagent's context at startup when the subagent's job depends on stable domain conventions (API patterns, formatting rules). This is the inverse of invoking a skill at runtime via the `Skill` tool — preloaded skills land in context before the first turn; runtime-invoked skills land mid-conversation.
**Why:** Preloaded skills avoid the latency-and-uncertainty of in-task discovery for known-needed knowledge. They are NOT a substitute for tool restriction: `skills:` controls what is preloaded, not what the subagent can access — to prevent runtime skill invocation entirely, omit `Skill` from `tools:` or add it to `disallowedTools:`. Skills with `disable-model-invocation: true` cannot be preloaded.
**Authority:** `https://docs.claude.com/en/docs/claude-code/sub-agents` — "Preload skills into subagents / Use the `skills` field to inject skill content into a subagent's context at startup … This field controls which skills are preloaded, not which skills the subagent can access: without it, the subagent can still discover and invoke project, user, and plugin skills through the Skill tool during execution."

### Rule 6: Subagents CANNOT spawn other subagents — do not put `Agent` in a subagent's `tools:` list

**Rule:** Subagents may not invoke the `Agent` tool to spawn nested subagents. Including `Agent` in a subagent's `tools:` frontmatter is a no-op at best, a misleading signal at worst (it implies a capability that does not exist). For workflows that require multi-step delegation, chain subagents from the main conversation OR use skills inside the subagent.
**Why:** Nested-spawn prevention is structural: the `Agent` tool only works in the main thread (and in agents running as main via `claude --agent`). Allowing nested spawn would defeat the context-isolation invariant — a parent expecting one focused summary could receive an unbounded tree of intermediate output. The docs are explicit: "Subagents cannot spawn other subagents."
**Grep:** `^tools:.*\bAgent\b`
**Target:** `.claude/agents/*.md`
**Authority:** `https://docs.claude.com/en/docs/claude-code/sub-agents` — "Subagents cannot spawn other subagents, so `Agent(agent_type)` has no effect in subagent definitions" + "Choose between subagents and main conversation / Subagents cannot spawn other subagents. If your workflow requires nested delegation, use Skills or chain subagents from the main conversation."

## Supplementary

Tier-3 supplementary references per ADR-0022 D2 and D9 — Anthropic-authored video distillations under `docs/best-practices/` covering subagent material. Supplementary to the Tier-1 rules above, not replacements:

- [`docs/best-practices/what-are-subagents-jKErNxuxPXg.md`](../../../docs/best-practices/what-are-subagents-jKErNxuxPXg.md) — the canonical Anthropic introduction to the subagent abstraction (`@claude` YouTube, 2m 48s). Reinforces Rules 1 (specialization-not-optimization framing), 2 (custom system prompt + bounded tool access), and the two-input invocation contract (system prompt + per-call task description) that underlies Rule 3's delegation routing.
- [`docs/best-practices/what-is-claude-code-fl1DSmwQKKY.md`](../../../docs/best-practices/what-is-claude-code-fl1DSmwQKKY.md) — Claude Code 101 framing relevant to the "subagent vs main conversation vs skill" choice that Rules 1+5 cover.

## How to apply to this project

Concrete checks against the 9 existing subagents under `.claude/agents/` (`reviewer`, `prd-critic`, `adr-critic`, `slicer-critic`, `glossary-critic`, `backlog-critic`, `slicer`, `implementer`, `qa-tester`). Run these when authoring a new subagent or auditing existing ones:

- **Rule 1 check** — every existing subagent description opens with a single bounded-job verb (Audit / Implement / Review / Execute / Score / Generate). No generalists. New subagent proposals must continue this pattern; if the description hedges with "or" between two job types, split into two subagents per the 6-critic-cap meta-rule consideration (ADR-0008 D7).
- **Rule 2 check** — every existing subagent declares an explicit `tools:` allowlist (verified by `grep -L '^tools:' .claude/agents/*.md` returning empty). The standard reads-only set is `Read, Glob, Grep, Bash`; `implementer` adds `Edit, Write` because it ships PRs; `qa-tester` uses `Read, Bash, Grep` (no Glob — its plan is structured input). No subagent uses `disallowedTools:` here.
- **Rule 3 check** — every existing description includes an explicit "Use when …" / "Use immediately after …" / "Use proactively …" trigger phrase. New subagents must preserve this; under-specified descriptions are reviewer-blockable per Rule 3.
- **Rule 4 check** — model assignments: critics (`*-critic.md`, `reviewer.md`) all use `opus` (deep verdict reasoning). Generators: `slicer` and `implementer` use `opus` (decomposition/PR-shaping reasoning); `qa-tester` uses `sonnet` (mechanical row-execution). No subagent currently uses `haiku` or `inherit`. If a future subagent ships with `model: inherit` or omits the field, the implementer must justify the choice in the slice body.
- **Rule 5 check** — NO existing subagent uses the `skills:` preload field. Project skills are invoked at runtime via the Skill tool path. This is consistent with the no-runtime-magic preference but worth re-evaluating when a future subagent needs to ship with stable preloaded conventions (e.g., a hypothetical `style-formatter` subagent preloading the project's prose-style skill).
- **Rule 6 check** — NO existing subagent has `Agent` in its `tools:` list (verified by `grep -lE '^tools:.*\bAgent\b' .claude/agents/*.md` returning empty). The `implementer.md` body explicitly states "You do NOT spawn other subagents" per ADR-0010 D6 — that prose enforcement matches the docs' structural prevention. New subagents must preserve this; any temptation to nested-spawn is a signal to redesign as a skill OR to chain from the main thread.

If a drift case is found by these checks (e.g., a future subagent lands with `model:` omitted), capture it as a `captured`-labeled issue per CLAUDE.md rule #11 and invoke `/promote-to-backlog` — do NOT fix in-flight here (Rule-5 drift fixes are out of scope per slice #180's "Out of scope" section).

## Common pitfalls

Anti-patterns drawn from the docs + project history:

- **Subagent used for parallelism instead of context isolation.** The primary purpose of a subagent is keeping intermediate bytes out of the main thread; parallelism is a side-effect. Spawning N subagents to "go faster" without a context-hygiene win is a smell. This project's `/ship` DAG-batching (ADR-0010 D3) is parallel because the slices are independent, NOT because subagents inherently parallelize.
- **Inheriting all tools by default (omitted `tools:`).** A subagent that omits `tools:` has the same blast radius as the main thread. Always enumerate the smallest tool set; default-to-inherit is rejected at PR time by `reviewer` (per Rule 2 audit hook).
- **Description that says what but not when.** A description like "Reviews code" without trigger phrases ("Use immediately after writing or modifying code" / "Use proactively") means Claude can't route to the subagent; the subagent becomes effectively dead-coded. Always state both purpose AND invocation triggers (Rule 3).
- **Putting `Agent` in subagent `tools:`.** Implies a capability that does not exist (Rule 6). Misleads future maintainers into designing workflows that the runtime will silently refuse to execute.
- **Default `model:` omission masking the trade-off.** Letting `model:` default to `inherit` is fine for general-purpose subagents but hides a real cost/quality decision for either high-volume (should pin `haiku`) or deep-judgment (should pin `opus`) cases. Make the choice explicit in the file (Rule 4).
- **Preloading skills the subagent doesn't need at turn-1 (Rule 5 misuse).** Preloaded skill content lands in the context window before the first turn. Preloading rarely-needed skills inflates startup cost; let runtime-invocation via the `Skill` tool handle just-in-time needs.
- **Confusing subagent with skill.** A subagent has isolated context + custom system prompt + restricted tools + summary-return contract; a skill is shared-context + auto-loaded by description + procedural. If the job needs the main conversation's full context, use a skill; if it produces verbose intermediate output the main thread won't reference, use a subagent. (Cross-reference: best-practices-workflow Rule 3.)

## Tool boundaries

The `/best-practice-subagents` skill that hosts this content has:

Allowed: `Read`, `Grep`, `Glob` — the skill is a reference text; it reads project files only to answer "is this rule honored here?" when asked. It does not edit anything.

Forbidden: `Edit`, `Write` (no project mutations from a best-practice reference); `Bash` (no shell execution from a doc skill — if a user wants to run the rule's Grep, they can copy it themselves; this skill is reference, not actuator); `Agent` (no recursive subagent invocation — this is a leaf reference skill, and per Rule 6 a skill spawning a subagent that spawns nothing is the correct topology); any `gh` / `git` operation (no GitHub mutations from a doc skill).

## References

- [ADR-0022](../../../decisions/0022-docs-first-kb-pattern.md) — D1 (4-section skill shape + Grep/Target audit-hook schema), D2 (Tier-1/2/3 source priority), D3 (`.claude/skills/best-practice-<topic>/` location convention applied to this skill as topic = `subagents`), D5 (hand-curated curl-based ingest), D9 (existing video distillations preserved as Tier 3 supplementary), D8 (DAG sequencing — PRD #179 is the first sibling-A-after-A application of the pattern).
- [ADR-0011](../../../decisions/0011-subagent-quality-framework.md) — D2 (mechanical/grep-only rubric pattern extended into ADR-0022 D1's Grep/Target schema), D4 (the 10-check rubric `/audit-subagents` runs against `.claude/agents/*.md` — this skill is the docs-grounded *why* layer to that mechanical *what* layer), D5 (advisory-only single-Markdown-report precedent).
- [ADR-0019](../../../decisions/0019-best-practices-kb-pattern.md) — D1 (fetch-distill-store pipeline; in-force per ADR-0022 D11) and D2 (`docs/best-practices/` tree; in-force) — sources the Tier-3 video distillations cited in Supplementary.
- [ADR-0015](../../../decisions/0015-claude-code-hooks-adoption.md) — adjacent; subagent-frontmatter `hooks:` field briefly noted in Rule 2's authority quote. Hook-specific best-practices live in the [best-practices-hooks](best-practices-hooks.md) sibling topic (PRD-C per ADR-0022 D8 DAG); not duplicated here per ADR-0022 D3 per-topic-skill convention.
- [ADR-0031](../../../decisions/0031-knowledge-architecture-v2.md) D10 step 5 — the slice that moved this synthesis from skill body to KB topic.
- `https://docs.claude.com/en/docs/claude-code/sub-agents` — canonical Tier-1 source for all 6 rules above.
- `https://docs.claude.com/en/docs/claude-code/skills` — adjacent Tier-1; sources Rule 5's `Skill` tool / `disable-model-invocation` interplay (covered in depth by best-practices-workflow Rules 1+2).

## Edges

- **part_of:** [[entities/skills/best-practice-subagents]]
- **related_to:** [[topics/best-practices-workflow]]
- **related_to:** [[topics/best-practices-hooks]]
- **related_to:** [[entities/skills/audit-subagents]]
- **related_to:** [[entities/skills/distill-video]]
- **related_to:** [[concepts/glossary/subagent]]
- **related_to:** [[concepts/glossary/critic]]
