#!/usr/bin/env python3
"""Reload one saved smoke adapter and make one harmless completion."""

import argparse
import json
from pathlib import Path

from train_qlora import CACHE_DIR, MODEL_ID, MODEL_REVISION, OUTPUT_ROOT, load_config, load_tokenizer


PROMPT = "Answer briefly: what does Python len([1, 2]) return?"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path, help="An existing training/output/smoke-* directory")
    args = parser.parse_args()
    run_dir = args.run_dir.resolve()
    if run_dir.parent != OUTPUT_ROOT or not run_dir.name.startswith("smoke-"):
        parser.error("run_dir must be a smoke directory directly under training/output")
    adapter_dir = run_dir / "adapter"
    if not (adapter_dir / "adapter_config.json").is_file():
        parser.error("saved adapter is missing")
    config = load_config(run_dir / "config.json")
    report = {"run_dir": str(run_dir), "model_id": MODEL_ID,
              "model_revision": MODEL_REVISION, "reload_succeeded": False,
              "inference_succeeded": False}
    try:
        import torch
        from peft import PeftModel
        from transformers import AutoModelForCausalLM, BitsAndBytesConfig

        if not torch.cuda.is_available():
            raise RuntimeError("CUDA is unavailable")
        if torch.cuda.get_device_properties(0).total_memory / 1024 ** 3 < config["min_training_vram_gb"]:
            raise RuntimeError("GPU VRAM is below the smoke-test minimum")
        tokenizer = load_tokenizer(offline=True)
        dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
        quant = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                                  bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=dtype)
        base = AutoModelForCausalLM.from_pretrained(MODEL_ID, revision=MODEL_REVISION,
                                                    quantization_config=quant, dtype=dtype,
                                                    cache_dir=CACHE_DIR,
                                                    device_map={"": torch.cuda.current_device()},
                                                    trust_remote_code=False)
        model = PeftModel.from_pretrained(base, adapter_dir, is_trainable=False)
        model.eval()
        report["reload_succeeded"] = True
        inputs = tokenizer.apply_chat_template([{"role": "user", "content": PROMPT}],
                                               add_generation_prompt=True, tokenize=True,
                                               return_tensors="pt").to("cuda")
        with torch.inference_mode():
            output = model.generate(inputs, max_new_tokens=24, do_sample=False,
                                    pad_token_id=tokenizer.eos_token_id)
        completion = tokenizer.decode(output[0][inputs.shape[-1]:], skip_special_tokens=True).strip()
        if not completion:
            raise RuntimeError("model generated an empty completion")
        report.update({"inference_succeeded": True, "prompt": PROMPT, "completion": completion})
    except Exception as error:
        report["error"] = f"{type(error).__name__}: {error}"
    (run_dir / "reload_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    metrics_path = run_dir / "smoke_metrics.json"
    if metrics_path.exists():
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        metrics["reload_succeeded"] = report["reload_succeeded"]
        metrics["inference_succeeded"] = report["inference_succeeded"]
        metrics_path.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["reload_succeeded"] and report["inference_succeeded"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
