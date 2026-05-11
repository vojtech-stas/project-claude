# project-claude

A clone-as-template starter for AI-coded projects, replicating the workflow of a **senior engineer overseeing a small team of developers** — but with AI agents instead of humans. Built on 20-year-old software engineering practices (small slices, fast feedback, git-tracked changes, PR review, scope discipline) and heavy borrowing from [Matt Pocock's skills repo](https://github.com/mattpocock/skills).

## What's the idea

You play **senior engineer**. AI agents play **the team**. The template ships with a workflow pipeline that mirrors how a project manager works with a small group of developers:

```
idea  →  grill-me  →  research  →  prototype × N  →  PRD
                                                      ↓
                              issues (kanban)  ←  -----
                                  ↓
                              implement (TDD)
                                  ↓
                              review (stronger model, restricted tools)
                                  ↓
                              YOU click merge
                                  ↓
                              QA plan for human verification
```

A main agent holds project context (grilling, PRD, issues). Specialist subagents handle research, prototyping, implementation, and review with clean isolated context. You stay in the driver's seat — every PR ships only after you approve.

## Use it

```bash
git clone https://github.com/vojtech-stas/project-claude my-new-project
cd my-new-project
# open in Claude Code — CLAUDE.md auto-loads, the agents are oriented
```

## What's inside

- **`CLAUDE.md`** — project rules, auto-loaded by Claude Code every session
- **`.claude/skills/`** — pipeline skills (`grill-me` installed; more land in later slices)
- **`decisions/`** — Architecture Decision Records, starting with `0001` for the founding design
- This README

## Status

**Walking-skeleton phase.** The pipeline is being built incrementally **on the project itself** — dogfooding from day one. Each slice ships one capability end-to-end, gets reviewed, and merges before the next begins.

See **`decisions/0001-foundational-design.md`** for the full design rationale (the grilling session that produced this template).

## License

MIT — use it, fork it, ship it. A shoutout is appreciated.

## Credits

Inspired by [Matt Pocock's skills repo](https://github.com/mattpocock/skills) and the senior-engineer-over-agents workflow pattern.
