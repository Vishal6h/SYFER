# Experiment D preparation

Experiment D starts afresh from
`Qwen/Qwen2.5-Coder-3B-Instruct` at pinned revision
`89fe5444e8baf5736e70f528f1edcc79e6616ef6`. It does not continue from
the B or C adapter. The D1 dataset uses the same output contracts as the new,
separately frozen D-development benchmark. Historical C-development scores
remain unchanged and are a different task series.

The pinned configuration uses 4-bit NF4 loading with double quantization,
all-linear LoRA rank 16, alpha 32, dropout 0.05, learning rate 7.5e-5,
one epoch, batch size 1, gradient accumulation 8 (effective batch size 8),
maximum length 768, gradient checkpointing, seed 42 and validation each epoch.
With 160 training examples, the planned run has about 20 optimizer steps.
One epoch and the lower learning rate limit overfitting on this small authored
dataset while preserving basic coding rehearsal. A CUDA GPU with at least
12 GiB VRAM is required by the preflight; a 16 GiB T4 is the intended host.
No local 4 GiB GPU training is planned.

The D-only entry point has explicit `--check-config`, `--dry-run` and `--train`
modes; it does not train by default. It reuses the existing QLoRA trainer's
pinned base and chat-template formatting. The tokenizer-only dry run checks
every example's target masking and sequence length without loading the base
weights. Host preflight checks the completed dry-run report, installed
packages, CUDA VRAM and installed Transformers TrainingArguments behavior.
Full training creates a unique directory under `training/output/experiment_d/`,
saves adapter-only checkpoints/final adapter, losses, run manifest, hashes,
runtime, peak VRAM and status. An interrupted/failed run is not marked
complete. The scorer requires a completed run directory before D evaluation.

Local model-free preparation:

```sh
python3 -B benchmark/experiment_d_dev/validate_d_dev.py
python3 -B benchmark/experiment_d_dev/test_d_dev.py
python3 -B dataset/validate_experiment_d.py
python3 -B training/test_experiment_d_setup.py
python3 -B training/preflight_experiment_d.py --local
python3 -B training/train_experiment_d.py --check-config
python3 -B benchmark/evaluate_experiment_d_dev.py --model stock --check
```

On the Kaggle GPU clone, after the committed files are pulled and a suitable
CUDA GPU is available, run these commands from the SYFER repository root:

```sh
git pull --ff-only
python3 -B dataset/validate_experiment_d.py
python3 -B benchmark/experiment_d_dev/validate_d_dev.py
python3 -B training/train_experiment_d.py --check-config
python3 -B training/train_experiment_d.py --dry-run
python3 -B training/preflight_experiment_d.py
python3 -B training/train_experiment_d.py --train
```

The final command is the **only** command above that trains. Do not run it
until dry run and host preflight pass. The GPU evaluation is a later, separate
step; `benchmark/evaluate_experiment_d_dev.py --check` never loads or queries
a model. For a completed D run, pass `--model experiment_d
--experiment-d-run training/output/experiment_d/<experiment-run> --check`
before any evaluation. B/C checks require their actual adapter directories on
the same host; C additionally takes `--experiment-c-run`.
