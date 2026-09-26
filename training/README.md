# SYFER QLoRA setup and Experiment A

Stage 4's one-step smoke test, adapter reload, and inference succeeded on the Lightning Tesla T4 according to the user's report. The smoke artifacts remain on that host. Experiment A has **not** run in this workspace. Training uses the exact upstream model [`Qwen/Qwen2.5-Coder-3B-Instruct`](https://huggingface.co/Qwen/Qwen2.5-Coder-3B-Instruct), pinned to [commit `89fe5444e8baf5736e70f528f1edcc79e6616ef6`](https://huggingface.co/Qwen/Qwen2.5-Coder-3B-Instruct/commit/89fe5444e8baf5736e70f528f1edcc79e6616ef6). The Stage 1 benchmark stays frozen; the Stage 2 validation split is used for loss monitoring, never as training text.

## Local environment and feasibility

The inspected WSL session has Python 3.14.4 by default and Python 3.12.14 available, an RTX 3050 Laptop GPU with 4,096 MiB VRAM, and about 7.6 GiB RAM exposed inside WSL (the laptop has 16 GB physical RAM). The installed CUDA driver reports compute capability 8.6, but PyTorch/CUDA availability cannot be tested because PyTorch is absent. All checked training packages are absent; see `environment_report.json`.

**Do not train the 3B model on this 4 GB GPU.** The upstream model has [3.09 billion parameters](https://huggingface.co/Qwen/Qwen2.5-Coder-3B-Instruct). Raw 4-bit weights alone are about 1.44 GiB; quantization metadata, nonquantized components, LoRA weights and optimizer state, activations, and CUDA workspace raise the working set. A planning estimate for batch 1 and 768 tokens is roughly **6–10 GiB VRAM**, with variation by software and examples. The 12 GiB guard in the script is a minimum safety margin, not a guarantee. Use a **16 GB GPU or larger** for Experiment A; 24 GB provides more room for Experiment B. Aim for 24–32 GB host RAM. These numbers are engineering estimates, not measurements on this machine. [Hugging Face's quantization guide](https://huggingface.co/docs/transformers/main/quantization/bitsandbytes) explains NF4, double quantization, and why quantized training updates extra parameters only.

Keep local Ollama inference as the deployment target after a later stage evaluates a trained adapter. No conversion or deployment is part of Stage 3.

## Files and commands

`config.json` is Experiment A. `train_qlora.py` validates the config and data with the standard library, formats all three-message records using the Qwen tokenizer chat template, masks system/user tokens from the loss, and trains LoRA adapters on a 4-bit NF4 base only when `--train` or `--smoke-test` is explicitly supplied. The `--train` path checks the exact Experiment A settings before loading model weights. It never saves base weights. Each training invocation reserves a new timestamped directory under `training/output/`; `save_strategy="no"` prevents full Trainer checkpoints. Experiment A saves a midpoint adapter-only checkpoint, a final adapter, loss history, metrics, a config snapshot, and an in-progress/complete/failed status. An interrupted run is never marked complete. `check_environment.py` records hardware and installed package versions without installing anything.

From the SYFER root:

```sh
python3 -B dataset/validate_dataset.py
python3 -B training/check_environment.py
python3 -B training/train_qlora.py --check-config
python3 -B training/train_qlora.py --dry-run
```

The dry run reads both JSONL files, checks config and output paths, downloads the exact pinned tokenizer into `training/cache/` if needed, applies its chat template to all records, checks the 768-token limit and assistant loss mask, and loads no model weights. Use `--dry-run --offline` to require an already populated project cache. If `transformers` or the tokenizer is unavailable, it writes `dry_run_report.json`, exits with code 2, and names the missing step. `--check-config` succeeds without ML packages.

The tested Lightning stack uses Python 3.12.11, CUDA PyTorch 2.14.0, torchvision 0.29.0, Transformers 5.17.0, PEFT 0.21.0, Accelerate 1.15.0, and bitsandbytes 0.50.2. `requirements.txt` pins this stack. Transformers 5 chat templates return a `BatchEncoding`; the formatter extracts and validates its `input_ids`. Transformers 5 also uses `warmup_steps=0.05` for a 5% warmup ratio. The PyTorch/torchvision pins are paired as tested on Lightning. Keep the installed CUDA-compatible build; do not replace it with a CPU build.

For the completed Stage 4 smoke test, the explicit command was:

```sh
python3 -B training/train_qlora.py --smoke-test
```

The script rejects GPUs below the configured 12 GiB minimum before loading the tokenizer or full model. Full training requires the separate `--train` flag. Follow [STAGE5_EXPERIMENT_A.md](STAGE5_EXPERIMENT_A.md) for the exact preflight and run command. This local checkout cannot run Experiment A on its 4 GB GPU.

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
