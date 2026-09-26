# Stage 6: frozen benchmark evaluation of Experiment A

Run from the updated `~/SYFER` checkout on the Lightning T4 host. The completed Experiment A output must be present at `training/output/experiment-20260926T093433Z-6630ef2a/`, including `adapter/adapter_model.safetensors`, `adapter/adapter_config.json`, `loss_history.json`, `experiment_metrics.json`, `manifest.json`, `config.json`, and `run_status.json` marked complete.

First check the exact artifact and frozen input hashes without loading a model:

```sh
cd ~/SYFER
python3 -B benchmark/run_tuned.py --check
```

If that succeeds, run all 16 tasks once:

```sh
python3 -B benchmark/run_tuned.py
```

The runner loads the pinned Qwen/Qwen2.5-Coder-3B-Instruct base at revision `89fe5444e8baf5736e70f528f1edcc79e6616ef6` in 4-bit NF4 for inference and attaches the saved LoRA adapter. It does not write a merged or quantized model. It uses the exact strings in the frozen `benchmark/tasks.json`, applies the model's chat template, and generates greedily with at most 512 new tokens and seed 42. It imports the unchanged `run_baseline.validate` function for every task, including exact mock tool-call matching. It performs no selective retries or format relaxation.

Each run gets a unique `results/tuned/<timestamp>-<suffix>/` directory with all 16 raw responses, `run_config.json`, `progress.json`, `summary.json`, `comparison.md`, and a completion status. The comparison lists category scores, improved and regressed tasks, unchanged passes and failures, total task runtime, absolute task gain, percentage-point gain, and relative gain against the verified stock 6/16 run. Model loading time is recorded separately.

The stock score came from Ollama's `qwen2.5-coder:3b`; the tuned score uses the pinned Hugging Face base plus LoRA. The task texts, generation cap, deterministic decoding, and validators are aligned, but serving and chat-template behavior differ. This is a comparison of the two usable model setups, not an isolated estimate of the adapter's causal effect. Do not train, tune against these tasks, or begin quantization in Stage 6.
