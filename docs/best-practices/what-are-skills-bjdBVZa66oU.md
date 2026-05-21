# What are skills? (distilled)

Short Anthropic explainer video introducing Claude Code Skills (https://www.youtube.com/watch?v=bjdBVZa66oU), uploaded 2026-02-27 on the `@claude` YouTube channel; runtime 2m 54s. This is the first video in the official "Claude Code Skills" playlist. The speaker is not identified by name in the auto-captions but speaks on behalf of Anthropic, walking through what a skill is, the `SKILL.md` shape (name + description), the personal-vs-project storage locations (`~/.claude/skills/` vs repo-root `.claude/skills/`), how Claude auto-activates skills by matching descriptions against the user's request, and how skills differ from `CLAUDE.md` files and slash-commands.

The 7 recommendations below are extracted as best-practice imperatives directly applicable to this project's `.claude/skills/*/SKILL.md` conventions and to future skill authoring. Each cites a single representative `(HH:MM:SS)` timestamp; the full transcript at [`bjdBVZa66oU.vtt`](transcripts/bjdBVZa66oU.vtt) is the audit source.

## Best-practice recommendations

- **Write a skill the moment you find yourself explaining the same thing to Claude twice.** The opening framing and the closing line both make this the core trigger: repeated explanation of coding standards, PR-review style, or commit-message preferences across conversations is the operational signal that a skill is missing. `(00:00:03)` For this project: when a critic round-trip surfaces the same correction twice in different PRs, that's the prompt to add either a CLAUDE.md rule or a project skill — not to keep restating the rule per session.

- **Treat the SKILL.md description as the activation contract — Claude decides whether to load a skill by matching the user request against the description.** The description is not documentation for humans; it is the discoverability surface Claude uses to pick the skill out of an inventory of available skills. `(00:00:45)` Maps to this project's existing pattern (every `.claude/skills/<name>/SKILL.md` frontmatter has a `description:` field) and to the `/audit-subagents` ALL-1 check — but reinforces that vague descriptions are a correctness bug, not a style nit, because they cause wrong-skill activation or missed activation.

- **Keep only `name` and `description` in the auto-loaded frontmatter; let the body load on demand.** Skills load on demand when their description matches the request — only the name + description live in the context window until then, so the skill body does not bloat the context budget. `(00:02:04)` Validates this project's frontmatter-minimal convention (`.claude/skills/*/SKILL.md` files have small frontmatter blocks with body-level detail) and argues against pre-loading skill bodies via CLAUDE.md inclusion.

- **Use personal skills (`~/.claude/skills/`) for cross-project preferences; use project skills (`.claude/skills/` in the repo) for team standards.** The two locations are not interchangeable: personal skills follow the developer across all their projects (preferences, commit style, doc format); project skills are team-shared and travel with the clone (brand guidelines, code-review checklists, company standards). `(00:01:10)` This project's `.claude/skills/` tree is correctly the project tier — team-shared, repo-cloned, autoloaded. The personal tier is the right home for individual style overrides and is intentionally out of scope for this repo's tracked conventions.

- **Distinguish skills from `CLAUDE.md`: skills load on demand by description-match; `CLAUDE.md` loads into every conversation.** The two mechanisms compose — put always-on rules (e.g., "always use TypeScript strict mode") in `CLAUDE.md`; put task-specific recipes that should only load when relevant (e.g., "PR review checklist") in a skill. `(00:01:51)` This project's `CLAUDE.md` correctly holds cross-cutting rules (rules 1-11, hierarchy, glossary) while task-specific recipes (`/grill-me`, `/ship`, `/distill-video`, `/audit-subagents`) live as skills — the right separation per this distinction.

- **Distinguish skills from slash-commands: slash-commands require the user to type them; skills auto-activate when Claude recognizes the situation.** Slash-commands are explicit user-driven invocation; skills are pattern-matched activation from natural-language requests. The two coexist and can wrap the same underlying recipe. `(00:02:17)` This project's skills are wired both ways: each skill has both a `/skill-name` slash-invocation AND a natural-language description that supports auto-activation — the right belt-and-suspenders pattern.

- **Skills are folders of instructions, scripts, and resources — not just a single Markdown file.** A skill can include supporting scripts and resources alongside the `SKILL.md`; the folder is the unit, the `SKILL.md` is the entry point. `(00:00:33)` Forward direction for this project: skills that grow beyond ~150 LoC should split supporting scripts (e.g., yt-dlp shell-out wrappers, post-distill validation scripts) into sibling files under the same skill folder rather than inlining everything in `SKILL.md`. Currently all this project's skills are single-file; this is a deliberate Phase-1 simplicity, not a constraint of the skills mechanism.

## Authority

- **Source:** https://www.youtube.com/watch?v=bjdBVZa66oU
- **Channel:** Claude (`@claude`) — "Claude Code Skills" playlist (first video)
- **Upload date:** 2026-02-27
- **Duration:** 2m 54s
- **Raw transcript:** [`bjdBVZa66oU.vtt`](transcripts/bjdBVZa66oU.vtt)
- **Distilled by:** `/distill-video` skill (per [ADR-0019](../../decisions/0019-best-practices-kb-pattern.md))
