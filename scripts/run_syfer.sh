#!/usr/bin/env bash
set -e

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BANNER="$ROOT/assets/syfer-banner.txt"

CYAN='\033[0;36m'
WHITE='\033[0;37m'
RESET='\033[0m'

clear

# Print only the ASCII SYFER logo in cyan
printf "${CYAN}"
head -n 6 "$BANNER"
printf "${RESET}"

# Print the rest in clean white/default text
printf "${WHITE}"
tail -n +7 "$BANNER"
printf "${RESET}"

echo
printf "${CYAN}Starting SYFER v1...${RESET}\n"
echo

exec ollama run syfer:v1
