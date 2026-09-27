# SYFER release package

Linux / WSL:

```bash
git clone https://github.com/Vishal6h/SYFER.git
cd SYFER
./setup.sh
./syfer
```

This is a standalone release skeleton. Once these files are added to the repository root, that clone flow will work. Setup downloads the v1.0 Q4 model, verifies its SHA-256 checksum, and finds or builds `llama-cli`. The build fallback is CPU only. To use a particular runtime, set `SYFER_LLAMA_CLI=/absolute/path/to/llama-cli` before setup. The launcher passes additional arguments through to `llama-cli`.

The model and built runtime stay in `model/` and `runtime/` and are excluded from Git. Setup needs `curl` and `sha256sum`; building llama.cpp also needs `git`, `cmake`, and a C++ compiler. Allow roughly 2 GB of free disk space for the model plus build space. The launcher starts with a 4K context to fit more machines; adjust with `./syfer -c 8192` when memory allows.
