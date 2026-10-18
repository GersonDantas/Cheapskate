#!/bin/sh
set -eu

root=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)

conversation="$root/shared/conversation-guidelines.md"
code="$root/shared/code-guidelines.md"
rtk="$root/shared/rtk-guidelines.md"
codegraph="$root/shared/codegraph-guidelines.md"
graphify="$root/shared/graphify-guidelines.md"
caveman="$root/shared/caveman-guidelines.md"
codex_rtk="$root/codex/rtk-guidelines.md"

{
  printf '%s\n\n' '<!-- Generated file. Do not edit directly. Source: shared/*.md and codex/rtk-guidelines.md. -->'
  cat "$conversation"
  printf '\n\n'
  cat "$code"
  printf '\n\n'
  cat "$rtk"
  printf '\n\n'
  cat "$codegraph"
  printf '\n\n'
  cat "$graphify"
  printf '\n\n'
  cat "$caveman"
  printf '\n\n'
  cat "$codex_rtk"
} > "$root/codex/AGENTS.md"

{
  printf '%s\n\n' '<!-- Generated file. Do not edit directly. Source: shared/*.md and claude/host-guidelines.md. -->'
  printf '%s\n\n' '@../shared/conversation-guidelines.md'
  printf '%s\n\n' '@../shared/code-guidelines.md'
  printf '%s\n\n' '@../shared/rtk-guidelines.md'
  printf '%s\n\n' '@../shared/codegraph-guidelines.md'
  printf '%s\n\n' '@../shared/graphify-guidelines.md'
  printf '%s\n\n' '@../shared/caveman-guidelines.md'
  printf '%s\n' '@host-guidelines.md'
} > "$root/claude/CLAUDE.md"

mkdir -p "$root/generic"
{
  printf '%s\n\n' '<!-- Generated file. Do not edit directly. Source: shared/*.md. -->'
  cat "$conversation"
  printf '\n\n'
  cat "$code"
  printf '\n\n'
  cat "$rtk"
  printf '\n\n'
  cat "$codegraph"
  printf '\n\n'
  cat "$graphify"
  printf '\n\n'
  cat "$caveman"
} > "$root/generic/INSTRUCTIONS.md"

printf 'Synchronized Codex, Claude, and generic instruction bundles.\n'
