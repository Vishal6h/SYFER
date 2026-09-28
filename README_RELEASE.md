# SYFER release package

Linux / WSL:

```bash
git clone https://github.com/Vishal6h/SYFER.git
cd SYFER
./setup.sh
./syfer
```

Setup downloads the v1.0 Q4 model, verifies its SHA-256 checksum, and finds or builds `llama-server`. The build fallback is CPU only. To use an existing runtime, set `SYFER_LLAMA_SERVER` to the executable path before setup and launch. The server listens on a temporary localhost port and stops when SYFER exits. Use `./syfer --debug` to see backend startup output.

The model and built runtime stay in `model/` and `runtime/` and are excluded from Git. Setup needs Python 3, `curl`, and `sha256sum`; building llama.cpp also needs `git`, `cmake`, and a C++ compiler. Allow roughly 2 GB of free disk space for the model plus build space. The launcher uses a 4K context to fit more machines.
