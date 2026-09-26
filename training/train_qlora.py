#!/usr/bin/env python3
"""Explicit, adapter-only QLoRA experiments for SYFER. No training runs by default."""

import argparse
import datetime as dt
import hashlib
import importlib.metadata
import json
import math
import sys
import time
import uuid
from collections.abc import Mapping
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
MODEL_ID = "Qwen/Qwen2.5-Coder-3B-Instruct"
MODEL_REVISION = "89fe5444e8baf5736e70f528f1edcc79e6616ef6"
EXPECTED_TRAIN = ROOT / "dataset" / "syfer_train.jsonl"
EXPECTED_VALIDATION = ROOT / "dataset" / "syfer_validation.jsonl"
OUTPUT_ROOT = HERE / "output"
CACHE_DIR = HERE / "cache"


def inside_root(name):
    path = (ROOT / name).resolve()
    if not path.is_relative_to(ROOT):
        raise ValueError(f"path escapes SYFER: {name}")
    return path


def require(condition, message):
    if not condition:
        raise ValueError(message)


def load_config(path):
    config = json.loads(path.read_text(encoding="utf-8"))
    require(config["model_id"] == MODEL_ID, "model_id must be the upstream instruction model")
    require(config["model_revision"] == MODEL_REVISION, "model_revision must be the verified upstream commit")
    require(inside_root(config["train_file"]) == EXPECTED_TRAIN, "train_file must be the frozen Stage 2 train split")
    require(inside_root(config["validation_file"]) == EXPECTED_VALIDATION, "validation_file must be the frozen Stage 2 validation split")
    require(inside_root(config["output_root"]) == OUTPUT_ROOT, "output_root must be training/output")
    require(256 <= config["max_sequence_length"] <= 2048, "max_sequence_length must be 256–2048")
    require(isinstance(config["seed"], int), "seed must be an integer")
    require(config["min_training_vram_gb"] >= 12, "minimum training VRAM must remain at least 12 GB")
    quant = config["quantization"]
    require(quant == {"load_in_4bit": True, "quant_type": "nf4", "double_quant": True,
                      "compute_dtype": "auto"}, "quantization must use 4-bit NF4 with double quantization")
    lora = config["lora"]
    require(lora["rank"] in (8, 16), "LoRA rank must be 8 or 16")
    require(lora["alpha"] in (16, 32), "LoRA alpha must be 16 or 32")
    require(0 <= lora["dropout"] <= 0.1, "LoRA dropout must be 0–0.1")
    require(lora["target_modules"] == "all-linear" and lora["bias"] == "none",
            "this plan targets all linear layers and no bias weights")
    train = config["training"]
    require(train["epochs"] in (1, 2, 3), "epochs must be 1–3")
    require(0 < train["learning_rate"] <= 0.0002, "learning rate must be at most 2e-4")
    require(train["per_device_batch_size"] == 1, "per-device batch size must be 1")
    require(1 <= train["gradient_accumulation_steps"] <= 16, "gradient accumulation must be 1–16")
    require(train["gradient_checkpointing"] is True, "gradient checkpointing must be enabled")
    require(0 <= train["warmup_ratio"] <= 0.2, "warmup_ratio must be 0–0.2")
    require(train["weight_decay"] >= 0 and train["logging_steps"] >= 1 and train["max_grad_norm"] > 0,
            "invalid optimizer/logging settings")
    return config


def require_experiment_a(config):
    """Refuse a full run if the first experiment's planned settings drift."""
    require(config["seed"] == 42 and config["max_sequence_length"] == 768,
            "Experiment A seed or sequence limit changed")
    require(config["lora"] == {"rank": 8, "alpha": 16, "dropout": 0.05,
                               "target_modules": "all-linear", "bias": "none"},
            "Experiment A LoRA settings changed")
    require(config["training"] == {"epochs": 1, "learning_rate": 0.0001,
                                   "per_device_batch_size": 1, "gradient_accumulation_steps": 8,
                                   "gradient_checkpointing": True, "warmup_ratio": 0.05,
                                   "weight_decay": 0.0, "logging_steps": 1,
                                   "max_grad_norm": 1.0},
            "Experiment A training settings changed")


def load_messages(path):
    records = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        record = json.loads(line)
        messages = record["messages"]
        if [item["role"] for item in messages] != ["system", "user", "assistant"]:
            raise ValueError(f"{path.name}:{number}: expected system/user/assistant roles")
        if any(not item["content"].strip() for item in messages):
            raise ValueError(f"{path.name}:{number}: empty message")
        records.append(messages)
    require(records, f"{path.name} is empty")
    return records


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_tokenizer(offline):
    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, revision=MODEL_REVISION,
                                              cache_dir=CACHE_DIR, local_files_only=offline,
                                              trust_remote_code=False)
    require(tokenizer.chat_template, "Qwen tokenizer has no chat template")
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"
    return tokenizer


def normalize_token_ids(encoded):
    """Accept a chat-template encoding for one conversation, then validate its IDs."""
    if isinstance(encoded, Mapping):
        require("input_ids" in encoded, "chat template encoding has no input_ids")
        encoded = encoded["input_ids"]
    require(isinstance(encoded, (list, tuple)), "chat template must return token IDs")
    if len(encoded) == 1 and isinstance(encoded[0], (list, tuple)):
        encoded = encoded[0]
    require(bool(encoded) and all(type(token_id) is int and token_id >= 0 for token_id in encoded),
            "chat template input_ids must be a nonempty sequence of nonnegative integers")
    return list(encoded)


def format_example(tokenizer, messages, max_length):
    """Mask system/user tokens so loss applies only to the assistant answer."""
    prompt_ids = normalize_token_ids(tokenizer.apply_chat_template(
        messages[:2], tokenize=True, add_generation_prompt=True))
    full_ids = normalize_token_ids(tokenizer.apply_chat_template(
        messages, tokenize=True, add_generation_prompt=False))
    require(full_ids[:len(prompt_ids)] == prompt_ids, "assistant transcript does not share the prompt prefix")
    require(len(full_ids) <= max_length, f"formatted example has {len(full_ids)} tokens, above limit {max_length}")
    require(len(full_ids) > len(prompt_ids), "assistant answer has no tokens")
    labels = [-100] * len(prompt_ids) + full_ids[len(prompt_ids):]
    return {"input_ids": full_ids, "attention_mask": [1] * len(full_ids), "labels": labels}


def format_split(tokenizer, messages, max_length):
    return [format_example(tokenizer, row, max_length) for row in messages]


def report_paths(config, train_path, validation_path):
    return {"model_id": config["model_id"], "model_revision": config["model_revision"],
            "train_file": str(train_path),
            "validation_file": str(validation_path), "output_root": str(OUTPUT_ROOT),
            "output_root_exists": OUTPUT_ROOT.exists(), "train_sha256": sha256(train_path),
            "validation_sha256": sha256(validation_path)}


def require_completed_dry_run():
    path = HERE / "dry_run_report.json"
    require(path.is_file(), "run the real-tokenizer dry run before training")
    report = json.loads(path.read_text(encoding="utf-8"))
    require(report.get("chat_format_status") == "passed_all_examples", "real-tokenizer dry run has not passed")
    require(report.get("assistant_label_check") is True, "assistant masking check has not passed")
    require(report.get("train_sha256") == sha256(EXPECTED_TRAIN), "train split changed after dry run")
    require(report.get("validation_sha256") == sha256(EXPECTED_VALIDATION),
            "validation split changed after dry run")


def dry_run(config, train_messages, validation_messages, offline=False):
    report = report_paths(config, EXPECTED_TRAIN, EXPECTED_VALIDATION)
    report.update({"mode": "dry-run", "train_examples": len(train_messages),
                   "validation_examples": len(validation_messages), "full_model_loaded": False})
    try:
        tokenizer = load_tokenizer(offline=offline)
        train_items = format_split(tokenizer, train_messages, config["max_sequence_length"])
        validation_items = format_split(tokenizer, validation_messages, config["max_sequence_length"])
        report.update({"tokenizer_status": "loaded_from_local_cache" if offline else "loaded_or_downloaded",
                       "chat_template_available": bool(tokenizer.chat_template),
                       "chat_format_status": "passed_all_examples",
                       "max_train_tokens": max(len(item["input_ids"]) for item in train_items),
                       "max_validation_tokens": max(len(item["input_ids"]) for item in validation_items),
                       "assistant_label_check": all(any(label != -100 for label in item["labels"])
                                                    for item in train_items + validation_items)})
        code = 0
    except Exception as error:
        report.update({"tokenizer_status": "unavailable", "chat_format_status": "deferred",
                       "detail": f"{type(error).__name__}: {error}"})
        code = 2
    (HERE / "dry_run_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return code


def check_gpu(torch, config):
    require(torch.cuda.is_available(), "CUDA PyTorch is required for QLoRA training")
    total_gib = torch.cuda.get_device_properties(0).total_memory / 1024 ** 3
    require(total_gib >= config["min_training_vram_gb"],
            f"GPU has {total_gib:.1f} GiB; this plan requires at least {config['min_training_vram_gb']} GiB")
    return total_gib


def create_run_dir(mode):
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    identifier = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    path = OUTPUT_ROOT / f"{mode}-{identifier}"
    path.mkdir(exist_ok=False)
    return path


def make_training_arguments(config, run_dir, smoke, bf16, TrainingArguments):
    """Build Trainer settings without loading a model or starting training."""
    settings = config["training"]
    # Transformers 5 interprets a float warmup_steps below 1 as a ratio of total steps.
    return TrainingArguments(
        output_dir=str(run_dir),
        num_train_epochs=1 if smoke else settings["epochs"], max_steps=1 if smoke else -1,
        per_device_train_batch_size=settings["per_device_batch_size"], per_device_eval_batch_size=1,
        gradient_accumulation_steps=1 if smoke else settings["gradient_accumulation_steps"],
        learning_rate=settings["learning_rate"], warmup_steps=settings["warmup_ratio"],
        weight_decay=settings["weight_decay"], max_grad_norm=settings["max_grad_norm"],
        bf16=bf16, fp16=not bf16,
        logging_strategy="steps", logging_steps=settings["logging_steps"], logging_first_step=True,
        eval_strategy="no" if smoke else "epoch", save_strategy="no", report_to="none", optim="adamw_torch",
        remove_unused_columns=False, dataloader_pin_memory=False, seed=config["seed"],
    )


def train(config, train_messages, validation_messages, smoke):
    import torch
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    from torch.utils.data import Dataset
    from transformers import (AutoModelForCausalLM, BitsAndBytesConfig, Trainer,
                              TrainerCallback, TrainingArguments, set_seed)

    vram_gib = check_gpu(torch, config)  # Guard before tokenizer or model downloads.
    started = time.monotonic()
    torch.cuda.reset_peak_memory_stats()
    set_seed(config["seed"])
    tokenizer = load_tokenizer(offline=False)
    if smoke:
        train_messages, validation_messages = train_messages[:2], validation_messages[:2]
    train_items = format_split(tokenizer, train_messages, config["max_sequence_length"])
    validation_items = format_split(tokenizer, validation_messages, config["max_sequence_length"])
    run_dir = create_run_dir("smoke" if smoke else "experiment")
    (run_dir / "config.json").write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    settings = config["training"]
    effective_batch_size = (settings["per_device_batch_size"] *
                            (1 if smoke else settings["gradient_accumulation_steps"]))
    expected_steps = 1 if smoke else math.ceil(len(train_items) / effective_batch_size)
    checkpoint_step = None if smoke else math.ceil(expected_steps / 2)
    manifest = report_paths(config, EXPECTED_TRAIN, EXPECTED_VALIDATION)
    manifest.update({"mode": "smoke-test" if smoke else "train", "gpu_vram_gib": round(vram_gib, 2),
                     "train_examples_used": len(train_items), "validation_examples_used": len(validation_items),
                     "effective_batch_size": effective_batch_size,
                     "expected_optimizer_steps": expected_steps,
                     "adapter_checkpoint_step": checkpoint_step,
                     "requirements": {name: importlib.metadata.version(name) for name in
                                      ("torch", "transformers", "peft", "bitsandbytes", "accelerate", "datasets", "trl")}})
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    status_path = run_dir / "run_status.json"

    def save_status(status, **details):
        status_path.write_text(json.dumps({"status": status, "optimizer_steps": details.pop("optimizer_steps", 0),
                                           **details}, indent=2) + "\n", encoding="utf-8")

    save_status("in_progress", optimizer_steps=0)

    def guarded(stage, operation):
        try:
            return operation()
        except Exception as error:
            failure = {
                "stage": stage, "error": f"{type(error).__name__}: {error}",
                "cuda_oom": isinstance(error, torch.cuda.OutOfMemoryError)
                or "out of memory" in str(error).lower(),
                "runtime_seconds": round(time.monotonic() - started, 3),
                "peak_allocated_vram_gib": round(torch.cuda.max_memory_allocated() / 1024 ** 3, 3),
                "peak_reserved_vram_gib": round(torch.cuda.max_memory_reserved() / 1024 ** 3, 3),
            }
            (run_dir / "failure.json").write_text(json.dumps(failure, indent=2) + "\n", encoding="utf-8")
            save_status("failed", optimizer_steps=0, **failure)
            raise

    dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
    quant = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                              bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=dtype)
    model = guarded("base_load", lambda: AutoModelForCausalLM.from_pretrained(
        MODEL_ID, quantization_config=quant, revision=MODEL_REVISION, cache_dir=CACHE_DIR,
        dtype=dtype, device_map={"": torch.cuda.current_device()}, trust_remote_code=False))
    model.config.use_cache = False
    model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True)
    lora = config["lora"]
    model = get_peft_model(model, LoraConfig(r=lora["rank"], lora_alpha=lora["alpha"],
                                             lora_dropout=lora["dropout"],
                                             target_modules=lora["target_modules"],
                                             bias=lora["bias"], task_type="CAUSAL_LM"))

    class EncodedDataset(Dataset):
        def __init__(self, items):
            self.items = items

        def __len__(self):
            return len(self.items)

        def __getitem__(self, index):
            return self.items[index]

    def collate(features):
        longest = max(len(item["input_ids"]) for item in features)
        pad = tokenizer.pad_token_id
        return {
            "input_ids": torch.tensor([item["input_ids"] + [pad] * (longest - len(item["input_ids"]))
                                       for item in features], dtype=torch.long),
            "attention_mask": torch.tensor([item["attention_mask"] + [0] * (longest - len(item["attention_mask"]))
                                            for item in features], dtype=torch.long),
            "labels": torch.tensor([item["labels"] + [-100] * (longest - len(item["labels"]))
                                    for item in features], dtype=torch.long),
        }

    args = make_training_arguments(config, run_dir, smoke, dtype == torch.bfloat16, TrainingArguments)
    trainer = Trainer(model=model, args=args, train_dataset=EncodedDataset(train_items),
                      eval_dataset=EncodedDataset(validation_items), data_collator=collate,
                      processing_class=tokenizer)
    if not smoke:
        class AdapterCheckpoint(TrainerCallback):
            def on_step_end(self, args, state, control, **kwargs):
                if state.global_step == checkpoint_step:
                    model.save_pretrained(run_dir / "adapter-checkpoints" / f"step-{state.global_step:04d}",
                                          safe_serialization=True)
                return control

        trainer.add_callback(AdapterCheckpoint())
    try:
        initial_eval = guarded("initial_validation", trainer.evaluate) if smoke else None
        train_result = guarded("optimizer_step", trainer.train)
        eval_result = guarded("final_validation", trainer.evaluate)
        # save_strategy='no' avoids full checkpoints; PEFT writes adapter weights/config only.
        guarded("adapter_save", lambda: model.save_pretrained(run_dir / "adapter", safe_serialization=True))
        (run_dir / "loss_history.json").write_text(json.dumps({"train": train_result.metrics,
                                                                "initial_validation": initial_eval,
                                                                "validation": eval_result,
                                                                "log_history": trainer.state.log_history}, indent=2) + "\n",
                                                   encoding="utf-8")
        adapter_bytes = sum(path.stat().st_size for path in (run_dir / "adapter").rglob("*") if path.is_file())
        run_metrics = {
            "completed_normally": True,
            "optimizer_steps": trainer.state.global_step,
            "effective_batch_size": effective_batch_size,
            "training_loss": train_result.metrics.get("train_loss"),
            "validation_loss": eval_result.get("eval_loss"),
            "peak_allocated_vram_gib": round(torch.cuda.max_memory_allocated() / 1024 ** 3, 3),
            "peak_reserved_vram_gib": round(torch.cuda.max_memory_reserved() / 1024 ** 3, 3),
            "runtime_seconds": round(time.monotonic() - started, 3),
            "adapter_size_bytes": adapter_bytes,
        }
        if not smoke:
            (run_dir / "experiment_metrics.json").write_text(json.dumps(run_metrics, indent=2) + "\n",
                                                               encoding="utf-8")
        save_status("complete", optimizer_steps=trainer.state.global_step,
                    runtime_seconds=run_metrics["runtime_seconds"])
    except BaseException as error:
        save_status("interrupted" if isinstance(error, KeyboardInterrupt) else "failed",
                    optimizer_steps=trainer.state.global_step,
                    runtime_seconds=round(time.monotonic() - started, 3),
                    error=f"{type(error).__name__}: {error}")
        raise
    if smoke:
        smoke_metrics = {
            "optimizer_steps": trainer.state.global_step,
            "initial_validation_loss": initial_eval.get("eval_loss"),
            "training_loss": train_result.metrics.get("train_loss"),
            "final_validation_loss": eval_result.get("eval_loss"),
            "peak_allocated_vram_gib": round(torch.cuda.max_memory_allocated() / 1024 ** 3, 3),
            "peak_reserved_vram_gib": round(torch.cuda.max_memory_reserved() / 1024 ** 3, 3),
            "runtime_seconds": round(time.monotonic() - started, 3),
            "adapter_size_bytes": adapter_bytes,
            "reload_succeeded": None,
            "inference_succeeded": None,
        }
        (run_dir / "smoke_metrics.json").write_text(json.dumps(smoke_metrics, indent=2) + "\n", encoding="utf-8")
    print(f"Adapter and losses saved to {run_dir}")
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--check-config", action="store_true", help="Validate configuration and JSONL with standard library only")
    modes.add_argument("--dry-run", action="store_true", help="Check cached tokenizer and chat formatting; load no model")
    modes.add_argument("--smoke-test", action="store_true", help="On a suitable cloud GPU, train one optimizer step")
    modes.add_argument("--train", action="store_true", help="On a suitable cloud GPU, run the configured experiment")
    parser.add_argument("--config", type=Path, default=HERE / "config.json")
    parser.add_argument("--offline", action="store_true",
                        help="With --dry-run, use only the project tokenizer cache")
    args = parser.parse_args()
    if args.offline and not args.dry_run:
        parser.error("--offline is only valid with --dry-run")
    try:
        config = load_config(args.config)
        train_messages = load_messages(EXPECTED_TRAIN)
        validation_messages = load_messages(EXPECTED_VALIDATION)
        require(set(tuple(item["content"] for item in row) for row in train_messages).isdisjoint(
                tuple(item["content"] for item in row) for row in validation_messages),
                "train and validation contain an identical conversation")
        if args.check_config:
            print(json.dumps({"config_status": "valid", "train_examples": len(train_messages),
                              "validation_examples": len(validation_messages),
                              **report_paths(config, EXPECTED_TRAIN, EXPECTED_VALIDATION)}, indent=2))
            return 0
        if args.dry_run:
            return dry_run(config, train_messages, validation_messages, offline=args.offline)
        if args.train:
            require_experiment_a(config)
        require_completed_dry_run()
        return train(config, train_messages, validation_messages, smoke=args.smoke_test)
    except (ImportError, OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        parser.exit(2, f"Stage 3 setup check failed: {type(error).__name__}: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
