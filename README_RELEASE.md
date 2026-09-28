# SYFER release package

See [README.md](README.md#linux--wsl--android) for Linux, WSL, Android and native
Windows installation. Both platforms use the same Python frontend and setup.

Linux / WSL / Android: `./setup.sh`, then `./syfer`.

Windows PowerShell: `.\setup.ps1`, then `.\syfer.ps1`.
Ollama is recommended on Windows; an existing llama-server.exe is also supported.

The official v1.0 GGUF is downloaded only when absent and verified against
`release/checksums.txt`. Setup requires Python 3.8 or newer. Linux llama.cpp builds
also need Git, CMake and a C++ compiler. No GPU is required. llama.cpp defaults to
4,096 context tokens; Ollama setup retains 32,768. Performance varies by hardware.

Quiet setup logs are in `logs/setup.log`; use `--debug` for details.
