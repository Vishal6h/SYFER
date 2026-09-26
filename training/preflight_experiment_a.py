#!/usr/bin/env python3
"""Check frozen inputs and, on Lightning, the prerequisites for Experiment A."""

import argparse
import importlib.metadata
import json
import sys
from pathlib import Path

from train_qlora import HERE, ROOT, load_config, require_experiment_a, sha256


EXPECTED_HASHES = {
    "benchmark/tasks.json": "48bb49ffdba9bb2e76f51251bc2b91407a0d10215c481e67041c6afa6e15bd1a",
    "benchmark/run_baseline.py": "17eb4e59df7932de874e494d6e3b12fefdf6fff7cad826a7b0aaf3d9c13adeb0",
    "dataset/syfer_train.jsonl": "64b0a10b0fe0f26e028b289dcbf7b5c98330ace089947671e25479e4c07afd35",
    "dataset/syfer_validation.jsonl": "57b12aa06063abad06cfe9e19564f4488e2d181df8f4df879c059a16aa929f5e",
}
SMOKE_DIR = ROOT / "training/output/smoke-20260926T085611Z-621a49b5"
VERSIONS = {
    "torch": "2.14.0", "torchvision": "0.29.0", "transformers": "5.17.0",
    "peft": "0.21.0", "accelerate": "1.15.0", "bitsandbytes": "0.50.2",
    "datasets": "5.0.1", "trl": "1.14.0",
}


def check(local=False):
    errors = []
    observed_hashes = {}
    for name, expected in EXPECTED_HASHES.items():
        path = ROOT / name
        observed = sha256(path) if path.is_file() else None
        observed_hashes[name] = observed
        if observed != expected:
            errors.append(f"{name}: frozen hash mismatch")
    try:
        config = load_config(HERE / "config.json")
        require_experiment_a(config)
    except (ValueError, KeyError, OSError, json.JSONDecodeError) as error:
        errors.append(f"Experiment A config: {error}")
    stats_path = ROOT / "dataset/stats.json"
    if stats_path.is_file():
        stats = json.loads(stats_path.read_text(encoding="utf-8"))
        if (stats.get("train_examples"), stats.get("validation_examples"),
                stats.get("validation_error_count"), stats.get("duplicate_exact_prompts"),
                stats.get("benchmark_contamination_count")) != (130, 40, 0, 0, 0):
            errors.append("dataset/stats.json does not show a clean 130/40 split")
    else:
        errors.append("dataset/stats.json missing; run dataset validation")
    static_checks_passed = not errors

    if not local:
        report_path = HERE / "dry_run_report.json"
        if report_path.is_file():
            report = json.loads(report_path.read_text(encoding="utf-8"))
            if (report.get("chat_format_status") != "passed_all_examples"
                    or report.get("chat_template_available") is not True
                    or report.get("assistant_label_check") is not True
                    or report.get("train_sha256") != EXPECTED_HASHES["dataset/syfer_train.jsonl"]
                    or report.get("validation_sha256") != EXPECTED_HASHES["dataset/syfer_validation.jsonl"]
                    or report.get("max_train_tokens", 10**9) > 768
                    or report.get("max_validation_tokens", 10**9) > 768):
                errors.append("real-tokenizer dry run has not passed for the frozen dataset")
        else:
            errors.append("dry_run_report.json missing")
        metrics_path = SMOKE_DIR / "smoke_metrics.json"
        reload_path = SMOKE_DIR / "reload_report.json"
        adapter_path = SMOKE_DIR / "adapter/adapter_config.json"
        if metrics_path.is_file() and reload_path.is_file() and adapter_path.is_file():
            metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
            reload = json.loads(reload_path.read_text(encoding="utf-8"))
            if (metrics.get("optimizer_steps") != 1 or reload.get("reload_succeeded") is not True
                    or reload.get("inference_succeeded") is not True):
                errors.append("Stage 4 smoke adapter verification is incomplete")
        else:
            errors.append("Stage 4 smoke adapter, metrics, or reload report missing")
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
                    errors.append(f"expected Lightning T4 with at least 12 GiB, found {gpu.name}")
        except Exception as error:
            errors.append(f"PyTorch GPU check failed: {type(error).__name__}: {error}")
    return {"static_checks_passed": static_checks_passed, "host_checks_performed": not local,
            "ready_for_training": not local and not errors,
            "frozen_hashes": observed_hashes, "errors": errors}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--local", action="store_true", help="Check static inputs only; skip cloud prerequisites")
    args = parser.parse_args()
    report = check(local=args.local)
    print(json.dumps(report, indent=2))
    return 0 if not report["errors"] else 2


if __name__ == "__main__":
    sys.exit(main())
