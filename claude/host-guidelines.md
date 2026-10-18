# Host-specific notes

When the configured Claude Code RTK hook is active, it handles supported shell
commands. Do not add a second `rtk` prefix in that case. If the hook is inactive,
invoke RTK explicitly. Use `rtk gain`, `rtk discover`, and `rtk proxy <command>`
directly when needed.

When available, use the Graphify skill explicitly and on demand. Do not add a
Graphify PreToolUse hook or consult Graphify before every repository search.
