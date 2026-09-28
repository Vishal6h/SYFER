# SYFER v1

**SYFER** is a lightweight specialized coding model built for practical programming assistance and local inference.

> Improved using Qwen.

## Project Information

| Item | Details |
|---|---|
| Project | SYFER |
| Version | v1.0 |
| Project Author | VISHAL K |
| Role | Creator & Model Developer |
| GitHub | https://github.com/Vishal6h/SYFER |
| Base Model | Qwen/Qwen2.5-Coder-3B-Instruct |
| Base Revision | 89fe5444e8baf5736e70f528f1edcc79e6616ef6 |
| Fine-Tuning | QLoRA |
| Release Format | GGUF Q4_K_M |
| Runtime | Ollama / llama.cpp |
| Context | 32,768 tokens |

## About

SYFER v1 is a fine-tuned derivative of Qwen2.5-Coder-3B-Instruct.

The project focuses on practical coding tasks including:

- Python coding
- Bug fixing
- Test-driven fixing
- Debugging
- Structured coding responses
- Tool-call formatting
- Small repository reasoning
- Local coding-assistant workflows

## Development Pipeline

Qwen2.5-Coder-3B-Instruct

→ custom dataset construction

→ QLoRA fine-tuning

→ development experiments

→ frozen final benchmark

→ Experiment D selected

→ LoRA merge

→ Hugging Face model

→ F16 GGUF

→ Q4_K_M quantization

→ Ollama deployment

No additional training was performed after the final frozen benchmark.

## Final Benchmark

The final SYFER v1 benchmark contains 48 unseen tasks across 8 categories.

| Candidate | Strict | Semantic Diagnostic |
|---|---:|---:|
| Stock base | 0 / 48 | 10 / 48 |
| Experiment B | 7 / 48 | 7 / 48 |
| Experiment D | 7 / 48 | 7 / 48 |

Experiment B and Experiment D tied under all preregistered final selection criteria.

Experiment D was selected through an explicit non-training tie-break decision as the latest finalized training iteration.

The benchmark is project-specific and should not be interpreted as a general coding-model leaderboard.

## Local Deployment

Tested locally with:

- NVIDIA GeForce RTX 3050 Laptop GPU
- 4 GB VRAM
- 16 GB RAM
- Ollama
- GGUF Q4_K_M
- 32,768-token configured context

Observed on the test system:

- Ollama model runtime size: ~3.3 GB
- GPU allocation: ~72%
- CPU allocation: ~28%
- VRAM usage: ~2.36 GB

These values are from one local test system and are not universal performance guarantees.

## Linux / WSL / Android

```bash
git clone https://github.com/Vishal6h/SYFER.git
cd SYFER
./setup.sh
./syfer
```

Requires Python 3.8 or newer. Setup verifies the official SHA-256 checksum and,
if the model is absent, downloads the existing v1.0 release (~1.8 GB) into
`model/SYFER-v1-Q4_K_M.gguf`. A corrupt existing model is preserved and reported.
You can also place the official asset there yourself before setup.

Setup uses a responding local Ollama service when available. Otherwise it finds
or builds llama-server. Building requires Git, CMake and a C++ compiler; install
these with your environment's package manager. CUDA is optional, with CPU build
fallback. Existing llama-server installations are reused. Hardware acceleration
is managed by the backend; NVIDIA hardware is not required.

For native Termux, install prerequisites with `pkg install python git cmake clang`
and use the same commands above. Linux distributions running on Android use their
own package manager. Performance and available context depend on device memory.

## Windows

Use native PowerShell; WSL is not required. Install Git, Python 3.8 or newer
(with the Python launcher or Python on PATH), and Ollama. Start the Ollama app
before setup. Ollama is the simplest Windows runtime; no compiler or CUDA Toolkit
is needed for this route.

```powershell
git clone https://github.com/Vishal6h/SYFER.git
cd SYFER
.\setup.ps1
.\syfer.ps1
```

Setup downloads the same official GGUF only if missing, verifies it with Python
hashlib, and creates `syfer:v1` in the local Ollama service. Allow disk space for
the ~1.8 GB GGUF and the backend's model storage. Python discovery tries `py -3`,
`python`, then `python3`.

If local script execution is blocked, use a process-only policy override:

```powershell
powershell -ExecutionPolicy Bypass -File .\setup.ps1
powershell -ExecutionPolicy Bypass -File .\syfer.ps1
```

These commands do not change system or user execution policy.

For an existing Windows llama.cpp installation, provide `llama-server.exe` and
its required DLLs. Setup does not install Windows build tools:

```powershell
$env:SYFER_LLAMA_SERVER="C:\Tools\llama.cpp\llama-server.exe"
.\setup.ps1 --backend llama
.\syfer.ps1 --backend llama
```

Repository-local `runtime/llama.cpp/build/bin/Release/llama-server.exe` and
`runtime/llama.cpp/build/bin/llama-server.exe` are also discovered, followed by PATH.
Paths containing spaces are supported. Native Windows execution still needs host
validation; the current automated checks run on Linux and validate Windows path
and launcher logic statically.

## Runtime and commands

Both launchers use `scripts/syfer_chat.py`, the same banner, and the same combined
`assets/system-prompt.txt` and `assets/project-facts.txt`. The frontend talks to
Ollama at `127.0.0.1:11434` or starts a quiet llama-server on a free loopback port.
It stops its owned server on exit, EOF or Ctrl+C. Ctrl+C during generation exits
the session. Ollama is an independently managed service and stays running.

Automatic chat selection prefers a responding Ollama with `syfer:v1`, then an
available llama-server. Setup can prepare `syfer:v1` when Ollama responds. To pin
a backend, pass `--backend ollama` or `--backend llama` to setup and launch, or set
`SYFER_BACKEND`. An explicit selection never silently switches backends.
The older `scripts/install_syfer.sh` and `scripts/run_syfer.sh` remain Ollama aliases.

- `/help`: show SYFER commands.
- `/clear`: clear the current conversation, retaining system and project facts.
- `/exit`: exit; aliases are `/quit`, `/bye`, `/q`, `exit`, `quit`, `bye` (case insensitive).
- Ctrl+C or EOF: exit cleanly (Windows console EOF is usually Ctrl+Z then Enter).

SYFER has no built-in persistent memory across sessions. Conversation history is
kept in memory during the session. Responses currently appear after generation
finishes; use `/clear` for long conversations approaching the context limit.

The maximum model context is 32,768 tokens. llama.cpp/mobile defaults to 4,096:

```bash
SYFER_CONTEXT=8192 ./syfer --backend llama
```

```powershell
$env:SYFER_CONTEXT="8192"
.\syfer.ps1 --backend llama
```

Ollama setup retains its 32,768-token configuration; `SYFER_CONTEXT` configures
llama-server. Larger contexts need more memory.

Setup logs compiler/backend output to `logs/setup.log` (replaced each setup run).
Use `./setup.sh --debug` or `.\setup.ps1 -Debug` to display it live. Runtime debug
is `./syfer --debug` or `.\syfer.ps1 --debug`. Normal chat does not write transcripts.
The cyan logo uses ANSI only on compatible terminals, with plain text fallback.

For manual model installation, download `SYFER-v1-Q4_K_M.gguf` from the
[official v1.0 release](https://github.com/Vishal6h/SYFER/releases/tag/v1.0), place
it in `model/`, and rerun setup. Setup always checks `release/checksums.txt` using
Python, without requiring `sha256sum`.

## Limitations

SYFER v1 is an experimental fine-tuned coding model.

It may:

- generate incorrect code
- produce invalid patches
- misunderstand repository context
- fail structured-output contracts
- hallucinate APIs
- make incorrect implementation assumptions

Generated code should be reviewed before important use.

SYFER is not claimed to outperform Qwen generally.

## License and Attribution

SYFER is derived from Qwen/Qwen2.5-Coder-3B-Instruct.

See:

- LICENSE
- NOTICE
- CREDITS.md

Improved using Qwen.

## Project Repository

https://github.com/Vishal6h/SYFER

## Author

**VISHAL K**

Creator & Model Developer
