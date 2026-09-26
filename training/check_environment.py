#!/usr/bin/env python3
"""Report hardware and package availability without installing anything."""

import argparse
import importlib.metadata
import json
import platform
import subprocess
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
PACKAGES = ("torch", "transformers", "datasets", "peft", "bitsandbytes", "accelerate", "trl")


def memory_gib():
    values = {}
    for line in Path("/proc/meminfo").read_text().splitlines():
        if line.startswith(("MemTotal:", "MemAvailable:", "SwapTotal:")):
            key, number, _ = line.split()
            values[key[:-1].lower() + "_gib"] = round(int(number) / 1024 / 1024, 2)
    return values


def gpu_report():
    command = ["nvidia-smi", "--query-gpu=name,memory.total,memory.free,compute_cap,driver_version",
               "--format=csv,noheader,nounits"]
    try:
        result = subprocess.run(command, text=True, capture_output=True, timeout=10, check=False)
    except (FileNotFoundError, subprocess.TimeoutExpired) as error:
        return {"status": "unavailable", "detail": str(error)}
    if result.returncode:
        return {"status": "unavailable", "detail": (result.stderr or result.stdout).strip()}
    devices = []
    for line in result.stdout.strip().splitlines():
        name, total, free, capability, driver = [part.strip() for part in line.split(",", 4)]
        devices.append({"name": name, "vram_mib": int(total), "free_vram_mib": int(free),
                        "compute_capability": capability, "driver_version": driver})
    return {"status": "ok", "devices": devices}


def torch_report():
    try:
        import torch
    except ImportError:
        return {"status": "not_installed", "cuda_available": None}
    except Exception as error:
        return {"status": "import_error", "detail": str(error), "cuda_available": None}
    result = {"status": "ok", "cuda_available": bool(torch.cuda.is_available()),
              "torch_cuda_version": torch.version.cuda}
    if result["cuda_available"]:
        result["bf16_supported"] = bool(torch.cuda.is_bf16_supported())
        result["gpu_name"] = torch.cuda.get_device_name(0)
    return result


def inspect():
    packages = {}
    for name in PACKAGES:
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = None
    try:
        system_version = Path("/proc/version").read_text()
    except OSError:
        system_version = ""
    return {
        "python_version": platform.python_version(), "python_executable": sys.executable,
        "platform": platform.platform(), "wsl": "microsoft" in system_version.lower(),
        "memory": memory_gib(), "gpu": gpu_report(), "torch_runtime": torch_report(),
        "packages": packages,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=HERE / "environment_report.json")
    args = parser.parse_args()
    report = inspect()
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
