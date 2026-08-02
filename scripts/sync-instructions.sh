#!/bin/sh
set -eu

root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)

{
  printf '%s\n\n' '<!-- Generated file. Do not edit directly. Source: shared/*.md. -->'
  cat "$root/shared/conversation-guidelines.md"
  printf '\n\n'
  cat "$root/shared/code-guidelines.md"
} > "$root/codex/AGENTS.md"

printf 'Synchronized codex/AGENTS.md.\n'
