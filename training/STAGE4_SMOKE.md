# Stage 4: one-step cloud smoke test

This runbook stops after one optimizer update, adapter reload, and one harmless completion. It never invokes `--train` or Experiment A. It needs a connected NVIDIA cloud machine with Python 3.12 and preferably at least 16 GiB VRAM. The current WSL machine has only 4 GiB VRAM and must not be used for this job.

The Stage 1 benchmark and Stage 2 JSONL splits are frozen. Run `python3 -B dataset/validate_dataset.py` before the smoke job and verify their recorded hashes. All commands below assume the SYFER checkout is present on the cloud machine and are run from its root.

```sh
python3.12 -m venv training/.venv
training/.venv/bin/python -m pip install --no-cache-dir -r training/requirements.txt
training/.venv/bin/python -B training/check_environment.py
training/.venv/bin/python -B training/train_qlora.py --check-config
training/.venv/bin/python -B training/train_qlora.py --dry-run --download-tokenizer
training/.venv/bin/python -B training/train_qlora.py --smoke-test
```

Check `environment_report.json` for CUDA availability, GPU name, VRAM, and package versions before the tokenizer download. The dry run downloads only the pinned tokenizer into `training/cache/`, applies the real chat template to all 170 examples, checks assistant-only labels, and verifies the 768-token limit. If it exits nonzero, stop and inspect `dry_run_report.json`; the smoke command refuses to run without a passed real-tokenizer report for the current dataset hashes.

The smoke command guards against GPUs below 12 GiB, loads the pinned base in 4-bit NF4, attaches rank-8 all-linear LoRA, uses two training and two validation examples, and runs exactly one optimizer step with accumulation 1. It records initial and final validation loss, train loss, runtime, peak allocated/reserved GPU memory, adapter size, and the actual optimizer step count under a new `training/output/smoke-<timestamp>-<suffix>/`. It writes an adapter only; there is no full-model checkpoint.

After a successful smoke command, run the reload checker against the exact directory printed by the command:

```sh
training/.venv/bin/python -B training/verify_smoke_adapter.py training/output/smoke-<timestamp>-<suffix>
```

The checker loads the pinned base and saved adapter, generates one short answer to a harmless Python question, and writes `reload_report.json`. It also updates `smoke_metrics.json` with reload and inference results. Stop after this check. A CUDA out-of-memory error is a failed smoke test; record the error and peak memory, then review a shorter **smoke-only** sequence limit or a larger GPU. Do not change Experiment A's config silently or retry repeatedly.

The current local environment cannot execute the cloud steps: no cloud GPU host or connected compute service is configured in this workspace. `stage4_status.json` records this state without claiming training occurred.
