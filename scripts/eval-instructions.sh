#!/bin/sh
set -eu
root=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
exec python3 "$root/scripts/eval-pair.py" codex "${1:-Compare duas opções para uma decisão importante, explicite os critérios e recomende uma delas.}"
