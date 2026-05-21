# Code with Claude London 2026 — Opening Keynote (distilled)

The opening keynote from Anthropic's Code with Claude London 2026 conference (https://www.youtube.com/watch?v=6amLO7I9xdg), uploaded 2026-05-19 on the `@claude` YouTube channel; runtime 46m 27s. The speaker is not identified by name in the auto-captions but speaks in first-person on behalf of Anthropic — referring throughout to "we at Anthropic" and walking through Anthropic's product line including Claude Opus 4.6/4.7 ("Mythos preview"), Claude Managed Agents, the Claude API, and Claude Code. The talk frames the developer takeaway as building scaffolding and evals that absorb each next-generation model upgrade, then demos several Anthropic-built reference workflows (a growth agent for an AI-native business, async routines, CI autofix).

The 8 recommendations below are extracted as best-practice imperatives directly applicable to this project's agent/skill/ADR conventions. Each cites a single representative `(HH:MM:SS)` timestamp; the full transcript at [`6amLO7I9xdg.vtt`](transcripts/6amLO7I9xdg.vtt) is the audit source.

## Best-practice recommendations

- **Build for emerging capabilities, not just what works today.** Architect agent systems so that each new Claude release can be slotted in without rewriting scaffolding; the developers who win are the ones whose architecture is ready to absorb the next big capability jump. `(00:18:42)` This argues against over-fitting prompts and scaffolds to the current model's quirks — keep the substrate general and the model substitutable.

- **Strip scaffolding as models get smarter.** Loops, hand-crafted instructions, and narrow tools that helped earlier models can actively hold a more capable model back. More-intelligent models often go further with generalized primitives like a filesystem and a sandboxed compute environment than with bespoke per-task tooling. `(00:19:09)` For this project: prefer simple Read/Write/Bash tool boundaries over elaborate orchestration scaffolds; revisit subagent prompts when a new model lands.

- **Maintain harder evals and product prototypes — they are how you notice the exponential moving underneath you.** When a task that used to fail starts passing on a model upgrade, that is the signal to ship something you previously couldn't. Without forward-looking evals you miss the unlock. `(00:19:33)` Maps to this project as: keep a backlog of "doesn't-work-yet" stress-test prompts and re-run them on each Claude release; treat upgrade days as eval-rerun days.

- **Treat model upgrades as a business advantage, not just a dependency bump.** The teams getting the most out of Claude treat each upgrade as an opportunity to expand product surface and customer value, not a maintenance chore to back-compat. `(00:19:56)` In this project's terms: a Claude release should trigger a PRD-shaped "what newly works" investigation, not just a sed-replace in subagent frontmatter.

- **Design agent surfaces around general MCP servers rather than bespoke per-task tools.** The reference growth-agent demo wires Slack, a data warehouse, and a feature-flag service to Claude via MCP servers — each a general-purpose connection that the agent decides how to combine. `(00:26:55)` Implication for this project's future agent surfaces: when a sibling skill needs an external system, reach for an MCP server first; bespoke skill-internal shell-outs are the YAGNI fallback.

- **Synchronous chat is now just one slice of how code gets written; design for async too.** A growing share of real production code is authored by async routines — long-running automations that watch repos, issues, or webhooks and wake the developer up to ready-to-merge PRs. `(00:42:26)` This validates this project's `/ship` autonomous-pipeline direction and the `implementer → reviewer → auto-merge` chain (per ADR-0010); synchronous human prompting becomes one channel among many, not the central interface.

- **Invest in verification so agents can run unattended.** The reason async coding is workable is that Claude can check its own work — when verification is solid, the developer can let the agent run while they focus elsewhere and come back to a working result. Skimping on verification breaks the async model. `(00:42:39)` Maps directly to this project's critic-pair pattern (ADR-0003 D2): every generation stage paired with an adversarial critic is the verification substrate that makes the autonomous pipeline trustable.

- **Use routines as higher-order prompts kicked off by schedule, webhook, or API.** Routines are the abstraction above one-shot prompting — a developer authors a routine that does the prompting, rather than doing the prompting themselves. They run locally or on remote compute and integrate with CI for autofix-style flows. `(00:43:01)` Suggests a future direction for this project: surface `/ship`, `/audit-meta`, and `/distill-video` as routine-shaped invocations that can be triggered by GitHub Actions (post-#63 CI) for unattended PRD/audit/distillation cadence per ADR-0019 D6's future-direction note.

## Authority

- **Source:** https://www.youtube.com/watch?v=6amLO7I9xdg
- **Channel:** Claude (`@claude`)
- **Upload date:** 2026-05-19
- **Duration:** 46m 27s
- **Raw transcript:** [`6amLO7I9xdg.vtt`](transcripts/6amLO7I9xdg.vtt)
- **Distilled by:** `/distill-video` skill (per [ADR-0019](../../decisions/0019-best-practices-kb-pattern.md))

## Distillation notes

The originally-targeted opening keynote for this slice was video ID `GMIWm5y90xA` (Code with Claude 2026: Opening Keynote, San Francisco edition). As of the slice-1 implementation run, that video has **no automatic captions and no manually-uploaded subtitles** available via `yt-dlp` across all probed YouTube player clients (`android_vr`, `web`, `tv`, `android`, `ios`) — likely because YouTube's automatic captioning has not yet processed the recently-uploaded talk. The `/distill-video` skill correctly surfaces this as an exit-non-zero failure mode per its Phase 1 VTT sanity check (slice acceptance criterion 12). The London 2026 opening keynote `6amLO7I9xdg` was substituted as the closest-equivalent walking-skeleton candidate from the same `@claude` channel — same talk format (Anthropic opening keynote), same content domain (Anthropic developer guidance), full English auto-captions available. The originally-targeted video can be re-distilled by re-running `/distill-video GMIWm5y90xA` once YouTube generates its auto-captions.
