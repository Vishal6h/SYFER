#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODEL="$ROOT/model/SYFER-v1-Q4_K_M.gguf"
MODELFILE="$ROOT/release/Modelfile"
PROMPT="$ROOT/assets/system-prompt.txt"
command -v python3 >/dev/null 2>&1 || { echo 'ERROR: Python 3 is required.' >&2; exit 1; }
command -v sha256sum >/dev/null 2>&1 || { echo 'ERROR: sha256sum is required.' >&2; exit 1; }

if ! command -v ollama >/dev/null 2>&1; then
    echo 'ERROR: Ollama is not installed.' >&2
    echo "Install Ollama first, then rerun this script."
    exit 1
fi

if [ ! -f "$MODEL" ]; then
    echo 'ERROR: SYFER model file not found.' >&2
    echo
    echo "Expected:"
    echo "$MODEL"
    echo
    echo "Download SYFER-v1-Q4_K_M.gguf from:"
    echo "https://github.com/Vishal6h/SYFER"
    exit 1
fi

(cd "$ROOT/model" && sha256sum -c "$ROOT/release/checksums.txt") || { echo 'ERROR: SYFER model checksum failed.' >&2; exit 1; }

[[ -f "$PROMPT" ]] || { echo 'ERROR: SYFER system prompt is missing.' >&2; exit 1; }
cat > "$MODELFILE" <<EOF2
FROM $MODEL

PARAMETER temperature 0
PARAMETER num_ctx 32768

SYSTEM """
$(cat "$PROMPT")
"""
EOF2

echo
echo 'Creating SYFER v1 in Ollama...'

ollama create syfer:v1 -f "$MODELFILE"

echo
echo 'SYFER v1 installed successfully.'
echo
echo "Run it with:"
echo "./scripts/run_syfer.sh"
