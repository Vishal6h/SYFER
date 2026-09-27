# SYFER v1 Model Card

## Model

- Name: SYFER
- Version: v1.0
- Author: VISHAL K
- Role: Creator & Model Developer
- Base: Qwen/Qwen2.5-Coder-3B-Instruct
- Base revision: 89fe5444e8baf5736e70f528f1edcc79e6616ef6
- Fine-tuning: QLoRA
- Quantization: Q4_K_M
- Runtime: Ollama / llama.cpp
- Configured context: 32,768 tokens

## Intended Uses

SYFER is intended for:

- programming practice
- small coding tasks
- debugging assistance
- test-driven fixing
- local coding experimentation
- coding-agent experimentation

## Training

SYFER was fine-tuned using QLoRA from the pinned Qwen base.

The final release uses Experiment D.

No model training occurred after the final frozen benchmark.

## Evaluation

Final benchmark:

- 48 tasks
- 8 categories
- 6 tasks per category

Strict:

- Stock: 0/48
- Experiment B: 7/48
- Experiment D: 7/48

Semantic diagnostic:

- Stock: 10/48
- Experiment B: 7/48
- Experiment D: 7/48

B and D tied under the preregistered selection policy.

Experiment D was selected through a documented non-training tie-break.

## Release

Merged model:

HF FP16

Converted to:

F16 GGUF

Quantized to:

Q4_K_M GGUF

Approximate GGUF size:

1.8 GB

## Limitations

The final benchmark showed notable weaknesses in:

- code explanation
- patch generation
- multi-step debugging
- tool-call formatting
- repository reasoning

SYFER should therefore be treated as experimental.

## Attribution

SYFER is a modified derivative of Qwen2.5-Coder-3B-Instruct.

Improved using Qwen.

See LICENSE, NOTICE, and CREDITS.md.
