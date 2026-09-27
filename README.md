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

## Installation

Requirements:

- Ollama
- Linux / WSL / supported Ollama platform

Clone the repository:

    git clone https://github.com/Vishal6h/SYFER.git
    cd SYFER

Download:

    SYFER-v1-Q4_K_M.gguf

Place it inside:

    release/

Install:

    ./scripts/install_syfer.sh

Run:

    ./scripts/run_syfer.sh

Or directly:

    ollama run syfer:v1

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
