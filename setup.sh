#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODEL="$ROOT/model/SYFER-v1-Q4_K_M.gguf"
SHA256='667dc80f693f8387829c3554ee1708f650035a9b3f2d69282fcf6abf3e08f9bf'
MODEL_URL="${SYFER_MODEL_URL:-https://github.com/Vishal6h/SYFER/releases/download/v1.0/SYFER-v1-Q4_K_M.gguf}"

command -v sha256sum >/dev/null || { echo 'Missing sha256sum.' >&2; exit 1; }
mkdir -p "$ROOT/model" "$ROOT/runtime"

if [[ -f "$MODEL" ]] && printf '%s  %s\n' "$SHA256" "$MODEL" | sha256sum -c --status; then
  echo 'SYFER model verified.'
else
  command -v curl >/dev/null || { echo 'Install curl and rerun setup.' >&2; exit 1; }
  echo 'Downloading SYFER model (~1.8 GB)...'
  curl -fL --retry 3 --continue-at - -o "$MODEL.part" "$MODEL_URL"
  printf '%s  %s\n' "$SHA256" "$MODEL.part" | sha256sum -c --status || { echo 'Model checksum failed.' >&2; exit 1; }
  mv "$MODEL.part" "$MODEL"
  echo 'SYFER model verified.'
fi

if [[ -n "${SYFER_LLAMA_CLI:-}" ]]; then
  [[ -x "$SYFER_LLAMA_CLI" ]] || { echo 'SYFER_LLAMA_CLI is not executable.' >&2; exit 1; }
  printf '%s\n' "$SYFER_LLAMA_CLI" > "$ROOT/config/llama-cli-path"
elif command -v llama-cli >/dev/null 2>&1; then
  command -v llama-cli > "$ROOT/config/llama-cli-path"
else
  for tool in git cmake c++; do
    command -v "$tool" >/dev/null || { echo "Install $tool and rerun setup." >&2; exit 1; }
  done
  if [[ ! -d "$ROOT/runtime/llama.cpp/.git" ]]; then
    git clone --depth 1 https://github.com/ggml-org/llama.cpp.git "$ROOT/runtime/llama.cpp"
  fi
  CUDA=OFF
  if command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi -L >/dev/null 2>&1 && command -v nvcc >/dev/null 2>&1; then
    CUDA=ON
  fi
  if ! cmake -S "$ROOT/runtime/llama.cpp" -B "$ROOT/runtime/llama.cpp/build" -DCMAKE_BUILD_TYPE=Release -DGGML_CUDA="$CUDA"; then
    if [[ "$CUDA" != ON ]]; then exit 1; fi
    echo 'CUDA build unavailable; falling back to CPU.' >&2
    CUDA=OFF
    cmake -S "$ROOT/runtime/llama.cpp" -B "$ROOT/runtime/llama.cpp/build" -DCMAKE_BUILD_TYPE=Release -DGGML_CUDA=OFF
  fi
  if ! cmake --build "$ROOT/runtime/llama.cpp/build" --config Release --target llama-cli -j 2; then
    if [[ "$CUDA" != ON ]]; then exit 1; fi
    echo 'CUDA build failed; falling back to CPU.' >&2
    cmake -S "$ROOT/runtime/llama.cpp" -B "$ROOT/runtime/llama.cpp/build" -DCMAKE_BUILD_TYPE=Release -DGGML_CUDA=OFF
    cmake --build "$ROOT/runtime/llama.cpp/build" --config Release --target llama-cli -j 2
  fi
  printf '%s\n' "$ROOT/runtime/llama.cpp/build/bin/llama-cli" > "$ROOT/config/llama-cli-path"
fi

echo 'Setup complete. Run ./syfer'
