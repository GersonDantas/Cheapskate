# MyCustomAiInstructions

Unified AI instruction repository for Claude Code, Codex, and other AI tools. This project keeps compact working agreements and code guidelines in version control, with tool-specific entry points generated from a shared source of truth.

<p align="center">
  <a href="https://ko-fi.com/gerson_dantas" target="_blank" rel="noopener noreferrer">
    <img src="https://github.com/GersonDantas/img/blob/b81c0ba4adb694a7a65a91f64f7a1670d4d5c101/qrcode.png" alt="Buy Me a Coffee" height="200">
  </a>
</p>

<p align="center">Enjoying Agent Team Configurator? Support the project with a coffee ☕</p>


## Structure

```
MyCustomAiInstructions/
├── README.md                        # This file
├── shared/
│   ├── conversation-guidelines.md   # Communication, judgment, and scope
│   └── code-guidelines.md           # Minimal, surgical, verifiable coding
├── claude/
│   └── CLAUDE.md                    # Claude Code entry point (@import references shared/)
├── codex/
│   └── AGENTS.md                    # Generated Codex/Cursor entry point
└── scripts/
    ├── sync-instructions.sh         # Rebuilds the Codex bundle
    ├── eval-instructions.sh         # Compares baseline and current Codex behavior
    └── eval-claude-instructions.sh  # Compares baseline and current Claude behavior
```

## Installation

### For Claude Code

1. Move this folder to `~/Documents/MyCustomAiInstructions/`.
2. Generate a self-contained Claude instruction file from the shared guidelines:
   ```bash
   sh scripts/sync-instructions.sh
   mkdir -p ~/.claude
   { cat generic/INSTRUCTIONS.md; printf '\n\n'; cat claude/host-guidelines.md; } > ~/.claude/CLAUDE.md
   ```
3. Open a new Claude Code session. Repeat step 2 after editing the shared guidelines.

### For Codex/Cursor

1. Move this folder to `~/Documents/MyCustomAiInstructions/`.
2. Copy `codex/AGENTS.md` to `~/.codex/AGENTS.md`:
   ```bash
   cp codex/AGENTS.md ~/.codex/AGENTS.md
   ```
3. Open a new Codex/Cursor session. The guidelines are now active.

## Design Rationale

**Claude Code** supports dynamic `@import` syntax (including absolute paths, max 5 levels deep), so `claude/CLAUDE.md` stays small and always references the source files in `shared/`.

**Codex** does not support file imports in AGENTS.md (feature requested in [#17401](https://github.com/openai/codex/issues/17401) and [#6038](https://github.com/openai/codex/issues/6038)). Therefore, `codex/AGENTS.md` embeds the full content of `conversation-guidelines.md` + `code-guidelines.md`.

## Maintenance

**When updating guidelines:**
- Edit `shared/conversation-guidelines.md` or `shared/code-guidelines.md`.
- **For Claude Code**: regenerate and copy the self-contained file as shown above.
- **For Codex**: run `sh scripts/sync-instructions.sh` to rebuild `codex/AGENTS.md`.

**Versioning:**
- Commit this folder to git for version history and team sync.
- `shared/` is the source of truth; `codex/AGENTS.md` is a derived artifact (document this in your git history if you use hooks).

## Files Overview

### `shared/conversation-guidelines.md`
Compact agreements for communication, judgment, scope, autonomy, factual verification, and completion.

### `shared/code-guidelines.md`
Compact rules for assumptions, reuse, minimum code, surgical changes, reproduction, and validation.

### `claude/CLAUDE.md`
Two `@import` lines that load the shared guidelines into Claude Code. Resolves at session startup.

### `codex/AGENTS.md`
Generated concatenation of the shared conversation and code guidelines for Codex.

## Test before and after

Before committing, compare the current bundle with the version at `HEAD`:

```bash
sh scripts/eval-instructions.sh
```

Use a representative prompt from real work:

```bash
sh scripts/eval-instructions.sh \
  "Revise esta decisão, compare custo, risco e reversibilidade, e recomende uma opção."
```

The test uses isolated Codex homes, the same authentication, read-only mode, and ephemeral sessions. It prints both instruction sizes, both answers, and their diff. Repeat real prompts and compare completion, style violations, unnecessary questions, unsupported claims, scope expansion, and answer length. After committing, set `BASELINE_REF=HEAD^` to compare with the previous commit.

Run the equivalent comparison with Claude Code:

```bash
sh scripts/eval-claude-instructions.sh \
  "Revise esta decisão, compare custo, risco e reversibilidade, e recomende uma opção."
```

The Claude test uses `--safe-mode`, disables tools and session persistence, and replaces the system prompt with the selected instruction bundle. It reports both answers, usage, cost, and their diff. Set `CLAUDE_EVAL_MODEL` or `CLAUDE_EVAL_EFFORT` to change the shared model configuration. If the Claude OAuth session has expired, run `claude auth login` first.

## Future

When Codex gains `@import` support, `codex/AGENTS.md` can be simplified to two lines, just like Claude's version. Until then, edit `shared/` and regenerate the derived bundle with `scripts/sync-instructions.sh`.

---

**Last updated:** August 2, 2026
**Maintainer:** [@gersondantas](https://www.linkedin.com/in/gersonsantosss/)
