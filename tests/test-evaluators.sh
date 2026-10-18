#!/bin/sh
set -eu

root=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT HUP INT TERM
fake_bin="$tmp/bin"
codex_home="$tmp/codex-home"
mkdir -p "$fake_bin" "$codex_home"
printf '{}\n' >"$codex_home/auth.json"

cat >"$fake_bin/codex" <<'EOF'
#!/bin/sh
set -eu
output=
while [ "$#" -gt 0 ]; do
  case "$1" in
    --output-last-message)
      output=$2
      shift 2
      ;;
    *)
      shift
      ;;
  esac
done
test -n "$output"
printf 'offline codex result\n' >"$output"
printf '%s\n' '{"usage":{"input_tokens":10,"output_tokens":3,"total_tokens":13}}'
EOF

cat >"$fake_bin/claude" <<'EOF'
#!/bin/sh
printf '%s\n' '{"is_error":false,"result":"offline claude result","total_cost_usd":0,"usage":{"input_tokens":10,"output_tokens":3}}'
EOF

chmod +x "$fake_bin/codex" "$fake_bin/claude"

for order in before-first after-first; do
  PATH="$fake_bin:$PATH" CODEX_HOME="$codex_home" EVAL_ORDER="$order" \
    sh "$root/scripts/eval-instructions.sh" "offline test" >/dev/null
  PATH="$fake_bin:$PATH" EVAL_ORDER="$order" \
    sh "$root/scripts/eval-claude-instructions.sh" "offline test" >/dev/null
done

cat >"$fake_bin/claude" <<'EOF'
#!/bin/sh
printf 'not-json\n'
EOF
chmod +x "$fake_bin/claude"
if PATH="$fake_bin:$PATH" sh "$root/scripts/eval-claude-instructions.sh" "offline test" >/dev/null 2>&1; then
  printf 'Claude evaluator accepted invalid JSON.\n' >&2
  exit 1
fi

cat >"$fake_bin/codex" <<'EOF'
#!/bin/sh
exit 7
EOF
chmod +x "$fake_bin/codex"
if PATH="$fake_bin:$PATH" CODEX_HOME="$codex_home" \
    sh "$root/scripts/eval-instructions.sh" "offline test" >/dev/null 2>&1; then
  printf 'Codex evaluator accepted a failed client.\n' >&2
  exit 1
fi

suite_dir="$tmp/suite"
mkdir -p "$suite_dir/scripts"
cp "$root/scripts/eval-suite.py" "$suite_dir/scripts/eval-suite.py"
cp "$root/scripts/evaluation_report.py" "$suite_dir/scripts/evaluation_report.py"
cp "$root/scripts/eval-instructions.sh" "$suite_dir/scripts/eval-instructions.sh"
real_dir="$suite_dir/evals/local"
mkdir -p "$real_dir"
printf '%s\n' '{"id":"private-01","prompt":"private","critical":false}' >"$real_dir/real-prompt-preview.jsonl"
marker="$tmp/provider-called"
cat >"$fake_bin/codex" <<EOF
#!/bin/sh
touch "$marker"
exit 1
EOF
chmod +x "$fake_bin/codex"
if PATH="$fake_bin:$PATH" python3 "$suite_dir/scripts/eval-suite.py" \
    --source real --hosts codex --run --approve-sha invalid >/dev/null 2>&1; then
  printf 'Real evaluation accepted an invalid digest.\n' >&2
  exit 1
fi
if [ -e "$marker" ]; then
  printf 'Provider was called before real-prompt digest validation.\n' >&2
  exit 1
fi
rm -f "$real_dir/real-prompt-preview.jsonl"

printf 'Evaluator wrappers passed offline.\n'
