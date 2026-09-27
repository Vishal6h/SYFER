#!/usr/bin/env bash
set -e

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODEL="$ROOT/release/SYFER-v1-Q4_K_M.gguf"
MODELFILE="$ROOT/release/Modelfile"
BANNER="$ROOT/assets/syfer-banner.txt"

CYAN='\033[0;36m'
WHITE='\033[0;37m'
GREEN='\033[0;32m'
RED='\033[0;31m'
RESET='\033[0m'

clear

printf "${CYAN}"
head -n 6 "$BANNER"
printf "${RESET}"

printf "${WHITE}"
tail -n +7 "$BANNER"
printf "${RESET}"

echo

if ! command -v ollama >/dev/null 2>&1; then
    printf "${RED}ERROR: Ollama is not installed.${RESET}\n"
    echo "Install Ollama first, then rerun this script."
    exit 1
fi

if [ ! -f "$MODEL" ]; then
    printf "${RED}ERROR: SYFER model file not found.${RESET}\n"
    echo
    echo "Expected:"
    echo "$MODEL"
    echo
    echo "Download SYFER-v1-Q4_K_M.gguf from:"
    echo "https://github.com/Vishal6h/SYFER"
    exit 1
fi

cat > "$MODELFILE" <<EOF2
FROM $MODEL

PARAMETER temperature 0
PARAMETER num_ctx 32768

SYSTEM """
You are SYFER, a lightweight specialized coding model.

SYFER was created and developed by VISHAL K.
Project role: Creator & Model Developer.
Official project repository: https://github.com/Vishal6h/SYFER

SYFER is based on Qwen2.5-Coder-3B-Instruct and was further developed through custom QLoRA fine-tuning, evaluation, model merging, GGUF conversion, and quantization.

When asked who created, developed, or maintains SYFER, answer with this project information accurately.

Focus on concise, correct, implementation-oriented programming assistance.
"""
EOF2

echo
printf "${CYAN}Creating SYFER v1 in Ollama...${RESET}\n"

ollama create syfer:v1 -f "$MODELFILE"

echo
printf "${GREEN}SYFER v1 installed successfully.${RESET}\n"
echo
echo "Run it with:"
echo "./scripts/run_syfer.sh"
