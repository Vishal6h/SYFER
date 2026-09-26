#!/usr/bin/env python3
"""Evaluate Experiment B on the 16 frozen tasks; never modify Stage 1 or A."""

import argparse
import datetime as dt
import importlib.metadata
import json
import time
import uuid
from pathlib import Path

import run_baseline as baseline
import run_tuned as experiment_a  # Reuse its exact chat-template generation path.


ROOT = Path(__file__).resolve().parents[1]
TASKS = ROOT / "benchmark/tasks.json"
BASELINE_RUN = experiment_a.BASELINE_RUN
ADAPTER_RUN = ROOT / "training/output/experiment_b/experiment-20260926T111408Z-4838f847"
STAGE6_RECORD = ROOT / "results/stage6_experiment_a_record.json"
OUTPUT_ROOT = ROOT / "results/experiment_b"
CONFIG = ROOT / "training/config_experiment_b.json"
MODEL_ID = experiment_a.MODEL_ID
REVISION = experiment_a.REVISION
TASKS_SHA256 = experiment_a.TASKS_SHA256
BASELINE_RUNNER_SHA256 = experiment_a.BASELINE_RUNNER_SHA256
EXPECTED_OPTIONS = {"temperature": 0, "num_predict": 512, "seed": 42}
EXPECTED_A_FAILURES = {"simple_dedupe", "bug_last_index", "explain_slice",
                       "patch_slug", "repo_call_chain"}
EXPECTED_A_IMPROVED = {"bug_count_words", "explain_mutation", "patch_clamp",
                       "debug_inventory", "debug_parse_average", "tdd_palindrome"}


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def stage6_passes(tasks, stock):
    """Reconstruct A pass/fail from verified metadata, not missing raw files."""
    record = read_json(STAGE6_RECORD)
    ids = {task["id"] for task in tasks}
    require(record.get("run_id") == "20260926T095444Z-1dd18233" and
            record.get("baseline") == {"passed": 6, "total": 16} and
            record.get("experiment_a") == {"passed": 11, "total": 16} and
            record.get("raw_lightning_artifacts_preserved_in_git") is False and
            record.get("artifact_note") == "Raw Lightning Stage 6 artifacts were not preserved in Git.",
            "Stage 6 provenance does not match the verified 6/16 and 11/16 results")
    require(record.get("evaluation") == {"same_frozen_prompts_and_validators": True,
                                         "temperature": 0, "generation_limit_tokens": 512,
                                         "seed": 42}, "Stage 6 evaluation settings differ")
    improved = record.get("improved_tasks")
    regressed = record.get("regressed_tasks")
    remaining = record.get("remaining_failed_tasks")
    require(isinstance(improved, list) and len(improved) == 6 and set(improved) == EXPECTED_A_IMPROVED and
            regressed == ["explain_slice"] and isinstance(remaining, list) and len(remaining) == 5 and
            set(remaining) == EXPECTED_A_FAILURES, "Stage 6 task outcomes differ")
    stock_passes = {item["id"] for item in stock["tasks"] if item["passed"]}
    require(set(improved).isdisjoint(stock_passes) and set(regressed) <= stock_passes,
            "Stage 6 changes conflict with stock task outcomes")
    a_passes = (stock_passes | set(improved)) - set(regressed)
    require(len(a_passes) == 11 and ids - a_passes == set(remaining),
            "Stage 6 provenance does not reconstruct its five failures")
    return a_passes


def preflight():
    """Check frozen inputs, B artifact identity, and settings without loading a model."""
    require(experiment_a.sha256(TASKS) == TASKS_SHA256, "frozen task file hash changed")
    require(experiment_a.sha256(ROOT / "benchmark/run_baseline.py") == BASELINE_RUNNER_SHA256,
            "frozen baseline validator hash changed")
    require(experiment_a.sha256(ROOT / "dataset/syfer_train.jsonl") == experiment_a.TRAIN_SHA256 and
            experiment_a.sha256(ROOT / "dataset/syfer_validation.jsonl") == experiment_a.VALIDATION_SHA256,
            "frozen Stage 2 dataset hashes changed")
    require(baseline.OPTIONS == EXPECTED_OPTIONS, "evaluation settings changed")
    require(MODEL_ID == "Qwen/Qwen2.5-Coder-3B-Instruct" and
            REVISION == "89fe5444e8baf5736e70f528f1edcc79e6616ef6",
            "pinned base model or revision changed")
    require(OUTPUT_ROOT == ROOT / "results/experiment_b" and
            OUTPUT_ROOT.resolve() != experiment_a.OUTPUT_ROOT.resolve() and
            OUTPUT_ROOT != ADAPTER_RUN and not OUTPUT_ROOT.is_relative_to(ADAPTER_RUN),
            "Experiment B result path is not separate")
    tasks = read_json(TASKS)
    stock = read_json(BASELINE_RUN / "summary.json")
    stock_config = read_json(BASELINE_RUN / "run_config.json")
    require(len(tasks) == 16 and len({task["id"] for task in tasks}) == 16,
            "expected 16 unique frozen tasks")
    require(stock.get("task_count") == 16 and stock.get("passed") == 6 and
            [item["id"] for item in stock["tasks"]] == [task["id"] for task in tasks],
            "verified stock baseline is not the same 6/16 task set")
    require(stock_config.get("tasks_sha256") == TASKS_SHA256 and
            stock_config.get("runner_sha256") == BASELINE_RUNNER_SHA256 and
            stock_config.get("options") == EXPECTED_OPTIONS,
            "stock baseline used different tasks, validator, or settings")
    a_passes = stage6_passes(tasks, stock)

    require(ADAPTER_RUN == ROOT / "training/output/experiment_b/experiment-20260926T111408Z-4838f847",
            "Experiment B adapter run path changed")
    adapter = ADAPTER_RUN / "adapter"
    weights = adapter / "adapter_model.safetensors"
    require((adapter / "adapter_config.json").is_file(), "Experiment B adapter config missing")
    require(weights.is_file() and weights.stat().st_size > 0, "Experiment B adapter weights missing")
    adapter_config = read_json(adapter / "adapter_config.json")
    require(adapter_config.get("peft_type") == "LORA" and adapter_config.get("r") == 16 and
            adapter_config.get("lora_alpha") == 32 and adapter_config.get("lora_dropout") == 0.05 and
            adapter_config.get("base_model_name_or_path") in (None, MODEL_ID),
            "adapter config differs from planned B LoRA or pinned base")
    for name in ("config.json", "manifest.json", "loss_history.json", "experiment_metrics.json", "run_status.json"):
        require((ADAPTER_RUN / name).is_file(), f"Experiment B {name} missing")
    planned = read_json(CONFIG)
    actual = read_json(ADAPTER_RUN / "config.json")
    manifest = read_json(ADAPTER_RUN / "manifest.json")
    metrics = read_json(ADAPTER_RUN / "experiment_metrics.json")
    status = read_json(ADAPTER_RUN / "run_status.json")
    require(actual == planned and planned.get("experiment") == "B" and
            planned.get("model_id") == MODEL_ID and planned.get("model_revision") == REVISION,
            "Experiment B config differs from the pinned plan")
    train = ROOT / planned["train_file"]
    validation = ROOT / planned["validation_file"]
    require(experiment_a.sha256(train) == planned["train_sha256"] and
            experiment_a.sha256(validation) == planned["validation_sha256"],
            "Experiment B dataset hashes changed")
    require(manifest.get("model_id") == MODEL_ID and manifest.get("model_revision") == REVISION and
            manifest.get("train_sha256") == planned["train_sha256"] and
            manifest.get("validation_sha256") == planned["validation_sha256"] and
            manifest.get("experiment") == "B" and manifest.get("mode") == "train",
            "Experiment B manifest does not match pinned model and dataset")
    require(status.get("status") == "complete" and metrics.get("completed_normally") is True and
            status.get("optimizer_steps") == 12 and metrics.get("optimizer_steps") == 12,
            "Experiment B did not complete normally at 12 optimizer steps")
    return tasks, stock, a_passes, weights


def compare_with_a(results, stock, a_passes):
    """Compare B against stock and A, preserving the frozen task order."""
    stock_comparison = experiment_a.compare(results, stock)
    improved = [item["id"] for item in results if item["passed"] and item["id"] not in a_passes]
    regressed = [item["id"] for item in results if not item["passed"] and item["id"] in a_passes]
    unchanged_pass = [item["id"] for item in results if item["passed"] and item["id"] in a_passes]
    unchanged_fail = [item["id"] for item in results if not item["passed"] and item["id"] not in a_passes]
    categories = {}
    for item in results:
        row = categories.setdefault(item["category"], {"total": 0, "stock_passed": 0,
                                                        "experiment_a_passed": 0,
                                                        "experiment_b_passed": 0})
        row["total"] += 1
        row["experiment_a_passed"] += int(item["id"] in a_passes)
        row["experiment_b_passed"] += int(item["passed"])
    for category, row in categories.items():
        row["stock_passed"] = stock["by_category"][category]["passed"]
        row["change_from_a"] = row["experiment_b_passed"] - row["experiment_a_passed"]
    return {"stock_passed": 6, "experiment_a_passed": 11,
            "experiment_b_passed": sum(item["passed"] for item in results),
            "task_count": len(results), "improved_vs_a": improved, "regressed_vs_a": regressed,
            "unchanged_pass_vs_a": unchanged_pass, "unchanged_fail_vs_a": unchanged_fail,
            "by_category": categories, "versus_stock": stock_comparison}


def comparison_markdown(comparison, total_runtime):
    count = comparison["task_count"]
    b_passed = comparison["experiment_b_passed"]
    lines = ["# Experiment B versus Experiment A and stock", "",
             f"Stock: 6/{count} (37.5%). Experiment A: 11/{count} (68.8%). "
             f"Experiment B: {b_passed}/{count} ({100 * b_passed / count:.1f}%).",
             f"B versus A: {b_passed - 11:+d} tasks, {100 * (b_passed - 11) / count:+.2f} percentage points.",
             f"B task runtime: {total_runtime:.2f} seconds.", "",
             "| Category | Stock | A | B | B − A |", "| --- | ---: | ---: | ---: | ---: |"]
    for category, row in comparison["by_category"].items():
        lines.append(f"| {category} | {row['stock_passed']}/{row['total']} | "
                     f"{row['experiment_a_passed']}/{row['total']} | "
                     f"{row['experiment_b_passed']}/{row['total']} | {row['change_from_a']:+d} |")
    for title, key in (("Improved versus A", "improved_vs_a"), ("Regressed versus A", "regressed_vs_a"),
                       ("Unchanged passes", "unchanged_pass_vs_a"),
                       ("Unchanged failures", "unchanged_fail_vs_a")):
        lines.extend(["", f"## {title}", "",
                      ", ".join(f"`{task}`" for task in comparison[key]) or "None."])
    lines.extend(["", "## Interpretation", "",
                  "Experiment B was designed after inspecting the Stage 6 failures. "
                  "These original 16 tasks are therefore a DEVELOPMENT benchmark for B, "
                  "not an untouched final holdout. Use a new holdout for final claims.", "",
                  "All three scores use the same frozen prompts and validators, temperature 0, "
                  "a 512-token generation limit, and seed 42. A and B use the same pinned "
                  "Hugging Face base, chat template, and generation path with separate LoRA adapters. "
                  "Stock used Ollama, so serving differences remain in stock comparisons. "
                  "A task outcomes come from the verified Stage 6 summary record; its raw Lightning "
                  "artifacts were not preserved in Git."])
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Verify inputs and adapter without loading a model")
    args = parser.parse_args()
    try:
        tasks, stock, a_passes, weights = preflight()
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        parser.exit(2, f"Experiment B evaluation preflight failed: {type(error).__name__}: {error}\n")
    if args.check:
        print(f"Ready to evaluate {len(tasks)} frozen tasks using {weights}")
        return 0

    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig, set_seed

    require(torch.cuda.is_available(), "CUDA is required for 4-bit Experiment B evaluation")
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
        "model_id": MODEL_ID, "model_revision": REVISION,
        "adapter_run": str(ADAPTER_RUN.relative_to(ROOT)),
        "adapter_weights_sha256": experiment_a.sha256(weights),
        "adapter_config_sha256": experiment_a.sha256(ADAPTER_RUN / "adapter/adapter_config.json"),
        "experiment_b_config_sha256": experiment_a.sha256(CONFIG),
        "experiment_b_train_sha256": read_json(CONFIG)["train_sha256"],
        "experiment_b_validation_sha256": read_json(CONFIG)["validation_sha256"],
        "tasks_sha256": TASKS_SHA256, "baseline_runner_sha256": BASELINE_RUNNER_SHA256,
        "runner_sha256": experiment_a.sha256(Path(__file__)),
        "experiment_a_provenance": str(STAGE6_RECORD.relative_to(ROOT)),
        "experiment_a_provenance_sha256": experiment_a.sha256(STAGE6_RECORD),
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
    try:
        for task in tasks:
            task_started = time.monotonic()
            raw = ""
            try:
                raw = experiment_a.generate_raw(model, tokenizer, task["prompt"], torch, set_seed)
                passed, detail = baseline.validate(task, raw)
                error = None
            except Exception as exc:
                passed, detail, error = False, str(exc), type(exc).__name__
            (run_dir / (task["id"] + ".txt")).write_text(raw, encoding="utf-8")
            item = {"id": task["id"], "category": task["category"], "passed": bool(passed),
                    "runtime_seconds": round(time.monotonic() - task_started, 3),
                    "detail": detail, "error": error, "raw_response_file": task["id"] + ".txt"}
            baseline.save_json(run_dir / (task["id"] + ".result.json"), item)
            results.append(item)
            baseline.save_json(run_dir / "progress.json", results)
            baseline.save_json(run_dir / "run_status.json", {"status": "in_progress", "completed_tasks": len(results)})
            print(f"{'PASS' if passed else 'FAIL'} {task['id']} ({item['runtime_seconds']:.2f}s)", flush=True)
        elapsed = time.monotonic() - started
        comparison = compare_with_a(results, stock, a_passes)
        summary = {"model": MODEL_ID, "model_revision": REVISION, "task_count": len(results),
                   "passed": comparison["experiment_b_passed"],
                   "failed": len(results) - comparison["experiment_b_passed"],
                   "total_runtime_seconds": round(elapsed, 3), "load_runtime_seconds": load_seconds,
                   "by_category": comparison["by_category"], "tasks": results,
                   "comparison": comparison}
        baseline.save_json(run_dir / "summary.json", summary)
        (run_dir / "comparison.md").write_text(comparison_markdown(comparison, elapsed), encoding="utf-8")
        baseline.save_json(run_dir / "run_status.json", {"status": "complete", "completed_tasks": len(results)})
    except BaseException as error:
        baseline.save_json(run_dir / "run_status.json", {"status": "interrupted", "completed_tasks": len(results),
                                                          "error": f"{type(error).__name__}: {error}"})
        raise
    print(f"Saved {summary['passed']}/{summary['task_count']} results to {run_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
