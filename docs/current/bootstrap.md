# Bootstrap — current capability table

- **Status:** current as of 2026-05-26
- **Date:** 2026-05-26
- **Topic slug:** `bootstrap`

Active synthesis of the fresh-clone setup per [ADR-0026](../../decisions/0026-knowledge-architecture-truth-docs.md) D1 — canonical answer to "what does `bootstrap.sh` do, what does it install, and what does it deliberately NOT do?" derived from the immutable ADR chain ([ADR-0008](../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D6, [ADR-0019](../../decisions/0019-best-practices-kb-pattern.md) D3, [ADR-0025](../../decisions/0025-qa-tester-ui-mode-playwright.md) D7, [ADR-0030](../../decisions/0030-windows-gitbash-hardening.md)) + the `bootstrap.sh` script itself; regenerated at PR review time per R-TRUTH-DOC ([ADR-0026](../../decisions/0026-knowledge-architecture-truth-docs.md) D5). FOURTH topic backfill after `qa-automation` / `subagents` / `hooks` per [ADR-0030](../../decisions/0030-windows-gitbash-hardening.md) D5.

## Active bootstrap.sh steps + dependencies

Per [ADR-0008](../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D6 (bootstrap.sh canonical fresh-clone setup). Extended by [ADR-0030](../../decisions/0030-windows-gitbash-hardening.md) for cross-platform hardening (steps 7+8).

| Step | What it does | Dependency | Idempotent? | ADR |
|---|---|---|---|---|
| 1. Sanity check | Confirm inside git repo + `gh` authenticated | git, gh CLI | yes | [ADR-0008](../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D6 |
| 2. Label creation | Create 6 repo labels (`prd`, `slice`, `backlog`, `captured`, `trivial`, `needs-human`) | gh CLI | yes (skip if exists) | [ADR-0008](../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D6 |
| 3. Git hook install | `git config core.hooksPath .githooks` + `chmod +x` `.githooks/*` + `.claude/hooks/*.sh` | git | yes | [ADR-0008](../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D6 + [ADR-0023](../../decisions/0023-validation-and-notification-hooks-extension.md) D7 |
| 4. Project board detection | Find GitHub Project v2 board for owner; manual hint if missing | gh CLI + `project` scope | yes (detect only) | [ADR-0008](../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D6 |
| 5. Branch protection | Apply R1+R2 (require PR, no force-push, no deletion) to `main` | gh CLI + admin | yes | [ADR-0008](../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D6 |
| 6. yt-dlp dep check | Warn-only check for `/distill-video` skill prerequisite | yt-dlp (not auto-installed) | yes (warn-only) | [ADR-0019](../../decisions/0019-best-practices-kb-pattern.md) D3 |
| 7. jq install | Idempotent OS-specific install (winget on Windows / brew on macOS / apt on Linux) | winget / brew / apt-get | yes (skip if installed) | [ADR-0030](../../decisions/0030-windows-gitbash-hardening.md) D1 |
| 8. Playwright MCP install | `npx -y @playwright/mcp@latest install` if `--version` probe fails | Node.js + npm | yes (skip if callable) | [ADR-0025](../../decisions/0025-qa-tester-ui-mode-playwright.md) D7 + [ADR-0030](../../decisions/0030-windows-gitbash-hardening.md) D2 |

## Required external tools

- `git` (≥2.x)
- `gh` CLI (authenticated; `project` scope optional for board detection)
- `bash` (Git Bash on Windows; bash on macOS/Linux)
- `jq` (auto-installed by bootstrap.sh per [ADR-0030](../../decisions/0030-windows-gitbash-hardening.md) D1)
- `npx` / Node.js + npm (required for Playwright MCP install per [ADR-0030](../../decisions/0030-windows-gitbash-hardening.md) D2)
- `winget` (Windows) / `brew` (macOS) / `apt-get` (Linux) for jq auto-install
- `yt-dlp` (warn-only; required by `/distill-video` skill per [ADR-0019](../../decisions/0019-best-practices-kb-pattern.md) D3 — NOT auto-installed)

## Failure mode

Best-effort. `set -uo pipefail` only — NOT `-e`. Per-step failures warn and continue; the script never aborts on a single-step failure (per [ADR-0008](../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D6 policy, preserved by [ADR-0030](../../decisions/0030-windows-gitbash-hardening.md) D1+D2).

## Explicit deferrals (NOT done by bootstrap.sh)

Per [ADR-0008](../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D6 scope discipline (the comment-block at the top of `bootstrap.sh` itself):

- Matt Pocock skills install — user-level concern
- MCP server configuration — user-level concern
- CI / GitHub Actions / bot identity — deferred to PRD-CI
- Branch protection R3 (status checks) — deferred to PRD-CI
- Branch protection R4 (non-author review) — deferred to PRD-CI
- `--global` git config changes — out of scope
- `--check` / dry-run mode — YAGNI ([ADR-0008](../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) OQ)
- GitHub Project v2 board creation — complex GraphQL; manual

## Bootstrap-mode (forward-only)

Per [ADR-0030](../../decisions/0030-windows-gitbash-hardening.md) D8: cross-platform hardening binds FORWARD from slice 1 merge. Existing developer machines get jq + Playwright on next `bootstrap.sh` run (idempotent — safe re-run). No retroactive sweep of historical sessions.

## 6-critic-cap honored

`bootstrap.sh` adds NO critic per [ADR-0030](../../decisions/0030-windows-gitbash-hardening.md) D9. [ADR-0008](../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D7 6-critic-cap preserved.

## Sources

ADRs:

- [ADR-0008](../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D6 — bootstrap.sh canonical fresh-clone setup
- [ADR-0019](../../decisions/0019-best-practices-kb-pattern.md) D3 — yt-dlp dependency (warn-only)
- [ADR-0023](../../decisions/0023-validation-and-notification-hooks-extension.md) D7 — `.claude/hooks/*.sh` chmod step
- [ADR-0025](../../decisions/0025-qa-tester-ui-mode-playwright.md) D7 — Playwright MCP install requirement (OQ-4 completed by [ADR-0030](../../decisions/0030-windows-gitbash-hardening.md) D2)
- [ADR-0030](../../decisions/0030-windows-gitbash-hardening.md) — cross-platform hardening (this is the canonical 4th-topic truth-doc home)

Configuration + scripts:

- `bootstrap.sh` — the script itself (top-of-file scope comment is the most authoritative inline reference)
- `.githooks/pre-commit`, `.githooks/install.sh` — git hooks installed by step 3
- `.claude/hooks/*.sh` — Claude Code hook scripts chmod'd by step 3 ([ADR-0023](../../decisions/0023-validation-and-notification-hooks-extension.md) D7)

CLAUDE.md: "Map" row pointing to `bootstrap.sh` at repo root.

External: backlog [#222](https://github.com/vojtech-stas/project-claude/issues/222) — origin of the 3-layer defense proposal that became ADR-0030.
