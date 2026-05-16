# Glossary — long-tail

Long-tail vocabulary for this project. Read on-demand by agents when an unfamiliar term comes up. The auto-loaded key-zone lives in [`CLAUDE.md`](CLAUDE.md) under `## Glossary (key terms)`; this file holds everything else.

Each entry follows the canonical shape from [ADR-0007](decisions/0007-vocabulary-glossary-and-grill-me-extension.md) D2: **term + one-sentence definition + authority + (optional) see-also**. Authority cites `ADR-NNNN D-X`, an external URL, or the literal string `external`.

Entries are sorted alphabetically. To add a term, run `/glossary-add` (per [ADR-0007](decisions/0007-vocabulary-glossary-and-grill-me-extension.md) D4); the [`glossary-critic`](.claude/agents/glossary-critic.md) subagent gates each addition.

---

## Entries

### hamburger method

A vertical-slicing technique that decomposes a feature into thin end-to-end slices cutting through every layer (schema, logic, UI, test) rather than building one horizontal layer at a time.

- **Scope category:** (b) external standard adopted
- **Authority:** https://gojko.net/2012/05/01/the-hamburger-method/
- **See also:** SPIDR; walking-skeleton; slice
