#!/bin/sh
set -eu

root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
baseline_ref=${BASELINE_REF:-HEAD}
candidate=${CANDIDATE_AGENTS:-"$root/codex/AGENTS.md"}
prompt=${1:-"Compare duas opções plausíveis para uma decisão importante, explicite os critérios e recomende uma delas. Seja direto e não invente contexto ausente."}
codex_home=${CODEX_HOME:-"$HOME/.codex"}

for file in "$candidate" "$codex_home/auth.json"; do
  if [ ! -f "$file" ]; then
    printf 'Missing required file: %s\n' "$file" >&2
    exit 1
  fi
done

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT HUP INT TERM
baseline="$tmp/baseline.md"

if ! git -C "$root" show "$baseline_ref:codex/AGENTS.md" >"$baseline"; then
  printf 'Could not read codex/AGENTS.md from %s. Set BASELINE_REF to a valid revision.\n' "$baseline_ref" >&2
  exit 1
fi

run_case() {
  label=$1
  instructions=$2
  home="$tmp/$label-home"
  project="$tmp/$label-project"
  output="$tmp/$label.md"

  mkdir -p "$home" "$project"
  ln -s "$codex_home/auth.json" "$home/auth.json"
  cp "$instructions" "$home/AGENTS.md"

  CODEX_HOME="$home" codex exec \
    --ephemeral \
    --ignore-user-config \
    --skip-git-repo-check \
    --sandbox read-only \
    --cd "$project" \
    --output-last-message "$output" \
    "$prompt" </dev/null >/dev/null
}

printf 'Instruction size\n'
wc -w -c "$baseline" "$candidate"
printf '\nRunning the same prompt with isolated Codex homes...\n'
run_case before "$baseline"
run_case after "$candidate"

printf '\nBEFORE\n\n'
sed -n '1,240p' "$tmp/before.md"
printf '\nAFTER\n\n'
sed -n '1,240p' "$tmp/after.md"
printf '\nDIFF\n\n'
diff -u "$tmp/before.md" "$tmp/after.md" || true
