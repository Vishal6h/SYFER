#!/usr/bin/env python3
"""Validate C development tasks and audit against every earlier task set."""

import collections
import difflib
import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TASKS = Path(__file__).resolve().parent / "tasks.json"
sys.path.insert(0, str(ROOT / "benchmark"))
from final_holdout import validate_holdout as core  # noqa: E402


EARLIER = (*core.EARLIER, ROOT / "benchmark/final_holdout/tasks.json")
PRIOR_HASHES = {
    "benchmark/tasks.json": "48bb49ffdba9bb2e76f51251bc2b91407a0d10215c481e67041c6afa6e15bd1a",
    "benchmark/final_holdout/tasks.json": "862cf0dc1a3d11cdff1f1555dce85fe26fdef9fd93548eb34d7b7c5bb75187a9",
    "dataset/syfer_train.jsonl": "64b0a10b0fe0f26e028b289dcbf7b5c98330ace089947671e25479e4c07afd35",
    "dataset/syfer_validation.jsonl": "57b12aa06063abad06cfe9e19564f4488e2d181df8f4df879c059a16aa929f5e",
    "dataset/experiment_b_train.jsonl": "62a87bb6b24ab6233773aa24a09fea9c89b133bc500a003da0c2730aa8c3d497",
    "dataset/experiment_b_validation.jsonl": "5515b5a7b1ad78ae2f27cd38dc900c8bf624988a95701b20db7dcfde1f4bd01b",
}


def earlier_material():
    prompts, vectors, singles, families = [], set(), set(), set()
    for path in EARLIER:
        records = (json.loads(path.read_text(encoding="utf-8")) if path.suffix == ".json" else
                   [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()])
        for record in records:
            if path.suffix == ".jsonl":
                prompt = record["messages"][1]["content"]
                category = record["category"]
                family = record["family"]
                check = record["checks"]
                outputs = ([case["expected"] for case in check["cases"]]
                           if check["kind"] in {"python", "patch"} else [check["expected"]])
            else:
                prompt = record["prompt"]
                category = record["category"]
                family = record["id"]
                outputs = ([case["expected"] for case in record["cases"]]
                           if "cases" in record else [record.get("expected", record.get("expected_fields"))])
            prompts.append((path.name, category, prompt))
            families.add(core.normalized(family))
            vector = outputs if len(outputs) > 1 or "cases" in record or (path.suffix == ".jsonl" and check["kind"] in {"python", "patch"}) else outputs[0]
            vectors.add(json.dumps(vector, sort_keys=True, separators=(",", ":"), ensure_ascii=False))
            singles.update(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
                           for value in outputs)
    return prompts, vectors, singles, families


def audit_contamination(tasks):
    old_prompts, old_vectors, old_singles, old_families = earlier_material()
    exact = {prompt for _, _, prompt in old_prompts}
    normalized = {core.normalized(prompt) for _, _, prompt in old_prompts}
    counts = collections.Counter()
    errors = []
    closest = []
    for task in tasks:
        prompt = task["prompt"]
        norm = core.normalized(prompt)
        if prompt in exact:
            counts["exact_prompt"] += 1
            errors.append(f"{task['id']}: exact earlier prompt")
        if norm in normalized:
            counts["normalized_prompt"] += 1
            errors.append(f"{task['id']}: normalized earlier prompt")
        if core.output_signature(task) in old_vectors:
            counts["expected_output_vector"] += 1
            errors.append(f"{task['id']}: complete expected-output vector reused")
        output_values = ([case["expected"] for case in task["cases"]]
                         if task["kind"] in {"python", "patch"} else [task["expected"]])
        counts["individual_output_values"] += sum(
            json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) in old_singles
            for value in output_values)
        if core.normalized(task["id"].removeprefix("cdev_")) in old_families:
            counts["family_name"] += 1
            errors.append(f"{task['id']}: earlier family name reused")
        similarities = []
        for source, category, earlier in old_prompts:
            if category != task["category"]:
                continue
            old_norm = core.normalized(earlier)
            ratio = difflib.SequenceMatcher(None, norm, old_norm, autojunk=False).ratio()
            left, right = set(norm.split()), set(old_norm.split())
            tokens = len(left & right) / len(left | right)
            similarities.append((ratio, tokens, source))
            if ratio >= 0.82 and tokens >= 0.68:
                counts["suspicious_similarity"] += 1
                errors.append(f"{task['id']}: suspicious similarity to {source}: {ratio:.2f}/{tokens:.2f}")
        if similarities:
            ratio, tokens, source = max(similarities)
            closest.append({"task": task["id"], "source": source,
                            "text_similarity": round(ratio, 3), "token_overlap": round(tokens, 3)})
    return counts, closest, errors


def validate():
    tasks = json.loads(TASKS.read_text(encoding="utf-8"))
    errors = []
    for name, expected in PRIOR_HASHES.items():
        if core.sha256(ROOT / name) != expected:
            errors.append(f"earlier material changed: {name}")
    categories = collections.Counter(task["category"] for task in tasks)
    if len(tasks) != 32 or categories != {category: 4 for category in core.CATEGORIES}:
        errors.append("expected 32 tasks, four per category")
    if len({task["id"] for task in tasks}) != len(tasks):
        errors.append("duplicate task IDs")
    if len({core.normalized(task["prompt"]) for task in tasks}) != len(tasks):
        errors.append("duplicate normalized C development prompts")
    validated = 0
    for task in tasks:
        try:
            if not task["prompt"].strip() or not task["reference"].strip():
                raise ValueError("empty prompt or reference")
            passed, detail = core.validate_response(task, task["reference"])
            if not passed:
                raise ValueError(f"reference failed: {detail}")
            if task["category"] in {"Code explanation", "Small repository reasoning"}:
                actual = core.run_oracle(task)
                expected = task["expected"]["output"]
                if actual != expected or type(actual) is not type(expected):
                    raise ValueError(f"oracle produced {actual!r}, expected {expected!r}")
            if task["kind"] == "tool_call" and (set(task["expected"]) != {"tool", "arguments"} or
                                                 not isinstance(task["expected"]["arguments"], dict)):
                raise ValueError("malformed mock tool-call schema")
            validated += 1
        except Exception as error:
            errors.append(f"{task.get('id')}: {type(error).__name__}: {error}")
    counts, closest, contamination_errors = audit_contamination(tasks)
    errors.extend(contamination_errors)
    report = {"task_count": len(tasks), "category_counts": dict(sorted(categories.items())),
              "validated_references": validated,
              "contamination": {name: counts[name] for name in
                                ("exact_prompt", "normalized_prompt", "expected_output_vector",
                                 "family_name", "suspicious_similarity", "individual_output_values")},
              "closest_previous_prompts": closest, "tasks_sha256": core.sha256(TASKS),
              "errors": errors, "error_count": len(errors)}
    return report


def main():
    report = validate()
    print(json.dumps(report, indent=2))
    return 0 if not report["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
