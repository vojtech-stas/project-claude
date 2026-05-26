---
title: R-SECRETS — reviewer hard-block on secret-shaped strings in diff
summary: The reviewer rule that BLOCKs any PR whose diff contains secret-shaped strings (API keys, tokens, credentials, private keys, .env files other than .env.example).
tags: [rule, reviewer-rubric, hard-block]
type: concept
last_updated: 2026-05-26
sources:
  - .claude/agents/reviewer.md rule 6
---

# R-SECRETS

**R-SECRETS** is rule 6 in the [`reviewer`](../../../.claude/agents/reviewer.md) rubric. It hard-blocks any PR whose diff contains secret-shaped strings or whose diff adds `.env*` files (other than `.env.example`). The rule is a grep-mechanical first-line defense against credential leaks; once a secret reaches `main`, rotation is mandatory and the audit cost is permanent.

## What

The rule fires on every PR. Mechanics:

- Reviewer scans the diff for known secret-shape patterns.
- Any hit → BLOCK with `secret leak: <pattern> at <file>:<line>`.

Patterns the reviewer greps for:

- `sk_` (Stripe-style secret keys)
- `gho_`, `ghp_`, `ghs_` (GitHub tokens)
- `AKIA` (AWS access keys)
- `BEGIN RSA PRIVATE KEY`, `BEGIN OPENSSH PRIVATE KEY`, `BEGIN PGP PRIVATE KEY` (private-key blocks)
- `password\s*=` (literal password assignments)
- `api_key\s*=` (literal API-key assignments)

Files the reviewer blocks on addition:

- `.env`, `.env.local`, `.env.production`, etc.
- `credentials.json`, `service-account.json`, anything ending in `.pem`, `.key`.

Whitelisted (not blocked):

- `.env.example` (template files for human reference).
- Documentation explaining what the patterns look like (e.g., this rule note itself contains the patterns as documentation).

## Why

R-SECRETS exists because **the cost asymmetry between false-positives and false-negatives is extreme**. A false-positive BLOCK costs the implementer one revision cycle to either remove the secret-shaped string or document why it's a false positive (e.g., in a `.example` file). A false-negative APPROVE costs credential rotation across every service the secret authorizes, plus permanent presence in git history requiring a rewrite or BFG to fully purge.

The grep-only mechanism is intentionally over-eager. A discriminator like "is the secret actually valid?" would require active API calls and would still miss revoked-but-not-deleted credentials. Pattern-match-on-shape is the right precision-vs-recall trade-off for a credential-leak detector: high recall, calibrated precision via the whitelist.

## How to check

```bash
gh pr diff <PR> --patch | grep -E '(sk_|gho_|ghp_|ghs_|AKIA|BEGIN.*PRIVATE KEY|password\s*=|api_key\s*=)'
gh pr view <PR> --json files --jq '.files[] | select(.path | test("^\\.env|credentials\\.json|\\.pem$|\\.key$"))'
```

Any hit → BLOCK with the exact pattern + file:line.

## Exemptions

- **`.env.example`** template files (human reference; no actual secrets).
- **Documentation files** (e.g., security policy docs, this rule note) that mention the patterns as examples — distinguish via context: pattern inside a markdown code fence labeled `documentation` or in a heading like "patterns we block on" is documentation; pattern in a config file is a real secret.

## Recovery

If R-SECRETS fires legitimately (the secret was committed by mistake):

1. **Do NOT just remove the line in a follow-up commit** — the secret remains in git history. Rotate the credential immediately.
2. Revert the PR.
3. Force-rewrite history with `git filter-repo` or BFG if the leak reached `main` (last-resort; coordinate with collaborators).
4. Re-open the PR with the secret replaced by a placeholder + the real value moved to a `.env` file (gitignored).

## Examples

- **PR adds `OPENAI_API_KEY=sk-proj-...`** to a config file: BLOCK at the `sk_` pattern.
- **PR adds `.env.example` with `OPENAI_API_KEY=sk-your-key-here`**: PASS — `.env.example` is whitelisted; the example value isn't a real key.

## Edges

- **part_of:** [[entities/subagents/reviewer]]
- **part_of:** [[topics/reviewer-philosophy]]
