# Managed-state inventory

This inventory defines the boundary between repository sources, generated
artifacts, future installer state, and private machine data.

| Item | Repository status | Installation status |
|---|---|---|
| Shared behavioral guidelines | Source | Copy to managed installation |
| Codex `AGENTS.md` | Generated | Installed bundle preserves global user instructions |
| Claude `CLAUDE.md` | Generated imports | Installed embedded bundle avoids symlink imports |
| Generic instructions | Generated | Optional copy for other hosts |
| RTK and graph host notes | Source | Copy with host adapter |
| Synthetic evaluation cases | Source | Optional developer tooling |
| Evaluation baseline | Immutable public fixture | Optional developer tooling |
| Real prompt previews and runs | Ignored | Private local files only |
| Authentication and credentials | Excluded | Never read or copy during installation |
| Sessions and histories | Excluded | Read only by explicit private prompt collection |
| Tool caches and graph indexes | Excluded | Never copy or initialize automatically |
| Dependency versions | Verified artifact manifest | Private versioned runtime for missing tools |
| Hooks and MCP registration | Installer and hook sources | Diagnose, preview, back up, then apply |
| Personal Agent Team policy | External optional plugin | Detect or install only; never configure |

The repository is the source for public desired state. The future active
installation under `~/.config/ai-instructions` is derived state. Backups and an
ownership journal remain private and must not be committed.
