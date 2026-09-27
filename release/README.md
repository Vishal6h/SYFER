# SYFER v1 Release

Expected model:

SYFER-v1-Q4_K_M.gguf

Place the GGUF inside this directory.

Expected layout:

release/
- README.md
- checksums.txt
- SYFER-v1-Q4_K_M.gguf

Verify the model with:

    sha256sum -c release/checksums.txt

Install:

    ./scripts/install_syfer.sh

Run:

    ./scripts/run_syfer.sh

Project:

https://github.com/Vishal6h/SYFER
