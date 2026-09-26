#!/usr/bin/env python3
"""Check frozen inputs, Experiment B data/config, and T4 host readiness."""

import argparse
import importlib.metadata
import json
from pathlib import Path

from preflight_experiment_a import EXPECTED_HASHES, VERSIONS
from train_qlora import HERE, ROOT, sha256


CONFIG = HERE / "config_experiment_b.json"
TRAIN = ROOT / "dataset/experiment_b_train.jsonl"
VALIDATION = ROOT / "dataset/experiment_b_validation.jsonl"
OUTPUT = HERE / "output/experiment_b"
STAGE6_RUN_ID = "20260926T095444Z-1dd18233"
STAGE6_RUN_PATH = Path("results/tuned") / STAGE6_RUN_ID
STAGE6_RECORD_PATH = Path("results/stage6_experiment_a_record.json")
EXPECTED_FAILURES = {"simple_dedupe", "bug_last_index", "explain_slice",
                     "patch_slug", "repo_call_chain"}
EXPECTED_IMPROVED = {"bug_count_words", "explain_mutation", "patch_clamp",
                     "debug_inventory", "debug_parse_average", "tdd_palindrome"}
EXPECTED_LORA = {"rank": 16, "alpha": 32, "dropout": 0.05,
                 "target_modules": "all-linear", "bias": "none"}
EXPECTED_TRAINING = {"epochs": 1, "learning_rate": 0.0001,
                     "per_device_batch_size": 1, "gradient_accumulation_steps": 8,
                     "gradient_checkpointing": True, "warmup_ratio": 0.05,
                     "weight_decay": 0.0, "logging_steps": 1, "max_grad_norm": 1.0}


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def validate_stage6_run(run):
    """Prefer the original Lightning run when it is present locally."""
    summary = read_json(run / "summary.json")
    status = read_json(run / "run_status.json")
    run_config = read_json(run / "run_config.json")
    failed = {item["id"] for item in summary["tasks"] if not item["passed"]}
    if (status.get("status") != "complete" or summary.get("task_count") != 16 or
            summary.get("passed") != 11 or len(summary["tasks"]) != 16 or
            len({item["id"] for item in summary["tasks"]}) != 16 or
            failed != EXPECTED_FAILURES or
            run_config.get("tasks_sha256") != EXPECTED_HASHES["benchmark/tasks.json"] or
            run_config.get("baseline_runner_sha256") != EXPECTED_HASHES["benchmark/run_baseline.py"]):
        raise ValueError("original Stage 6 run does not match the reported 11/16 result")


def validate_stage6_record(path):
    """Accept only the precise user-verified summary, never substitute raw artifacts."""
    record = read_json(path)
    expected_keys = {"stage", "run_id", "original_run_path", "baseline",
                     "experiment_a", "improved_tasks", "regressed_tasks",
                     "remaining_failed_tasks", "evaluation",
                     "raw_lightning_artifacts_preserved_in_git", "artifact_note"}
    def exact_score(value, passed):
        return (isinstance(value, dict) and set(value) == {"passed", "total"} and
                type(value["passed"]) is int and value["passed"] == passed and
                type(value["total"]) is int and value["total"] == 16)

    def exact_task_set(value, expected):
        return (isinstance(value, list) and all(isinstance(item, str) for item in value)
                and len(value) == len(expected) and set(value) == expected)

    evaluation = record.get("evaluation", {}) if isinstance(record, dict) else {}
    if (not isinstance(record, dict) or set(record) != expected_keys or
            type(record["stage"]) is not int or record["stage"] != 6 or
            record["run_id"] != STAGE6_RUN_ID or
            record["original_run_path"] != STAGE6_RUN_PATH.as_posix() or
            not exact_score(record["baseline"], 6) or
            not exact_score(record["experiment_a"], 11) or
            not exact_task_set(record["improved_tasks"], EXPECTED_IMPROVED) or
            record["regressed_tasks"] != ["explain_slice"] or
            not exact_task_set(record["remaining_failed_tasks"], EXPECTED_FAILURES) or
            not isinstance(evaluation, dict) or
            set(evaluation) != {"same_frozen_prompts_and_validators", "temperature",
                                "generation_limit_tokens", "seed"} or
            evaluation["same_frozen_prompts_and_validators"] is not True or
            type(evaluation["temperature"]) is not int or evaluation["temperature"] != 0 or
            type(evaluation["generation_limit_tokens"]) is not int or
            evaluation["generation_limit_tokens"] != 512 or
            type(evaluation["seed"]) is not int or evaluation["seed"] != 42 or
            record["raw_lightning_artifacts_preserved_in_git"] is not False or
            record["artifact_note"] != "Raw Lightning Stage 6 artifacts were not preserved in Git."):
        raise ValueError("Stage 6 provenance record differs from the verified summary")


def stage6_evidence():
    run = ROOT / STAGE6_RUN_PATH
    if run.exists():
        validate_stage6_run(run)  # An invalid original run cannot be bypassed by metadata.
        return "run_directory", run
    record = ROOT / STAGE6_RECORD_PATH
    validate_stage6_record(record)
    return "provenance_record", record


def check(local=False):
    errors = []
    config = {}
    for name, expected in EXPECTED_HASHES.items():
        path = ROOT / name
        if not path.is_file() or sha256(path) != expected:
            errors.append(f"frozen hash mismatch: {name}")
    try:
        config = read_json(CONFIG)
        if (config.get("experiment") != "B" or
                config.get("model_id") != "Qwen/Qwen2.5-Coder-3B-Instruct" or
                config.get("model_revision") != "89fe5444e8baf5736e70f528f1edcc79e6616ef6" or
                config.get("train_file") != "dataset/experiment_b_train.jsonl" or
                config.get("validation_file") != "dataset/experiment_b_validation.jsonl" or
                config.get("output_root") != "training/output/experiment_b" or
                config.get("seed") != 42 or config.get("max_sequence_length") != 768 or
                config.get("min_training_vram_gb") != 12 or
                config.get("quantization") != {"load_in_4bit": True, "quant_type": "nf4",
                                               "double_quant": True, "compute_dtype": "auto"} or
                config.get("lora") != EXPECTED_LORA or
                config.get("training") != EXPECTED_TRAINING):
            errors.append("Experiment B config differs from the planned one-epoch setup")
        if not TRAIN.is_file() or sha256(TRAIN) != config.get("train_sha256"):
            errors.append("Experiment B train hash mismatch")
        if not VALIDATION.is_file() or sha256(VALIDATION) != config.get("validation_sha256"):
            errors.append("Experiment B validation hash mismatch")
        stats = read_json(ROOT / "dataset/experiment_b_stats.json")
        if (stats.get("validation_error_count") != 0 or stats.get("new_examples") != 80 or
                stats.get("train_examples") != 190 or stats.get("validation_examples") != 60 or
                stats.get("dataset_hashes", {}).get(TRAIN.name) != config.get("train_sha256") or
                stats.get("dataset_hashes", {}).get(VALIDATION.name) != config.get("validation_sha256")):
            errors.append("Experiment B dataset validation stats are stale or invalid")
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        errors.append(f"Experiment B config/data check failed: {type(error).__name__}: {error}")
    stage6_source = None
    stage6_path = None
    try:
        stage6_source, stage6_path = stage6_evidence()
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        errors.append(f"Stage 6 result check failed: {type(error).__name__}: {error}")
    static_passed = not errors
    if not local:
        try:
            report = read_json(HERE / "dry_run_experiment_b.json")
            if (report.get("chat_format_status") != "passed_all_examples" or
                    report.get("assistant_label_check") is not True or
                    report.get("train_sha256") != config.get("train_sha256") or
                    report.get("validation_sha256") != config.get("validation_sha256") or
                    report.get("max_train_tokens", 10**9) > 768 or
                    report.get("max_validation_tokens", 10**9) > 768):
                errors.append("Experiment B real-tokenizer dry run did not pass")
        except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
            errors.append(f"Experiment B dry-run report missing or invalid: {error}")
        for package, expected in VERSIONS.items():
            try:
                observed = importlib.metadata.version(package)
            except importlib.metadata.PackageNotFoundError:
                observed = None
            if observed is None or observed.split("+", 1)[0] != expected:
                errors.append(f"{package}: expected {expected}, found {observed}")
        try:
            import torch

            if not torch.cuda.is_available():
                errors.append("CUDA is unavailable")
            else:
                gpu = torch.cuda.get_device_properties(0)
                if "T4" not in gpu.name or gpu.total_memory < 12 * 1024**3:
                    errors.append(f"expected T4 with at least 12 GiB, found {gpu.name}")
        except Exception as error:
            errors.append(f"PyTorch GPU check failed: {type(error).__name__}: {error}")
    return {"static_checks_passed": static_passed, "host_checks_performed": not local,
            "stage6_run": str(stage6_path) if stage6_source == "run_directory" else None,
            "stage6_evidence_source": stage6_source,
            "stage6_evidence_path": str(stage6_path) if stage6_path else None,
            "ready_for_training": not local and not errors, "errors": errors,
            "output_root": str(OUTPUT)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--local", action="store_true", help="Skip tokenizer, package, and GPU host checks")
    args = parser.parse_args()
    report = check(local=args.local)
    print(json.dumps(report, indent=2))
    return 0 if not report["errors"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
