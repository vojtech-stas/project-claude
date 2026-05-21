# Installing Claude Code (distilled)

The second video in Anthropic's "Claude Code 101" playlist on the `@claude` YouTube channel (https://www.youtube.com/watch?v=0kILa02vKuI), uploaded 2026-05-14; runtime 3m 1s. The speaker is not identified by name in the auto-captions and narrates a short procedural walkthrough of every supported way to install and launch Claude Code — terminal (macOS/Linux/WSL via curl or Homebrew; Windows via PowerShell `Invoke-RestMethod`, curl in CMD, or winget), IDEs (VS Code marketplace extension, JetBrains Marketplace plugin), Claude Desktop's "Code" toggle, and the web at `claude.ai/code`. The auto-captions consistently mis-transcribe "Claude" as "Cloud" throughout; the recommendations below paraphrase the speaker's intent rather than the literal caption text.

The 7 recommendations below are extracted as best-practice imperatives for choosing AND maintaining a Claude Code install across the supported surfaces. Each cites a single representative `(HH:MM:SS)` timestamp; the full transcript at [`0kILa02vKuI.vtt`](transcripts/0kILa02vKuI.vtt) is the audit source.

## Best-practice recommendations

- **Prefer the one-shot curl install on macOS/Linux/WSL.** The official curl-piped install command installs Claude Code in a single step on Unix-like systems and is the path that auto-updates work against. `(00:00:15)` For this project's `bootstrap.sh`, the curl install is the canonical fresh-clone install path on every developer machine that isn't pinned to Homebrew/winget for policy reasons.

- **If you install via Homebrew or winget, accept that you lose auto-update.** Both `brew install` and `winget install` are supported, but the speaker calls out explicitly that neither package manager ships Claude Code's auto-update mechanism — you must manually re-`brew upgrade` / `winget upgrade` to pick up new releases. `(00:00:35)` Implication for this project: if a contributor reports a stale Claude Code version on Mac or Windows, ask first whether they installed via a package manager before debugging the symptom.

- **Run `claude` from the project directory you want it to operate on — directory scope is the access boundary.** Whatever directory you run Claude Code in becomes its working scope, and it gains access to that directory AND all of its subfolders. `(00:00:57)` Maps directly to this project's worktree-per-agent pattern: every implementer subagent operates from inside its own slice worktree precisely so the project root is its access boundary, not an unrelated parent dir.

- **Pick the auth tier that matches your org's plan — Pro, Max, Enterprise, or raw API key — and explicitly select Enterprise if your org has one.** During first-run setup Claude Code prompts for sign-in and offers all four paths; if your organization has a Claude Enterprise account you must select that option explicitly rather than defaulting to a personal Pro/Max session. `(00:00:48)` Relevant whenever this project's CLAUDE.md mentions auth-tier assumptions — keep the Enterprise-vs-personal distinction explicit in any contributor-onboarding docs.

- **For VS Code, install via the Extensions panel (look for the blue verified-publisher check) and restart the editor.** Search "Claude Code" in the VS Code Extensions panel, verify the extension is the Anthropic-published one (blue check), install, then restart VS Code before invoking. `(00:01:09)` The blue-check verification step is the practical anti-phishing check for any IDE Marketplace install of a Claude tool — apply the same vigilance for the JetBrains Marketplace plugin.

- **You can opt the IDE integration out of the GUI and use the terminal experience directly via the IDE's settings file.** The IDE integration ships a UI by default, but for users who prefer the terminal-style experience the speaker explicitly calls out a settings-file opt-out. `(00:01:25)` Useful when this project's contributors prefer the terminal-first workflow even from inside VS Code — pure-terminal Claude Code keeps tool-output formatting identical across IDE-launched and standalone-shell sessions.

- **Use the terminal install if you want features the day they ship; use Desktop for background runs; use the web for GitHub-repo remote work or parallel sessions.** The speaker explicitly orders the install surfaces by feature-velocity (terminal ships first) and by use case: Desktop is best for letting Claude run in the background while you do other things, and Claude Code on the web (restricted to GitHub repositories) is the option for remote work or multiple parallel sessions on the same project. `(00:02:30)` For this project's autonomous-pipeline direction (per ADR-0010), the terminal surface is the right primary target; the web surface's parallel-sessions capability maps onto the `/ship` DAG-batch dispatch pattern as a future-direction note.

## Authority

- **Source:** https://www.youtube.com/watch?v=0kILa02vKuI
- **Channel:** Claude (`@claude`)
- **Upload date:** 2026-05-14
- **Duration:** 3m 1s
- **Raw transcript:** [`0kILa02vKuI.vtt`](transcripts/0kILa02vKuI.vtt)
- **Distilled by:** `/distill-video` skill (per [ADR-0019](../../decisions/0019-best-practices-kb-pattern.md))

## Distillation notes

The Claude Code 101 playlist (`PLmWCw1CzcFilebjK89WLb5cAvM8K0cLB3`) was enumerated chronologically via `yt-dlp --flat-playlist`; this video is the **chronologically-second** entry (playlist index 2, zero-based index 1) per the slice-3 (#150) deterministic-selection protocol. The chronologically-first entry — "What is Claude Code?" (`fl1DSmwQKKY`) — is the target of slice-2 (#149) per the sibling-coordination convention. The auto-caption mis-transcription of "Claude" as "Cloud" throughout this video is documented here so future re-distillations don't propagate the error into the recommendations.
