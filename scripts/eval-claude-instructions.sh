#!/bin/sh
set -eu

root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
baseline_ref=${BASELINE_REF:-HEAD}
prompt=${1:-"Compare duas opções plausíveis para uma decisão importante, explicite os critérios e recomende uma delas. Seja direto e não invente contexto ausente."}
model=${CLAUDE_EVAL_MODEL:-sonnet}
effort=${CLAUDE_EVAL_EFFORT:-medium}

for command in claude jq; do
  if ! command -v "$command" >/dev/null 2>&1; then
    printf 'Missing required command: %s\n' "$command" >&2
    exit 1
  fi
done

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT HUP INT TERM
before_bundle="$tmp/before-instructions.md"
after_bundle="$tmp/after-instructions.md"

for name in conversation-guidelines.md code-guidelines.md; do
  git -C "$root" show "$baseline_ref:shared/$name" >>"$before_bundle"
  printf '\n' >>"$before_bundle"
  sed -n '1,400p' "$root/shared/$name" >>"$after_bundle"
  printf '\n' >>"$after_bundle"
done

run_case() {
  label=$1
  instructions=$2
  output="$tmp/$label.json"

  if ! claude -p \
      --safe-mode \
      --tools '' \
      --model "$model" \
      --effort "$effort" \
      --no-session-persistence \
      --output-format json \
      --system-prompt "$(sed -n '1,1200p' "$instructions")" \
      "$prompt" >"$output"; then
    if jq -e . "$output" >/dev/null 2>&1; then
      jq -r '.result // "Claude evaluation failed."' "$output" >&2
    else
      printf 'Claude evaluation failed before returning valid JSON.\n' >&2
    fi
    exit 1
  fi

  if ! jq -e '.is_error == false' "$output" >/dev/null; then
    jq -r '.result' "$output" >&2
    exit 1
  fi
}

printf 'Instruction size\n'
wc -w -c "$before_bundle" "$after_bundle"
printf '\nRunning model=%s effort=%s with safe mode and no tools...\n' "$model" "$effort"
run_case before "$before_bundle"
run_case after "$after_bundle"

jq -r '.result' "$tmp/before.json" >"$tmp/before.md"
jq -r '.result' "$tmp/after.json" >"$tmp/after.md"

printf '\nBEFORE\n\n'
sed -n '1,240p' "$tmp/before.md"
printf '\nAFTER\n\n'
sed -n '1,240p' "$tmp/after.md"
printf '\nUSAGE\n\n'
jq '{label: "before", total_cost_usd, usage}' "$tmp/before.json"
jq '{label: "after", total_cost_usd, usage}' "$tmp/after.json"
printf '\nDIFF\n\n'
diff -u "$tmp/before.md" "$tmp/after.md" || true
