# Stage 3: QLoRA setup and experiment plan

**No training has been run.** This directory prepares a future cloud experiment for the exact upstream model [`Qwen/Qwen2.5-Coder-3B-Instruct`](https://huggingface.co/Qwen/Qwen2.5-Coder-3B-Instruct), pinned to [commit `89fe5444e8baf5736e70f528f1edcc79e6616ef6`](https://huggingface.co/Qwen/Qwen2.5-Coder-3B-Instruct/commit/89fe5444e8baf5736e70f528f1edcc79e6616ef6). The stock local Ollama model remains an inference and baseline target. The Stage 1 benchmark stays frozen; the Stage 2 validation split is used for loss monitoring, never as training text.

## Local environment and feasibility

The inspected WSL session has Python 3.14.4 by default and Python 3.12.14 available, an RTX 3050 Laptop GPU with 4,096 MiB VRAM, and about 7.6 GiB RAM exposed inside WSL (the laptop has 16 GB physical RAM). The installed CUDA driver reports compute capability 8.6, but PyTorch/CUDA availability cannot be tested because PyTorch is absent. All checked training packages are absent; see `environment_report.json`.

**Do not train the 3B model on this 4 GB GPU.** The upstream model has [3.09 billion parameters](https://huggingface.co/Qwen/Qwen2.5-Coder-3B-Instruct). Raw 4-bit weights alone are about 1.44 GiB; quantization metadata, nonquantized components, LoRA weights and optimizer state, activations, and CUDA workspace raise the working set. A planning estimate for batch 1 and 768 tokens is roughly **6–10 GiB VRAM**, with variation by software and examples. The 12 GiB guard in the script is a minimum safety margin, not a guarantee. Use a **16 GB GPU or larger** for Experiment A; 24 GB provides more room for Experiment B. Aim for 24–32 GB host RAM. These numbers are engineering estimates, not measurements on this machine. [Hugging Face's quantization guide](https://huggingface.co/docs/transformers/main/quantization/bitsandbytes) explains NF4, double quantization, and why quantized training updates extra parameters only.

Keep local Ollama inference as the deployment target after a later stage evaluates a trained adapter. No conversion or deployment is part of Stage 3.

## Files and commands

`config.json` is Experiment A. `train_qlora.py` validates the config and data with the standard library, formats all three-message records using the Qwen tokenizer chat template, masks system/user tokens from the loss, and trains LoRA adapters on a 4-bit NF4 base only when `--train` or `--smoke-test` is explicitly supplied. It never saves base weights. Each training invocation reserves a new timestamped directory under `training/output/`; adapter weights and training/validation loss go there. `save_strategy="no"` prevents full Trainer checkpoints. `check_environment.py` records hardware and installed package versions without installing anything.

From the SYFER root:

```sh
python3 -B dataset/validate_dataset.py
python3 -B training/check_environment.py
python3 -B training/train_qlora.py --check-config
python3 -B training/train_qlora.py --dry-run
```

The dry run reads both JSONL files, checks config and output paths, attempts to load the exact upstream tokenizer **from the local cache only**, applies its chat template to all records, checks the 768-token limit and assistant loss mask, and loads no model weights. If `transformers` or the tokenizer is unavailable, it writes `dry_run_report.json`, exits with code 2, and names the missing step. It does not download anything. The currently available environment is expected to stop at tokenizer loading. Re-run on the future cloud environment after installing dependencies and caching the tokenizer. `--check-config` succeeds without ML packages.

For a future cloud machine in Stage 4, use Python 3.12 and install the pinned `requirements.txt` with the appropriate CUDA PyTorch build. The pins were selected from published releases but have **not** been installed or integration-tested here. Verify that `torch.cuda.is_available()` and BF16 support match the cloud GPU. A one-step smoke test would then be:

```sh
python3 -B training/train_qlora.py --smoke-test
```

The script rejects GPUs below the configured 12 GiB minimum before loading the tokenizer or full model. Full training requires the separate `--train` flag. Neither command was run in Stage 3.

## Experiment plan

| Setting | Experiment A | Experiment B, only if A underfits |
| --- | ---: | ---: |
| Base loading | 4-bit NF4, double quantization | Same |
| LoRA target | All linear layers | Same |
| LoRA rank / alpha / dropout | 8 / 16 / 0.05 | 16 / 32 / 0.05 |
| Epochs | 1 | 2 |
| Learning rate | 1e-4 | 1e-4 |
| Sequence limit | 768 tokens | 768 tokens |
| Device batch / accumulation | 1 / 8 | 1 / 8 |
| Precision | BF16 if supported; otherwise FP16 | Same |
| Evaluation | Validation loss after each epoch | Same |

Rank 8 and alpha 16 keep adapter size modest while touching all linear layers, a common [QLoRA target choice](https://huggingface.co/docs/peft/en/package_reference/lora). Dropout 0.05 and one epoch limit memorization risk with only 130 training examples. Batch 1 and gradient accumulation 8 provide an effective batch of 8 while limiting activation memory. Gradient checkpointing trades computation for memory. NF4 and double quantization reduce base-weight storage; the base is frozen. The 768-token limit is deliberately below the model's full context and must be checked by the dry run before training. A learning rate of 1e-4 is a cautious LoRA starting point; [TRL's PEFT guidance](https://huggingface.co/docs/trl/peft_integration) shows the usual higher LoRA rates and target choices.

For A, compare training and validation loss and inspect the 40 held-out Stage 2 records. Run B only if both losses remain high or A clearly underfits; if training loss falls while validation loss rises, improve the data instead of increasing capacity. The frozen Stage 1 benchmark should be used only after a candidate adapter is selected in a later stage. Do not use its answers for training or hyperparameter selection.

The `datasets` and `trl` packages are inspected by the environment checker but are not required by this script: JSONL loading uses Python's standard library, and supervised fine-tuning uses Transformers `Trainer` with a small explicit assistant-loss collator. This keeps the data path inspectable and avoids extra dependencies.
