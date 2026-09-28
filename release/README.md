# SYFER v1 Release

Canonical model: `model/SYFER-v1-Q4_K_M.gguf` (relative to the repository).
Download source: https://github.com/Vishal6h/SYFER/releases/tag/v1.0

Run `./setup.sh` on Linux / WSL / Android, or `.\setup.ps1` on Windows.
Both verify SHA-256 using Python and `release/checksums.txt`. Missing models are
downloaded from the official release; existing valid models are reused.

Launch with `./syfer` or `.\syfer.ps1`. To explicitly prepare and use Ollama,
pass `--backend ollama` to setup and launch. See [installation](../README.md).
