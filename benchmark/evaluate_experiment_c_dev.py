#!/usr/bin/env python3
"""Evaluate stock, B, or C on the frozen C development tasks when requested."""

import argparse
import datetime as dt
import hashlib
import importlib.metadata
import json
import time
import uuid
from collections import Counter
from pathlib import Path

import run_baseline as baseline
import run_tuned  # Reuse Experiment A's pinned chat-template generation path.
from experiment_c_dev import validate_c_dev as development


ROOT = Path(__file__).resolve().parents[1]
TASKS = ROOT / "benchmark/experiment_c_dev/tasks.json"
VALIDATOR = ROOT / "benchmark/experiment_c_dev/validate_c_dev.py"
OUTPUT_ROOT = ROOT / "results/experiment_c_dev"
MODEL_ID = "Qwen/Qwen2.5-Coder-3B-Instruct"
REVISION = "89fe5444e8baf5736e70f528f1edcc79e6616ef6"
OPTIONS = {"temperature": 0, "num_predict": 512, "seed": 42}
TASKS_SHA256 = "d428a4186944358b420c754a70e70027e6bc0251d8320ad058db4e3609eb04b4"
VALIDATOR_SHA256 = "39fa89524df13d27005d607f57ac0504c20e0a6fbbf0acc2f6c65b0ea230801f"
SCORING_SHA256 = "f36aec792f6e3c0cb7d81765908d7bc5f8cfd279799cadb36628a9dbf3e4bec1"
B_ADAPTER = ROOT / "training/output/experiment_b/experiment-20260926T111408Z-4838f847/adapter"
C_OUTPUT = ROOT / "training/output/experiment_c"


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def select_adapter(model_name, c_run):
    if model_name == "stock":
        require(c_run is None, "--experiment-c-run is only for Experiment C")
        return None
    if model_name == "experiment_b":
        require(c_run is None, "--experiment-c-run is only for Experiment C")
        return B_ADAPTER
    require(c_run is not None, "--experiment-c-run is required for Experiment C")
    run = (ROOT / c_run).resolve()
    require(run.parent == C_OUTPUT.resolve() and run.name.startswith("experiment-"),
            "C run must be an experiment directory under training/output/experiment_c")
    status = json.loads((run / "run_status.json").read_text(encoding="utf-8"))
    manifest = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
    config = json.loads((run / "config.json").read_text(encoding="utf-8"))
    pinned = json.loads((ROOT / "training/config_experiment_c.json").read_text(encoding="utf-8"))
    require(status.get("status") == "complete" and manifest.get("experiment") == "C" and
            manifest.get("mode") == "train" and config == pinned and
            manifest.get("model_id") == MODEL_ID and manifest.get("model_revision") == REVISION and
            manifest.get("train_sha256") == pinned["train_sha256"] and
            manifest.get("validation_sha256") == pinned["validation_sha256"],
            "C run is incomplete or differs from the pinned experiment")
    return run / "adapter"


def check(model_name, c_run=None):
    """Check hashes, validator, settings and the selected adapter, without a model."""
    require(model_name in ("stock", "experiment_b", "experiment_c"), "unknown model")
    require(MODEL_ID == run_tuned.MODEL_ID and REVISION == run_tuned.REVISION,
            "pinned base differs from Experiment A")
    require(OPTIONS == baseline.OPTIONS == {"temperature": 0, "num_predict": 512, "seed": 42},
            "generation settings changed")
    require(sha256(TASKS) == TASKS_SHA256 and sha256(VALIDATOR) == VALIDATOR_SHA256,
            "C development benchmark changed after freeze")
    require(sha256(ROOT / "benchmark/run_baseline.py") == run_tuned.BASELINE_RUNNER_SHA256,
            "frozen Python/diff scoring logic changed")
    require(sha256(ROOT / "benchmark/final_holdout/validate_holdout.py") == SCORING_SHA256,
            "frozen shared holdout scoring logic changed")
    require(OUTPUT_ROOT == ROOT / "results/experiment_c_dev" and
            OUTPUT_ROOT.resolve() != (ROOT / "results/final_holdout").resolve(),
            "development output path is not isolated")
    audit = development.validate()
    require(audit["error_count"] == 0 and audit["task_count"] == 32 and
            audit["validated_references"] == 32, "C development validation failed")
    adapter = select_adapter(model_name, c_run)
    weights = None
    if adapter:
        weights = adapter / "adapter_model.safetensors"
        metadata = adapter / "adapter_config.json"
        require(weights.is_file() and weights.stat().st_size > 0 and metadata.is_file(),
                f"{model_name} adapter files missing")
        config = json.loads(metadata.read_text(encoding="utf-8"))
        require(config.get("peft_type") == "LORA" and config.get("r") == 16 and
                config.get("lora_alpha") == 32 and config.get("lora_dropout") == 0.05 and
                config.get("base_model_name_or_path") in (None, MODEL_ID),
                f"{model_name} adapter metadata differs from the planned LoRA settings")
    tasks = json.loads(TASKS.read_text(encoding="utf-8"))
    return tasks, adapter, weights


def run(model_name, tasks, adapter, weights):
    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig, set_seed

    require(torch.cuda.is_available(), "CUDA is required for 4-bit C development evaluation")
    dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
    cache = ROOT / "training/cache"
    load_started = time.monotonic()
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, revision=REVISION, cache_dir=cache,
                                              trust_remote_code=False)
    require(tokenizer.chat_template, "pinned tokenizer has no chat template")
    quant = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                              bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=dtype)
    base = AutoModelForCausalLM.from_pretrained(MODEL_ID, revision=REVISION, cache_dir=cache,
                                                quantization_config=quant, dtype=dtype,
                                                device_map={"": torch.cuda.current_device()},
                                                trust_remote_code=False)
    model = PeftModel.from_pretrained(base, adapter, is_trainable=False) if adapter else base
    model.eval()
    load_seconds = round(time.monotonic() - load_started, 3)
    output_root = OUTPUT_ROOT / model_name
    output_root.mkdir(parents=True, exist_ok=True)
    run_id = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    run_dir = output_root / run_id
    run_dir.mkdir(exist_ok=False)
    baseline.save_json(run_dir / "tasks_snapshot.json", tasks)
    baseline.save_json(run_dir / "run_config.json", {
        "model": model_name, "base_model_id": MODEL_ID, "base_revision": REVISION,
        "adapter": str(adapter.relative_to(ROOT)) if adapter else None,
        "adapter_weights_sha256": sha256(weights) if weights else None,
        "adapter_config_sha256": sha256(adapter / "adapter_config.json") if adapter else None,
        "c_dev_tasks_sha256": TASKS_SHA256, "c_dev_validator_sha256": VALIDATOR_SHA256,
        "runner_sha256": sha256(Path(__file__)), "options": OPTIONS,
        "generation": "greedy pinned Hugging Face chat template; max_new_tokens=512",
        "load_runtime_seconds": load_seconds,
        "packages": {name: importlib.metadata.version(name) for name in
                     ("torch", "transformers", "peft", "bitsandbytes", "accelerate")},
        "started_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
    })
    baseline.save_json(run_dir / "run_status.json", {"status": "in_progress", "completed_tasks": 0})
    results = []
    started = time.monotonic()
    try:
        for task in tasks:
            task_started = time.monotonic()
            raw = ""
            try:
                raw = run_tuned.generate_raw(model, tokenizer, task["prompt"], torch, set_seed)
                passed, detail = development.core.validate_response(task, raw)
                error = None
            except Exception as exc:
                passed, detail, error = False, str(exc), type(exc).__name__
            raw_path = run_dir / (task["id"] + ".txt")
            raw_path.write_text(raw, encoding="utf-8")
            item = {"id": task["id"], "category": task["category"], "passed": bool(passed),
                    "runtime_seconds": round(time.monotonic() - task_started, 3),
                    "detail": detail, "error": error, "raw_response_file": raw_path.name}
            baseline.save_json(run_dir / (task["id"] + ".result.json"), item)
            results.append(item)
            baseline.save_json(run_dir / "progress.json", results)
            baseline.save_json(run_dir / "run_status.json", {"status": "in_progress",
                                                              "completed_tasks": len(results)})
        counts = Counter(item["category"] for item in results if item["passed"])
        categories = {category: {"passed": counts[category], "total": 4}
                      for category in development.core.CATEGORIES}
        summary = {"model": model_name, "task_count": len(results),
                   "passed": sum(item["passed"] for item in results),
                   "failed": sum(not item["passed"] for item in results),
                   "total_runtime_seconds": round(time.monotonic() - started, 3),
                   "load_runtime_seconds": load_seconds,
                   "by_category": dict(sorted(categories.items())), "tasks": results}
        baseline.save_json(run_dir / "summary.json", summary)
        baseline.save_json(run_dir / "run_status.json", {"status": "complete",
                                                          "completed_tasks": len(results)})
    except BaseException as error:
        baseline.save_json(run_dir / "run_status.json", {"status": "interrupted",
                                                          "completed_tasks": len(results),
                                                          "error": f"{type(error).__name__}: {error}"})
        raise
    print(f"Saved {summary['passed']}/{summary['task_count']} to {run_dir}")
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True, choices=("stock", "experiment_b", "experiment_c"))
    parser.add_argument("--experiment-c-run", type=Path,
                        help="Completed C run directory beneath training/output/experiment_c")
    parser.add_argument("--check", action="store_true", help="Check inputs without loading/querying a model")
    args = parser.parse_args()
    try:
        tasks, adapter, weights = check(args.model, args.experiment_c_run)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        parser.exit(2, f"C development preflight failed: {type(error).__name__}: {error}\n")
    if args.check:
        print(f"Ready: {args.model}, {len(tasks)} frozen C development tasks, "
              f"adapter={weights if weights else 'none'}; no model loaded")
        return 0
    return run(args.model, tasks, adapter, weights)


if __name__ == "__main__":
    raise SystemExit(main())
