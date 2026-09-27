#!/usr/bin/env python3
"""Replay saved D-dev responses with the frozen scorer; never query a model."""

import collections
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "benchmark/experiment_d_dev"))
import validate_d_dev as scorer

RUNS = {
    "stock": "20260926T193513Z-3fae33e9",
    "experiment_b": "20260926T193905Z-ac78ed09",
    "experiment_c": "20260926T194313Z-57e70711",
    "experiment_d": "20260926T194859Z-b37b0aee",
}
BASE = ROOT / "results/experiment_d_dev"
FENCE = re.compile(r"\A\s*```(?:python|json|diff)?\s*\n(.*?)\n```\s*\Z", re.DOTALL)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def score(task, raw):
    try:
        passed, detail = scorer.validate_response(task, raw)
        return {"passed": bool(passed), "detail": detail, "error_type": None}
    except Exception as error:
        return {"passed": False, "detail": str(error), "error_type": type(error).__name__}


def load():
    tasks = json.loads(scorer.TASKS.read_text(encoding="utf-8"))
    by_id = {task["id"]: task for task in tasks}
    runs = {}
    for model, run_id in RUNS.items():
        directory = BASE / model / run_id
        summary = json.loads((directory / "summary.json").read_text(encoding="utf-8"))
        run_config = json.loads((directory / "run_config.json").read_text(encoding="utf-8"))
        status = json.loads((directory / "run_status.json").read_text(encoding="utf-8"))
        snapshot = json.loads((directory / "tasks_snapshot.json").read_text(encoding="utf-8"))
        if snapshot != tasks:
            raise ValueError(f"{model}: task snapshot differs from frozen tasks")
        if status != {"status": "complete", "completed_tasks": 32}:
            raise ValueError(f"{model}: run status is not complete")
        if run_config["d_dev_tasks_sha256"] != digest(scorer.TASKS):
            raise ValueError(f"{model}: frozen task hash mismatch")
        if run_config["d_dev_validator_sha256"] != digest(Path(scorer.__file__)):
            raise ValueError(f"{model}: frozen validator hash mismatch")
        entries = {}
        for task in tasks:
            task_id = task["id"]
            raw_file = directory / f"{task_id}.txt"
            result_file = directory / f"{task_id}.result.json"
            raw = raw_file.read_text(encoding="utf-8")
            recorded = json.loads(result_file.read_text(encoding="utf-8"))
            replayed = score(task, raw)
            match = FENCE.fullmatch(raw)
            inner = score(task, match.group(1)) if match else None
            entries[task_id] = {
                "category": task["category"], "response_mode": task["response_mode"],
                "raw_path": str(raw_file.relative_to(ROOT)), "raw_sha256": digest(raw_file),
                "raw_bytes": len(raw_file.read_bytes()), "raw_preview": raw[:200],
                "recorded": recorded, "replayed": replayed,
                "recorded_match": recorded["passed"] == replayed["passed"],
                "fenced": match is not None, "unfenced_diagnostic": inner,
            }
        if len(entries) != 32 or len(list(directory.glob("*.txt"))) != 32 or len(list(directory.glob("*.result.json"))) != 32:
            raise ValueError(f"{model}: missing or unexpected per-task files")
        if sum(entry["recorded"]["passed"] for entry in entries.values()) != summary["passed"]:
            raise ValueError(f"{model}: summary score differs from per-task results")
        runs[model] = {"run_id": run_id, "directory": str(directory.relative_to(ROOT)),
                       "summary": summary, "run_config": run_config, "status": status,
                       "tasks": entries}
    return tasks, runs


if __name__ == "__main__":
    tasks, runs = load()
    for model, run in runs.items():
        entries = run["tasks"]
        print(model, "score", run["summary"]["passed"],
              "replayed", sum(item["replayed"]["passed"] for item in entries.values()),
              "mismatches", sum(not item["recorded_match"] for item in entries.values()),
              "fenced", sum(item["fenced"] for item in entries.values()),
              "pass_if_unfenced", sum(bool(item["unfenced_diagnostic"] and
                                           item["unfenced_diagnostic"]["passed"])
                                      for item in entries.values()))
        print("categories", dict(collections.Counter(item["category"] for item in entries.values()
                                                     if item["replayed"]["passed"])))
        if model in {"stock", "experiment_c"}:
            for task in tasks:
                item = entries[task["id"]]
                print(task["id"], "fenced", item["fenced"],
                      "inner_pass", item["unfenced_diagnostic"]["passed"] if item["unfenced_diagnostic"] else None,
                      "raw_error", item["replayed"]["detail"],
                      "inner_error", item["unfenced_diagnostic"]["detail"] if item["unfenced_diagnostic"] else None)
