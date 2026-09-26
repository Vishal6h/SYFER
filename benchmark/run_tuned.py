#!/usr/bin/env python3
"""Evaluate the pinned Experiment A adapter on the frozen Stage 1 tasks."""

import argparse
import datetime as dt
import hashlib
import importlib.metadata
import json
import time
import uuid
from pathlib import Path

import run_baseline as baseline  # Reuse the frozen validators unchanged.


ROOT = Path(__file__).resolve().parents[1]
TASKS = ROOT / "benchmark/tasks.json"
ADAPTER_RUN = ROOT / "training/output/experiment-20260926T093433Z-6630ef2a"
BASELINE_RUN = ROOT / "results/baseline/20260926T060444Z-601c3126"
OUTPUT_ROOT = ROOT / "results/tuned"
MODEL_ID = "Qwen/Qwen2.5-Coder-3B-Instruct"
REVISION = "89fe5444e8baf5736e70f528f1edcc79e6616ef6"
TASKS_SHA256 = "48bb49ffdba9bb2e76f51251bc2b91407a0d10215c481e67041c6afa6e15bd1a"
BASELINE_RUNNER_SHA256 = "17eb4e59df7932de874e494d6e3b12fefdf6fff7cad826a7b0aaf3d9c13adeb0"
TRAIN_SHA256 = "64b0a10b0fe0f26e028b289dcbf7b5c98330ace089947671e25479e4c07afd35"
VALIDATION_SHA256 = "57b12aa06063abad06cfe9e19564f4488e2d181df8f4df879c059a16aa929f5e"


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def preflight():
    require(sha256(TASKS) == TASKS_SHA256, "frozen task file hash changed")
    require(sha256(ROOT / "benchmark/run_baseline.py") == BASELINE_RUNNER_SHA256,
            "frozen baseline validator hash changed")
    require(sha256(ROOT / "dataset/syfer_train.jsonl") == TRAIN_SHA256, "train dataset hash changed")
    require(sha256(ROOT / "dataset/syfer_validation.jsonl") == VALIDATION_SHA256,
            "validation dataset hash changed")
    tasks = json.loads(TASKS.read_text(encoding="utf-8"))
    baseline_summary = json.loads((BASELINE_RUN / "summary.json").read_text(encoding="utf-8"))
    baseline_config = json.loads((BASELINE_RUN / "run_config.json").read_text(encoding="utf-8"))
    require(len(tasks) == 16 and len({task["id"] for task in tasks}) == 16, "expected 16 unique frozen tasks")
    require(baseline_summary["task_count"] == 16 and baseline_summary["passed"] == 6,
            "verified stock baseline is not 6/16")
    require(baseline_config["tasks_sha256"] == TASKS_SHA256 and
            baseline_config["runner_sha256"] == BASELINE_RUNNER_SHA256,
            "baseline run did not use the frozen tasks and validator")
    require(baseline_config["options"] == baseline.OPTIONS, "baseline generation settings changed")
    require([task["id"] for task in tasks] == [item["id"] for item in baseline_summary["tasks"]],
            "baseline task order differs")
    require((ADAPTER_RUN / "adapter/adapter_config.json").is_file(), "final adapter config missing")
    weights = ADAPTER_RUN / "adapter/adapter_model.safetensors"
    require(weights.is_file() and weights.stat().st_size > 0, "final adapter weights missing")
    adapter_config = json.loads((ADAPTER_RUN / "adapter/adapter_config.json").read_text(encoding="utf-8"))
    require(adapter_config.get("peft_type") == "LORA" and adapter_config.get("r") == 8 and
            adapter_config.get("lora_alpha") == 16 and adapter_config.get("lora_dropout") == 0.05,
            "final adapter is not the planned Experiment A LoRA")
    require(adapter_config.get("base_model_name_or_path") in (None, MODEL_ID),
            "adapter config refers to a different base model")
    for name in ("config.json", "manifest.json", "loss_history.json", "experiment_metrics.json", "run_status.json"):
        require((ADAPTER_RUN / name).is_file(), f"Experiment A {name} missing")
    config = json.loads((ADAPTER_RUN / "config.json").read_text(encoding="utf-8"))
    manifest = json.loads((ADAPTER_RUN / "manifest.json").read_text(encoding="utf-8"))
    metrics = json.loads((ADAPTER_RUN / "experiment_metrics.json").read_text(encoding="utf-8"))
    status = json.loads((ADAPTER_RUN / "run_status.json").read_text(encoding="utf-8"))
    require(config["model_id"] == MODEL_ID and config["model_revision"] == REVISION,
            "Experiment A model ID or revision changed")
    require(manifest["model_id"] == MODEL_ID and manifest["model_revision"] == REVISION,
            "Experiment A manifest model ID or revision changed")
    require(manifest["train_sha256"] == TRAIN_SHA256 and
            manifest["validation_sha256"] == VALIDATION_SHA256,
            "Experiment A manifest dataset hashes changed")
    require(status.get("status") == "complete" and metrics.get("completed_normally") is True and
            metrics.get("optimizer_steps") == 17, "Experiment A did not complete normally at 17 steps")
    return tasks, baseline_summary, weights


def generate_raw(model, tokenizer, prompt, torch, set_seed):
    set_seed(baseline.OPTIONS["seed"])
    inputs = tokenizer.apply_chat_template([{"role": "user", "content": prompt}],
                                           tokenize=True, add_generation_prompt=True,
                                           return_dict=True, return_tensors="pt").to("cuda")
    prompt_length = inputs["input_ids"].shape[-1]
    with torch.inference_mode():
        output = model.generate(**inputs, do_sample=False,
                                max_new_tokens=baseline.OPTIONS["num_predict"],
                                return_dict_in_generate=False,
                                pad_token_id=tokenizer.eos_token_id)
    return tokenizer.decode(output[0][prompt_length:], skip_special_tokens=True)


def compare(results, stock):
    prior = {item["id"]: item for item in stock["tasks"]}
    improved = [item["id"] for item in results if item["passed"] and not prior[item["id"]]["passed"]]
    regressed = [item["id"] for item in results if not item["passed"] and prior[item["id"]]["passed"]]
    unchanged_pass = [item["id"] for item in results if item["passed"] and prior[item["id"]]["passed"]]
    unchanged_fail = [item["id"] for item in results if not item["passed"] and not prior[item["id"]]["passed"]]
    tuned_passed = sum(item["passed"] for item in results)
    stock_passed = stock["passed"]
    categories = {}
    for item in results:
        row = categories.setdefault(item["category"], {"tuned_passed": 0, "total": 0,
                                                        "stock_passed": stock["by_category"][item["category"]]["passed"]})
        row["tuned_passed"] += int(item["passed"])
        row["total"] += 1
    for row in categories.values():
        row["task_gain"] = row["tuned_passed"] - row["stock_passed"]
    return {"stock_passed": stock_passed, "tuned_passed": tuned_passed,
            "task_count": len(results), "absolute_task_gain": tuned_passed - stock_passed,
            "percentage_point_gain": round(100 * (tuned_passed - stock_passed) / len(results), 2),
            "relative_improvement_percent": round(100 * (tuned_passed - stock_passed) / stock_passed, 2),
            "improved_tasks": improved, "regressed_tasks": regressed,
            "unchanged_pass_tasks": unchanged_pass, "unchanged_fail_tasks": unchanged_fail,
            "by_category": categories}


def comparison_markdown(comparison, total_runtime):
    lines = ["# Experiment A versus frozen stock baseline", "",
             f"Stock: {comparison['stock_passed']}/{comparison['task_count']} "
             f"({100 * comparison['stock_passed'] / comparison['task_count']:.1f}%). "
             f"Tuned: {comparison['tuned_passed']}/{comparison['task_count']} "
             f"({100 * comparison['tuned_passed'] / comparison['task_count']:.1f}%).",
             f"Gain: {comparison['absolute_task_gain']:+d} tasks; "
             f"{comparison['percentage_point_gain']:+.1f} percentage points; "
             f"{comparison['relative_improvement_percent']:+.1f}% relative to stock.",
             f"Tuned task runtime: {total_runtime:.2f} seconds.", "",
             "| Category | Stock | Tuned | Task gain |", "| --- | ---: | ---: | ---: |"]
    for category, row in comparison["by_category"].items():
        lines.append(f"| {category} | {row['stock_passed']}/{row['total']} | "
                     f"{row['tuned_passed']}/{row['total']} | {row['task_gain']:+d} |")
    for label, key in (("Improved", "improved_tasks"), ("Regressed", "regressed_tasks"),
                       ("Unchanged passes", "unchanged_pass_tasks"),
                       ("Unchanged failures", "unchanged_fail_tasks")):
        lines.extend(["", f"## {label}", "", ", ".join(f"`{name}`" for name in comparison[key]) or "None."])
    declined = [category for category, row in comparison["by_category"].items() if row["task_gain"] < 0]
    remaining = comparison["regressed_tasks"] + comparison["unchanged_fail_tasks"]
    lines.extend(["", "## Categories that regressed", "", ", ".join(declined) or "None.",
                  "", "## Remaining failed tasks", "",
                  ", ".join(f"`{name}`" for name in remaining) or "None."])
    lines.extend(["", "Same 16 prompt strings and frozen validators. Both runs use temperature 0, "
                  "512-token generation limits, and seed 42. The stock run used Ollama; "
                  "the tuned run uses the pinned Hugging Face base plus LoRA and its chat template. "
                  "Serving and tokenizer differences mean this is a product comparison, "
                  "not an adapter-only ablation."])
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Verify frozen inputs and adapter artifacts; do not load a model")
    args = parser.parse_args()
    try:
        tasks, stock, weights = preflight()
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        parser.exit(2, f"Tuned evaluation preflight failed: {type(error).__name__}: {error}\n")
    if args.check:
        print(f"Ready to evaluate {len(tasks)} frozen tasks with {weights}")
        return 0
    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig, set_seed

    require(torch.cuda.is_available(), "CUDA is required for 4-bit tuned evaluation")
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
    model = PeftModel.from_pretrained(base, ADAPTER_RUN / "adapter", is_trainable=False)
    model.eval()
    load_seconds = round(time.monotonic() - load_started, 3)

    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    run_id = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    run_dir = OUTPUT_ROOT / run_id
    run_dir.mkdir(exist_ok=False)
    baseline.save_json(run_dir / "tasks_snapshot.json", tasks)
    baseline.save_json(run_dir / "run_config.json", {
        "model_id": MODEL_ID, "model_revision": REVISION, "adapter_run": str(ADAPTER_RUN.relative_to(ROOT)),
        "adapter_weights_sha256": sha256(weights), "tasks_sha256": TASKS_SHA256,
        "runner_sha256": sha256(Path(__file__)),
        "baseline_runner_sha256": BASELINE_RUNNER_SHA256,
        "baseline_run": str(BASELINE_RUN.relative_to(ROOT)), "options": baseline.OPTIONS,
        "generation": "greedy Hugging Face chat template; max_new_tokens=512",
        "load_runtime_seconds": load_seconds,
        "packages": {name: importlib.metadata.version(name) for name in
                     ("torch", "transformers", "peft", "bitsandbytes", "accelerate")},
        "started_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
    })
    baseline.save_json(run_dir / "run_status.json", {"status": "in_progress", "completed_tasks": 0})
    results = []
    started = time.monotonic()
    for task in tasks:
        task_started = time.monotonic()
        raw = ""
        try:
            raw = generate_raw(model, tokenizer, task["prompt"], torch, set_seed)
            (run_dir / (task["id"] + ".txt")).write_text(raw, encoding="utf-8")
            passed, detail = baseline.validate(task, raw)
            error = None
        except Exception as exc:
            passed, detail, error = False, str(exc), type(exc).__name__
            (run_dir / (task["id"] + ".txt")).write_text(raw, encoding="utf-8")
        item = {"id": task["id"], "category": task["category"], "passed": bool(passed),
                "runtime_seconds": round(time.monotonic() - task_started, 3),
                "detail": detail, "error": error, "raw_response_file": task["id"] + ".txt"}
        results.append(item)
        baseline.save_json(run_dir / "progress.json", results)
        baseline.save_json(run_dir / "run_status.json", {"status": "in_progress", "completed_tasks": len(results)})
        print(f"{'PASS' if passed else 'FAIL'} {task['id']} ({item['runtime_seconds']:.2f}s)", flush=True)
    elapsed = time.monotonic() - started
    comparison = compare(results, stock)
    summary = {"model": MODEL_ID, "model_revision": REVISION, "task_count": len(results),
               "passed": comparison["tuned_passed"], "failed": len(results) - comparison["tuned_passed"],
               "total_runtime_seconds": round(elapsed, 3), "load_runtime_seconds": load_seconds,
               "by_category": comparison["by_category"], "tasks": results,
               "comparison": comparison}
    baseline.save_json(run_dir / "summary.json", summary)
    (run_dir / "comparison.md").write_text(comparison_markdown(comparison, elapsed), encoding="utf-8")
    baseline.save_json(run_dir / "run_status.json", {"status": "complete", "completed_tasks": len(results)})
    print(f"Saved {summary['passed']}/{summary['task_count']} results to {run_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
