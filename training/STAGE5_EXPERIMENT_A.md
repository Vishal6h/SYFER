# Stage 5: Experiment A on Lightning T4

Run from the updated `~/SYFER` checkout on the Lightning host. Keep the successful Stage 4 smoke directory at `training/output/smoke-20260926T085611Z-621a49b5/`. The host must have Python 3.12 and the tested package versions in `training/requirements.txt`, including CUDA PyTorch 2.14.0 and torchvision 0.29.0. Do not reinstall the stack just to run these checks.

The planned settings are Qwen/Qwen2.5-Coder-3B-Instruct at revision `89fe5444e8baf5736e70f528f1edcc79e6616ef6`, 4-bit NF4 with double quantization, rank-8 all-linear LoRA (alpha 16, dropout 0.05), one epoch, learning rate `1e-4`, batch size 1, gradient accumulation 8, 768 tokens, seed 42, and validation after the epoch. Transformers 5's `warmup_steps=0.05` preserves the configured 5% warmup ratio. The script checks these exact Experiment A values before `--train` can load a model.

Run each preflight command and stop if any command fails:

```sh
cd ~/SYFER
python3 --version
python3 -B dataset/validate_dataset.py
python3 -B training/train_qlora.py --check-config
python3 -B -m unittest discover -s training -p 'test_*.py' -v
python3 -B training/train_qlora.py --dry-run
python3 -B training/check_environment.py
python3 -B training/preflight_experiment_a.py
```

The final preflight must print `"ready_for_training": true` with no errors. It checks the frozen dataset and benchmark hashes, exact Experiment A settings, dry-run masking and lengths, successful Stage 4 smoke and adapter reload reports, package versions, and CUDA on a Tesla T4 with at least 12 GiB VRAM. The unit tests must not skip the real `TrainingArguments` test on Lightning. The dry run loads only the tokenizer. Check that the smoke adapter weights and reload report are still present on Lightning.

After all checks pass, run **only Experiment A**:

```sh
python3 -B training/train_qlora.py --train
```

`--train` and `--smoke-test` are mutually exclusive. This command creates a unique `training/output/experiment-<timestamp>-<suffix>/` directory. It saves `manifest.json` with package versions, dataset hashes, model revision, effective batch size 8, and expected optimizer steps 17; `config.json` is the exact run snapshot. A midpoint adapter-only checkpoint is saved after optimizer step 9 under `adapter-checkpoints/`, and the final adapter is saved under `adapter/`. No base-model weights or full Trainer checkpoint are saved. `loss_history.json` includes training logs and validation results; `experiment_metrics.json` records total runtime, training and validation loss, peak allocated/reserved GPU memory, actual optimizer steps, effective batch size, and final adapter size. `run_status.json` reads `complete` only after the final adapter and metrics are saved. An interrupted or failed run remains visibly incomplete.

After training, inspect `run_status.json` and `experiment_metrics.json` in the printed run directory. Check adapter reload and one harmless completion with the printed experiment directory:

```sh
python3 -B training/verify_smoke_adapter.py training/output/experiment-<timestamp>-<suffix>
```

The verifier writes `reload_report.json` and updates `experiment_metrics.json` with reload and inference results. Do not run the frozen Stage 1 benchmark until Stage 6. Do not start Experiment B, merge adapters, or quantize.
