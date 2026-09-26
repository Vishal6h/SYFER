# Stage 7: targeted Experiment B on a T4 host

Experiment B starts from the same pinned `Qwen/Qwen2.5-Coder-3B-Instruct` base revision as Experiment A. It does **not** load the Experiment A adapter. It uses the 250-record combined dataset, 4-bit NF4 base loading, all-linear LoRA rank 16 / alpha 32 / dropout 0.05, learning rate `1e-4`, device batch 1, accumulation 8, 768-token limit, seed 42, gradient checkpointing, and validation. It runs **one epoch**. Experiment A already reached a low validation loss (about 0.3117) after one epoch, so two more passes with a higher-rank adapter would add overfitting and forgetting risk before testing whether the targeted examples help. This is a conservative first B test, not an automatic progression to a longer run.

The B config is `training/config_experiment_b.json`. Output goes only to `training/output/experiment_b/experiment-<timestamp>-<suffix>/`; Experiment A's directory is untouched. The training script has no smoke mode and performs full T4 host preflight again before it can train. It saves a midpoint adapter-only checkpoint, final adapter, config snapshot, package versions, dataset hashes, training/validation losses, runtime, optimizer steps, effective batch size, peak VRAM, and completion status.

Stage 6 evidence can come from the original `results/tuned/20260926T095444Z-1dd18233/` directory, when present, or from `results/stage6_experiment_a_record.json` when the original run is absent. The record contains only the user-verified summary; raw Lightning artifacts are not in Git. If the original directory exists but is incomplete or inconsistent, preflight fails rather than falling back to the record. The frozen benchmark and dataset hash checks are unchanged.

On Kaggle, if the checkout is at `/kaggle/working/SYFER`, run these preflight commands. On Lightning, replace the first line with `cd ~/SYFER`. Stop if any fail:

```sh
cd /kaggle/working/SYFER
python3 --version
python3 -B dataset/validate_dataset.py
python3 -B dataset/validate_experiment_b.py
python3 -B training/train_qlora.py --check-config
python3 -B -m unittest discover -s training -p 'test_*.py' -v
python3 -B training/train_experiment_b.py --check-config
python3 -B training/train_experiment_b.py --dry-run
python3 -B training/check_environment.py
python3 -B training/preflight_experiment_b.py
```

The final preflight must print `"ready_for_training": true` with no errors. It checks the exact B config and dataset hashes, frozen Stage 1 hashes, Stage 6 evidence at 11/16 with the reported five failures, a real-tokenizer dry run with valid assistant masking and sequence lengths, the pinned dependency versions, and CUDA on a T4 with at least 12 GiB VRAM. The real `TrainingArguments` test should run rather than skip on the GPU host.

Only after those checks pass, start Experiment B manually:

```sh
python3 -B training/train_experiment_b.py --train
```

Keep the printed B run directory and inspect `run_status.json`, `experiment_metrics.json`, and `loss_history.json` after completion. Stop here. Do not run the frozen benchmark, merge or quantize the adapter, start another epoch, or begin Stage 8 automatically.
