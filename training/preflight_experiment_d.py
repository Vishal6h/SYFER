#!/usr/bin/env python3
"""Check frozen D inputs locally, then tokenizer/CUDA readiness on the GPU host."""

import argparse
import importlib.metadata
import json
import sys

from preflight_experiment_c import FROZEN as PRIOR_FROZEN
from train_qlora import HERE, ROOT, MODEL_ID, MODEL_REVISION, make_training_arguments, sha256

CONFIG = HERE / "config_experiment_d.json"
TRAIN = ROOT / "dataset/experiment_d_train.jsonl"
VALIDATION = ROOT / "dataset/experiment_d_validation.jsonl"
OUTPUT = HERE / "output/experiment_d"
DRY_RUN_REPORT = HERE / "dry_run_experiment_d.json"
FROZEN = {
    **PRIOR_FROZEN,
    "dataset/experiment_c_train.jsonl": "6e89c5c4655738f92154a441e5302004ddf245721f49eae0b71fa89daf1d64ba",
    "dataset/experiment_c_validation.jsonl": "45efc706e096df71e11126ed77356b7f1fab6022eac2a91d45f340154444e291",
    "benchmark/experiment_d_dev/tasks.json": "c2e858e1b67dd6d8d529e7f80db9cb6a9eb6715a80066e53c686544f188ad788",
    "benchmark/experiment_d_dev/validate_d_dev.py": "4e0a7d268861f7df898406116e52ec80037d48b73a3b4691939ae539c3558792",
    "docs/TRAINING_OUTPUT_CONTRACT.md": "346fde854d59d5c02daaa55bb74e9c00dd9fdb1de732070795eda87c3e74733f",
}
EXPECTED_QUANT = {"load_in_4bit":True,"quant_type":"nf4","double_quant":True,"compute_dtype":"auto"}
EXPECTED_LORA = {"rank":16,"alpha":32,"dropout":0.05,"target_modules":"all-linear","bias":"none"}
EXPECTED_TRAINING = {"epochs":1,"learning_rate":0.000075,"per_device_batch_size":1,
                     "gradient_accumulation_steps":8,"gradient_checkpointing":True,
                     "warmup_ratio":0.05,"weight_decay":0.0,"logging_steps":1,"max_grad_norm":1.0}


def check(local=False):
    errors = []
    config = {}
    for name,expected in FROZEN.items():
        path = ROOT / name
        if not path.is_file() or sha256(path) != expected:
            errors.append(f"frozen hash mismatch: {name}")
    try:
        config = json.loads(CONFIG.read_text(encoding="utf-8"))
        if (config.get("experiment") != "D" or config.get("model_id") != MODEL_ID or
                config.get("model_revision") != MODEL_REVISION or
                config.get("train_file") != "dataset/experiment_d_train.jsonl" or
                config.get("validation_file") != "dataset/experiment_d_validation.jsonl" or
                config.get("output_root") != "training/output/experiment_d" or
                config.get("seed") != 42 or config.get("max_sequence_length") != 768 or
                config.get("min_training_vram_gb") != 12 or
                config.get("quantization") != EXPECTED_QUANT or
                config.get("lora") != EXPECTED_LORA or
                config.get("training") != EXPECTED_TRAINING):
            errors.append("Experiment D config differs from the pinned fresh-base plan")
        if not TRAIN.is_file() or sha256(TRAIN) != config.get("train_sha256"):
            errors.append("Experiment D train hash mismatch")
        if not VALIDATION.is_file() or sha256(VALIDATION) != config.get("validation_sha256"):
            errors.append("Experiment D validation hash mismatch")
        sys.path.insert(0,str(ROOT / "dataset"))
        from validate_experiment_d import inspect
        stats = inspect()
        if (stats["validation_error_count"] != 0 or stats["total"] != 200 or
                stats["train"] != 160 or stats["validation"] != 40 or
                stats["sha256"]["train"] != config.get("train_sha256") or
                stats["sha256"]["validation"] != config.get("validation_sha256")):
            errors.append("Experiment D dataset validation failed")
        sys.path.insert(0,str(ROOT / "benchmark/experiment_d_dev"))
        from validate_d_dev import validate_benchmark
        development = validate_benchmark()
        if (development["error_count"] != 0 or development["task_count"] != 32 or
                development["validated_references"] != 32 or
                any(development["contamination"].values())):
            errors.append("frozen D development benchmark validation failed")
    except (OSError,ValueError,KeyError,TypeError,json.JSONDecodeError) as error:
        errors.append(f"D input validation failed: {type(error).__name__}: {error}")
    static_passed = not errors
    if not local:
        try:
            report = json.loads(DRY_RUN_REPORT.read_text(encoding="utf-8"))
            if (report.get("chat_format_status") != "passed_all_examples" or
                    report.get("chat_template_available") is not True or
                    report.get("assistant_label_check") is not True or
                    report.get("train_sha256") != config.get("train_sha256") or
                    report.get("validation_sha256") != config.get("validation_sha256") or
                    report.get("max_train_tokens",10**9) > 768 or
                    report.get("max_validation_tokens",10**9) > 768 or
                    report.get("full_model_loaded") is not False):
                errors.append("Experiment D real-tokenizer dry run did not pass")
        except (OSError,ValueError,KeyError,json.JSONDecodeError) as error:
            errors.append(f"Experiment D dry-run report missing or invalid: {error}")
        versions = {}
        for package in ("torch","transformers","datasets","peft","bitsandbytes","accelerate","trl"):
            try:
                versions[package] = importlib.metadata.version(package)
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
                args = make_training_arguments(config,OUTPUT / "preflight-not-created",False,
                                               torch.cuda.is_bf16_supported(),TrainingArguments)
                if (args.max_steps != -1 or args.num_train_epochs != 1 or
                        args.gradient_accumulation_steps != 8 or args.learning_rate != 0.000075):
                    errors.append("installed TrainingArguments changed planned D settings")
        except Exception as error:
            errors.append(f"PyTorch/Transformers host check failed: {type(error).__name__}: {error}")
    return {"static_checks_passed":static_passed,"host_checks_performed":not local,
            "ready_for_training":not local and not errors,"errors":errors,
            "output_root":str(OUTPUT),"train_sha256":config.get("train_sha256"),
            "validation_sha256":config.get("validation_sha256")}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--local",action="store_true",help="Static checks only; no tokenizer/model/GPU")
    args = parser.parse_args()
    report = check(local=args.local)
    print(json.dumps(report,indent=2))
    return 0 if not report["errors"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
