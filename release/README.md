# SYFER v1 Release

Expected model:

SYFER-v1-Q4_K_M.gguf

The primary setup places the GGUF in `model/`. The Ollama installer and both launchers use that same location.

Expected layout:

model/
- SYFER-v1-Q4_K_M.gguf

Verify the model with:

    cd model && sha256sum -c ../release/checksums.txt

Install:

    ./scripts/install_syfer.sh

Run:

    ./scripts/run_syfer.sh

Project:

https://github.com/Vishal6h/SYFER
