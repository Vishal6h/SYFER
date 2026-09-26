# Experiment C preparation (no training run yet)

Experiment C starts from the original pinned
`Qwen/Qwen2.5-Coder-3B-Instruct` revision
`89fe5444e8baf5736e70f528f1edcc79e6616ef6`. It does not load the
Experiment A or B adapter. The older 32-task holdout has been inspected and
is a development result for this decision, not a final untouched test for C.
The new 32-task C development benchmark was frozen before this dataset was
created. Do not evaluate it until C preparation is complete.

`config_experiment_c.json` pins 4-bit NF4 with double quantization, all-linear
LoRA rank 16 / alpha 32 / dropout 0.05, batch size 1, accumulation 8,
sequence length 768, gradient checkpointing, one epoch, seed 42, and learning
rate `5e-5`. Rank and alpha retain the B adapter capacity. One epoch and the
lower learning rate reduce the chance of overfitting 88 training examples or
losing basic coding ability. The dataset includes 40 rehearsal records across
simple coding, bug fixing, explanation, multi-step debugging, and TDD.
`train_qlora.py` provides the same chat-template masking, initial adapter
checkpoint, final adapter, metrics, manifest, unique run directory, and
interruption status used by previous experiments. C output is isolated in
`training/output/experiment_c/`.

Local static checks, with no tokenizer, model, or GPU:

```sh
python3 -B dataset/validate_experiment_c.py
python3 -B benchmark/experiment_c_dev/validate_c_dev.py
python3 -B -m unittest discover -s benchmark/experiment_c_dev -p 'test_*.py'
python3 -B -m unittest discover -s training -p 'test_experiment_c_setup.py'
python3 -B training/preflight_experiment_c.py --local
python3 -B training/train_experiment_c.py --check-config
python3 -B benchmark/evaluate_experiment_c_dev.py --model stock --check
```

On Kaggle, after pulling these files and confirming a CUDA GPU with at least
12 GiB and the packages in `training/requirements.txt`, run in this order:

```sh
git pull --ff-only
python3 -B dataset/validate_experiment_c.py
python3 -B benchmark/experiment_c_dev/validate_c_dev.py
python3 -B training/train_experiment_c.py --check-config
python3 -B training/train_experiment_c.py --dry-run
python3 -B training/preflight_experiment_c.py
python3 -B training/train_experiment_c.py --train
```

The real-tokenizer `--dry-run` downloads or loads only the pinned tokenizer,
checks chat formatting, assistant-label masking, and sequence lengths, and
saves `training/dry_run_experiment_c.json`. The host preflight then checks
the dry-run report, input hashes, installed packages, and CUDA VRAM. The final
`--train` is the **only** command above that loads the full base model and
performs GPU updates. It is prepared for a later authorized run and has not
been executed in this preparation stage.

After training, evaluate stock, B, and C on the C development tasks using
`benchmark/evaluate_experiment_c_dev.py`, with `--check` first. For C, pass
`--experiment-c-run training/output/experiment_c/<completed-run-directory>`.
The runner saves separate results under `results/experiment_c_dev/`. These
tasks are for diagnosis; their results cannot restore the untouched status of
the earlier 32-task holdout.
