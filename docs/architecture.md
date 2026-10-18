# Architecture

Cheapskate is a reproducible configuration and evaluation toolkit for reducing
avoidable context in Codex and Claude Code. It does not claim that every task or
provider bill will be smaller.

## Layers

1. `shared/` is the portable source of behavioral instructions.
2. `codex/` contains Codex-specific generated instructions and host notes.
3. `claude/` contains Claude Code imports and host notes.
4. `generic/` is a generated bundle for hosts without imports.
5. `evals/` contains public synthetic cases and immutable public baselines.
6. `evals/local/` contains private prompts and run artifacts and is ignored.

## Tool boundaries

- RTK compresses supported terminal output. Its gain is an estimate, not billing.
- Caveman lite makes conversational prose concise. RTK remains responsible for
  terminal output, so the Caveman proxy is not enabled.
- CodeGraph answers precise code structure questions when a repository already
  has a `.codegraph/` index.
- Graphify is an explicit, on-demand tool for broad cross-source exploration.
- Personal Agent Team is optional and independently owns agent models,
  workflows, triggers, response contracts, and limits.

`scripts/cheapskate.py` manages an explicit set of files with private snapshots,
a write-ahead journal, a process lock, and conflict checks. `dependencies.json`
pins verified main artifacts and skills. External package/plugin installation
has separate effects and is not claimed as reversible by the file journal.

`scripts/bootstrap.sh` runs before the Python installer. It prepares missing
macOS packages and clients through Homebrew, arranges shell PATH, checks each
client's authentication state, and delegates the Cheapskate file changes to the
Python installer. Homebrew changes, shell profile edits, and client logins stay
outside the file journal and are not reverted by rollback.

The installed Claude adapter embeds the shared content. The Codex RTK hook
supplies mapping hints without returning permission decisions; the Claude hook
can rewrite input while leaving its permission decision untouched. See
`installation.md` for the runtime and rollback boundaries.
