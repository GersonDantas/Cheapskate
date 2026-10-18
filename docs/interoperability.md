# Codex and Claude Code interoperability

`shared/` is the repository source of truth. Codex receives a generated bundle
because its instruction discovery uses `AGENTS.md`. Claude Code receives a
generated file of relative imports so the repository stays portable.

The installer copies sources into `~/.config/ai-instructions`. Global Codex and
Claude entry points contain generated bundles plus existing user instructions.
The installed Claude bundle embeds the shared content, avoiding relative import
resolution through a global symlink. The clone can move or disappear without
breaking the installation. Repository imports remain a maintenance adapter.

Host-specific rules stay in `codex/` and `claude/`. Shared policy must not be
copied into both host files manually.

Personal Agent Team is a Codex-only optional integration. Its plugin owns agent
configuration and injects its policy through its own trusted hook. Cheapskate
must not duplicate that policy in `AGENTS.md`.
