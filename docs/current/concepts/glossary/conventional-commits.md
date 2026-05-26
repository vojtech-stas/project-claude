---
title: Conventional Commits — tightened commit-message format
summary: The `<type>(<optional scope>): <subject>` commit-message format applied here with a lowercase subject, at most 72 chars, and a Co-authored-by trailer on agent commits.
tags: [glossary, conventions, external-standard, git]
type: concept
last_updated: 2026-05-26
sources:
  - https://www.conventionalcommits.org/en/v1.0.0/
  - CLAUDE.md
---

# Conventional Commits

**Conventional Commits** is an external commit-message specification (v1.0.0) that this project adopts with three project-specific tightenings: lowercase subject, ≤72-char hard cap, and a `Co-authored-by:` trailer on every agent-authored commit. The shape is `<type>(<optional scope>): <subject>` where `<type>` comes from a closed set.

**Edges**

- **related-to:** [[concepts/glossary/trivial-lane]]
- **related-to:** [[concepts/glossary/slice]]
- **part-of:** [[topics/git-workflow]]

## What

The closed type set for this project: `feat`, `fix`, `docs`, `chore`, `refactor`, `test`, `perf`, `style`, `build`, `ci` (per CLAUDE.md rule #5). The `hotfix/` branch prefix is reserved for the trivial lane (I3) and is NOT a Conventional Commits type — trivial-lane PRs still use one of the type set above in the commit subject (typically `docs:` or `fix:`).

Project-specific tightenings applied on top of the upstream spec:

1. **Lowercase subject** after the colon — `feat: add ship skill`, not `feat: Add Ship Skill`.
2. **≤72-character hard cap** on the subject line — enforced by the [`commit-msg`](../../../.githooks/commit-msg) git hook.
3. **`Closes #<slice-issue>`** belongs in the PR body, not the commit subject — keeps slice-issue references out of git log noise; reviewer's R-CLOSES rule enforces.
4. **`Co-Authored-By:` trailer** on every agent-authored commit — preserves attribution; reviewer's R-META rule cites this for new ADR files.
5. **Body explains WHY**, not what — the diff already shows what changed; the body's value-add is the rationale.

Optional scope syntax (`feat(kb): ...`, `fix(slicer): ...`) is permitted but not required.

## Why

Conventional Commits exists because **commit messages are the changelog** (CLAUDE.md rule #6). The structured prefix lets readers and tools scan `git log` to find feature additions vs bug fixes vs documentation changes without reading bodies. The closed type set prevents the bikeshed problem (`add:` vs `new:` vs `introduce:` all meaning "feat"). The ≤72-char cap keeps `git log --oneline` readable at any terminal width.

The Co-Authored-By trailer is the load-bearing project-specific addition. It anchors the R-META reviewer rule's "subagent provenance" check on new ADR files — the trailer proves the file was generated through the subagent pipeline rather than hand-authored by the main agent (which would violate CLAUDE.md rule #10).

## Examples from this project

- `feat(kb): glossary migration — 5 pipeline-cluster atomic notes` — slice 1 of PRD #245.
- `docs(claude): add rule #13 root-cause workflow capture + ADR-0024` — a recent docs PR with body explaining the workflow rationale.
- `fix(hooks): correct SessionStart additionalContext field` — hypothetical fix-shape commit.
- Forbidden: `Add Ship Skill.` (capitalized + period + no type), `wip` (vague), `final` (vague), `update stuff` (vague).

## Anti-patterns

- **Capitalized subject** — `feat: Add ship skill`. The hook (or the reviewer) BLOCKs.
- **Subject over 72 chars** — `feat: implement comprehensive end-to-end glossary migration with full edge resolution for all 22 terms`. Move detail to the body.
- **Multiple unrelated changes in one commit** — bundles drift; squash-merge cannot rescue this because the squash commit inherits the noisy subject. Commit at meaningful checkpoints, not just at the end.
- **`Closes #N` in the subject** — clutters `git log`; belongs in the PR body where R-CLOSES looks.
- **Missing `Co-Authored-By:` on agent-authored commits** — breaks the R-META provenance chain for new ADR files.

## Scope

(b) external standard adopted

## Authority

[Conventional Commits v1.0.0 specification](https://www.conventionalcommits.org/en/v1.0.0/)

## References

- [Conventional Commits v1.0.0](https://www.conventionalcommits.org/en/v1.0.0/) — upstream specification.
- [CLAUDE.md](../../../CLAUDE.md) rule #5 — project-specific tightenings.
- [CLAUDE.md](../../../CLAUDE.md) rule #6 — `git log` is the changelog (no separate CHANGELOG file).
- [`.githooks/commit-msg`](../../../.githooks/commit-msg) — local enforcement hook.
- [ADR-0004](../../../decisions/0004-bypass-prevention.md) D4 — R-META subagent-provenance via Co-Authored-By trailer.
