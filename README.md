# MyCustomAiInstructions

Unified AI instruction repository for Claude Code, Codex, and other AI tools. This project maintains conversation guidelines (dez diretrizes) and code guidelines in version control, with tool-specific entry points that reference a shared source of truth.

## Structure

```
MyCustomAiInstructions/
├── README.md                        # This file
├── shared/
│   ├── conversation-guidelines.md   # 10 conversation & reasoning directives (Portuguese)
│   └── code-guidelines.md           # 4 coding discipline guidelines (English)
├── claude/
│   └── CLAUDE.md                    # Claude Code entry point (@import references shared/)
└── codex/
    └── AGENTS.md                    # Codex/Cursor entry point (embedded content)
```

## Installation

### For Claude Code

1. Move this folder to `~/Documents/MyCustomAiInstructions/`.
2. Copy `claude/CLAUDE.md` to `~/.claude/CLAUDE.md`:
   ```bash
   cp claude/CLAUDE.md ~/.claude/CLAUDE.md
   ```
3. Open a new Claude Code session. The `@import` directives in `CLAUDE.md` will resolve and load the shared guidelines automatically.

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
- Claude Code picks up changes automatically the next session.
- **For Codex**: manually paste the updated sections into `codex/AGENTS.md`. This is a temporary workaround until Codex gains import support.

**Versioning:**
- Commit this folder to git for version history and team sync.
- `shared/` is the source of truth; `codex/AGENTS.md` is a derived artifact (document this in your git history if you use hooks).

## Files Overview

### `shared/conversation-guidelines.md`
Ten directives for AI reasoning and communication style (Português):
1. Responsabilidade Extrema (Accountability Prompting)
2. Anti-Bajulação (Sycophancy Mitigation)
3. Sistematize o Repetível (Systematization Protocol)
4. Pense Antes de Responder (Clarification Prompting)
5. Elevação de Nível (Effort Scaffolding)
6. Execução Orientada por Meta (Self-Eval Prompting)
7. Recuo Estratégico (Step-Back Prompting)
8. Verificação em Cadeia (Chain of Verification)
9. Confiança Calibrada (Verbalized Confidence)
10. Refinamento de Pergunta (Prompt Refinement)

Plus style discipline rules: no preamble, avoid filler words, rhythm not staccato, zero em-dashes, right format for the task.

### `shared/code-guidelines.md`
Four directives for coding discipline (English):
1. **Think Before Coding** – State assumptions, surface tradeoffs, ask before acting.
2. **Simplicity First** – Minimum code, no speculative features or error handling.
3. **Surgical Changes** – Touch only what's required; don't "improve" adjacent code.
4. **Goal-Driven Execution** – Define success criteria, loop until verified (test-first pattern).

### `claude/CLAUDE.md`
Two `@import` lines that load the shared guidelines into Claude Code. Resolves at session startup.

### `codex/AGENTS.md`
Embedded concatenation of conversation + code guidelines for Codex. Update manually when `shared/` changes.

## Future

When Codex gains `@import` support, `codex/AGENTS.md` can be simplified to two lines, just like Claude's version. Until then, both files must be maintained (though `codex/AGENTS.md` is a derived file, so automate the sync if possible).

---

**Last updated:** July 24, 2026  
**Maintainer:** [@gersondantas](https://www.linkedin.com/in/gersonsantosss/)
