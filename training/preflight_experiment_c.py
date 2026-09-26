#!/usr/bin/env python3
"""Verify the frozen C inputs and, on the training host, CUDA readiness."""

import argparse
import importlib.metadata
import json
import sys

from preflight_experiment_a import EXPECTED_HASHES
from train_qlora import HERE, ROOT, MODEL_ID, MODEL_REVISION, make_training_arguments, sha256


CONFIG = HERE / "config_experiment_c.json"
TRAIN = ROOT / "dataset/experiment_c_train.jsonl"
VALIDATION = ROOT / "dataset/experiment_c_validation.jsonl"
OUTPUT = HERE / "output/experiment_c"
DRY_RUN_REPORT = HERE / "dry_run_experiment_c.json"
FROZEN = {
    **EXPECTED_HASHES,
    "benchmark/final_holdout/tasks.json": "862cf0dc1a3d11cdff1f1555dce85fe26fdef9fd93548eb34d7b7c5bb75187a9",
    "benchmark/final_holdout/validate_holdout.py": "f36aec792f6e3c0cb7d81765908d7bc5f8cfd279799cadb36628a9dbf3e4bec1",
    "benchmark/experiment_c_dev/tasks.json": "d428a4186944358b420c754a70e70027e6bc0251d8320ad058db4e3609eb04b4",
    "benchmark/experiment_c_dev/validate_c_dev.py": "39fa89524df13d27005d607f57ac0504c20e0a6fbbf0acc2f6c65b0ea230801f",
    "dataset/experiment_b_train.jsonl": "62a87bb6b24ab6233773aa24a09fea9c89b133bc500a003da0c2730aa8c3d497",
    "dataset/experiment_b_validation.jsonl": "5515b5a7b1ad78ae2f27cd38dc900c8bf624988a95701b20db7dcfde1f4bd01b",
}
EXPECTED_LORA = {"rank": 16, "alpha": 32, "dropout": 0.05,
                 "target_modules": "all-linear", "bias": "none"}
EXPECTED_TRAINING = {"epochs": 1, "learning_rate": 0.00005,
                     "per_device_batch_size": 1, "gradient_accumulation_steps": 8,
                     "gradient_checkpointing": True, "warmup_ratio": 0.05,
                     "weight_decay": 0.0, "logging_steps": 1, "max_grad_norm": 1.0}


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def check(local=False):
    errors = []
    config = {}
    for name, expected in FROZEN.items():
        path = ROOT / name
        if not path.is_file() or sha256(path) != expected:
            errors.append(f"frozen hash mismatch: {name}")
    try:
        config = read_json(CONFIG)
        if (config.get("experiment") != "C" or config.get("model_id") != MODEL_ID or
                config.get("model_revision") != MODEL_REVISION or
                config.get("train_file") != "dataset/experiment_c_train.jsonl" or
                config.get("validation_file") != "dataset/experiment_c_validation.jsonl" or
                config.get("output_root") != "training/output/experiment_c" or
                config.get("seed") != 42 or config.get("max_sequence_length") != 768 or
                config.get("min_training_vram_gb") != 12 or
                config.get("quantization") != {"load_in_4bit": True, "quant_type": "nf4",
                                               "double_quant": True, "compute_dtype": "auto"} or
                config.get("lora") != EXPECTED_LORA or
                config.get("training") != EXPECTED_TRAINING):
            errors.append("Experiment C config differs from the pinned fresh-base plan")
        if not TRAIN.is_file() or sha256(TRAIN) != config.get("train_sha256"):
            errors.append("Experiment C train hash mismatch")
        if not VALIDATION.is_file() or sha256(VALIDATION) != config.get("validation_sha256"):
            errors.append("Experiment C validation hash mismatch")
        sys.path.insert(0, str(ROOT / "dataset"))
        from validate_experiment_c import validate

        stats = validate()
        if (stats["validation_error_count"] != 0 or stats["validated_examples"] != 120 or
                stats["train_examples"] != 88 or stats["validation_examples"] != 32 or
                stats["hashes"].get(TRAIN.name) != config.get("train_sha256") or
                stats["hashes"].get(VALIDATION.name) != config.get("validation_sha256")):
            errors.append("Experiment C dataset validation failed")
        sys.path.insert(0, str(ROOT / "benchmark/experiment_c_dev"))
        from validate_c_dev import validate as validate_dev

        development = validate_dev()
        if (development["error_count"] != 0 or development["task_count"] != 32 or
                development["validated_references"] != 32):
            errors.append("frozen C development benchmark validation failed")
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        errors.append(f"C input validation failed: {type(error).__name__}: {error}")
    static_passed = not errors
    if not local:
        try:
            report = read_json(DRY_RUN_REPORT)
            if (report.get("chat_format_status") != "passed_all_examples" or
                    report.get("chat_template_available") is not True or
                    report.get("assistant_label_check") is not True or
                    report.get("train_sha256") != config.get("train_sha256") or
                    report.get("validation_sha256") != config.get("validation_sha256") or
                    report.get("max_train_tokens", 10**9) > 768 or
                    report.get("max_validation_tokens", 10**9) > 768 or
                    report.get("full_model_loaded") is not False):
                errors.append("Experiment C real-tokenizer dry run did not pass")
        except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
            errors.append(f"Experiment C dry-run report missing or invalid: {error}")
        for package in ("torch", "transformers", "datasets", "peft", "bitsandbytes", "accelerate", "trl"):
            try:
                importlib.metadata.version(package)
            except importlib.metadata.PackageNotFoundError:
                errors.append(f"missing training package: {package}")
        try:
            import torch
            from transformers import TrainingArguments

            if not torch.cuda.is_available():
                errors.append("CUDA is unavailable")
            else:
                gpu = torch.cuda.get_device_properties(0)
                if gpu.total_memory < 12 * 1024**3:
                    errors.append(f"GPU has less than 12 GiB: {gpu.name}")
                args = make_training_arguments(config, OUTPUT / "preflight-not-created", False,
                                               torch.cuda.is_bf16_supported(), TrainingArguments)
                if (args.max_steps != -1 or args.gradient_accumulation_steps != 8 or
                        args.num_train_epochs != 1):
                    errors.append("installed TrainingArguments changed the planned C settings")
        except Exception as error:
            errors.append(f"PyTorch/Transformers host check failed: {type(error).__name__}: {error}")
    return {"static_checks_passed": static_passed, "host_checks_performed": not local,
            "ready_for_training": not local and not errors, "errors": errors,
            "output_root": str(OUTPUT), "train_sha256": config.get("train_sha256"),
            "validation_sha256": config.get("validation_sha256")}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--local", action="store_true", help="Static checks only; no tokenizer/model/GPU")
    args = parser.parse_args()
    report = check(local=args.local)
    print(json.dumps(report, indent=2))
    return 0 if not report["errors"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
