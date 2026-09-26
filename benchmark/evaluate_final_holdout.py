#!/usr/bin/env python3
"""Run one pinned model on the frozen 32-task final holdout when requested."""

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
import run_tuned  # Exact same Hugging Face chat-template generation path.
from final_holdout import validate_holdout as holdout


ROOT = Path(__file__).resolve().parents[1]
TASKS = ROOT / "benchmark/final_holdout/tasks.json"
VALIDATOR = ROOT / "benchmark/final_holdout/validate_holdout.py"
OUTPUT_ROOT = ROOT / "results/final_holdout"
MODEL_ID = "Qwen/Qwen2.5-Coder-3B-Instruct"
REVISION = "89fe5444e8baf5736e70f528f1edcc79e6616ef6"
OPTIONS = {"temperature": 0, "num_predict": 512, "seed": 42}
TASKS_SHA256 = "862cf0dc1a3d11cdff1f1555dce85fe26fdef9fd93548eb34d7b7c5bb75187a9"
VALIDATOR_SHA256 = "f36aec792f6e3c0cb7d81765908d7bc5f8cfd279799cadb36628a9dbf3e4bec1"
ADAPTERS = {
    "experiment_a": ROOT / "training/output/experiment-20260926T093433Z-6630ef2a/adapter",
    "experiment_b": ROOT / "training/output/experiment_b/experiment-20260926T111408Z-4838f847/adapter",
}
LORA_SETTINGS = {"experiment_a": (8, 16), "experiment_b": (16, 32)}


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def check(model_name):
    """Validate holdout, settings, output separation, and selected adapter only."""
    require(model_name in {"stock", *ADAPTERS}, "unknown model name")
    require(MODEL_ID == run_tuned.MODEL_ID and REVISION == run_tuned.REVISION,
            "pinned base identifier or revision differs from Experiment A")
    require(OPTIONS == baseline.OPTIONS == {"temperature": 0, "num_predict": 512, "seed": 42},
            "generation settings differ from Experiment A")
    require(sha256(TASKS) == TASKS_SHA256 and sha256(VALIDATOR) == VALIDATOR_SHA256,
            "final holdout files changed after freeze")
    require(sha256(ROOT / "benchmark/run_baseline.py") == run_tuned.BASELINE_RUNNER_SHA256,
            "frozen Python/diff validators changed")
    require(OUTPUT_ROOT == ROOT / "results/final_holdout" and
            OUTPUT_ROOT.resolve() != run_tuned.OUTPUT_ROOT.resolve(),
            "final-holdout output path is not separate")
    report = holdout.validate_holdout()
    require(report["validation_error_count"] == 0 and report["task_count"] == 32 and
            report["reference_answers_validated"] == 32,
            "final holdout validation or contamination audit failed")
    tasks = json.loads(TASKS.read_text(encoding="utf-8"))
    adapter = ADAPTERS.get(model_name)
    weights = None
    if adapter:
        require(adapter == ROOT / ("training/output/experiment-20260926T093433Z-6630ef2a/adapter"
                                   if model_name == "experiment_a" else
                                   "training/output/experiment_b/experiment-20260926T111408Z-4838f847/adapter"),
                "adapter path differs from completed experiment")
        weights = adapter / "adapter_model.safetensors"
        config_path = adapter / "adapter_config.json"
        require(weights.is_file() and weights.stat().st_size > 0 and config_path.is_file(),
                f"{model_name} adapter weights or config missing")
        config = json.loads(config_path.read_text(encoding="utf-8"))
        rank, alpha = LORA_SETTINGS[model_name]
        require(config.get("peft_type") == "LORA" and config.get("r") == rank and
                config.get("lora_alpha") == alpha and config.get("lora_dropout") == 0.05 and
                config.get("base_model_name_or_path") in (None, MODEL_ID),
                f"{model_name} adapter metadata differs from pinned plan")
    return tasks, adapter, weights


def run(model_name, tasks, adapter, weights):
    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig, set_seed

    require(torch.cuda.is_available(), "CUDA is required for 4-bit final-holdout evaluation")
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
        "holdout_tasks_sha256": TASKS_SHA256, "holdout_validator_sha256": VALIDATOR_SHA256,
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
                passed, detail = holdout.validate_response(task, raw)
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
            print(f"{'PASS' if passed else 'FAIL'} {task['id']} ({item['runtime_seconds']:.2f}s)", flush=True)
        counts = Counter(item["category"] for item in results if item["passed"])
        by_category = {category: {"passed": counts[category], "total": 4}
                       for category in holdout.CATEGORIES}
        elapsed = round(time.monotonic() - started, 3)
        summary = {"model": model_name, "task_count": len(results),
                   "passed": sum(item["passed"] for item in results),
                   "failed": sum(not item["passed"] for item in results),
                   "total_runtime_seconds": elapsed, "load_runtime_seconds": load_seconds,
                   "by_category": dict(sorted(by_category.items())), "tasks": results}
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
    parser.add_argument("--model", required=True, choices=("stock", "experiment_a", "experiment_b"))
    parser.add_argument("--check", action="store_true", help="Validate files and settings; load no model")
    args = parser.parse_args()
    try:
        tasks, adapter, weights = check(args.model)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        parser.exit(2, f"Final holdout preflight failed: {type(error).__name__}: {error}\n")
    if args.check:
        print(f"Ready: {args.model}, {len(tasks)} frozen tasks, "
              f"adapter={weights if weights else 'none'}; no model loaded")
        return 0
    return run(args.model, tasks, adapter, weights)


if __name__ == "__main__":
    raise SystemExit(main())
