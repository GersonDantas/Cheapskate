# Decision record

## Product boundary

- Support Codex and Claude Code.
- Target macOS first.
- Store desired reproducible state, not a literal home-directory backup.
- Exclude credentials, sessions, caches, histories, private evaluations, and
  project indexes.
- Keep active installation independent from the repository clone.

## Token reduction

- Combine RTK with Caveman only across non-overlapping layers.
- Use CodeGraph for precise code navigation and Graphify for broad exploration.
- Never add savings percentages from separate tools.
- Describe RTK statistics as output estimates until a controlled end-to-end
  benchmark observes provider token usage.

## Distribution

- Pin managed dependency versions and update them explicitly.
- Install missing dependencies only after diagnosis, preview, and confirmation.
- Keep Personal Agent Team optional. Cheapskate may install it but must not
  configure its models, permissions, workflows, triggers, or limits.
- Preserve user changes and create private backups before future installation
  writes.

## Installer implementation

- Use Python 3.11 standard library and one command for all lifecycle operations.
- Preserve whole-file originals conservatively; later user edits block automatic
  update/removal rather than being overwritten.
- Treat dependency and plugin installation as external effects. File rollback
  does not uninstall packages or remove marketplaces.
- Embed the installed Claude instructions to avoid symlink/import ambiguity.
- In Codex, use explicit RTK invocations assisted by hook hints. The documented
  rewrite contract requires an allow decision, so automatic rewrite is omitted
  to preserve ordinary tool permission processing.
- In Claude, return updated input without an allow decision.
- Keep the team plugin optional and select it before managing Codex config.
