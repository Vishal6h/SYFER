#!/usr/bin/env python3
"""Validate the combined Experiment B splits without changing Stage 2 files."""

import collections
import hashlib
import json
import re
from pathlib import Path

import validate_dataset as stage2


HERE = Path(__file__).resolve().parent
FILES = (("train", HERE / "experiment_b_train.jsonl", HERE / "syfer_train.jsonl"),
         ("validation", HERE / "experiment_b_validation.jsonl", HERE / "syfer_validation.jsonl"))
NEW_SOURCE = "targeted_experiment_b_v1"


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_jsonl(path):
    rows = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as error:
            raise ValueError(f"{path.name}:{number}: malformed JSON: {error}") from error
    return rows


def validate():
    errors = []
    combined = []
    split_rows = {}
    new_rows = []
    duplicate_count = 0
    contamination_count = 0
    family_splits = collections.defaultdict(set)
    seen_prompts = set()
    exact_texts, banned_functions, banned_paths, banned_symbols, baseline_pairs = stage2.baseline_terms()
    for split, path, original_path in FILES:
        if not path.is_file():
            errors.append(f"missing {path.name}")
            continue
        try:
            rows = read_jsonl(path)
            originals = read_jsonl(original_path)
        except (OSError, ValueError) as error:
            errors.append(str(error))
            continue
        split_rows[split] = rows
        if rows[:len(originals)] != originals:
            errors.append(f"{path.name}: original Stage 2 records were changed or reordered")
        for number, row in enumerate(rows, 1):
            location = f"{path.name}:{number}"
            try:
                stage2.check_record(row)
                user = row["messages"][1]["content"]
                answer = row["messages"][2]["content"]
                if user in seen_prompts:
                    duplicate_count += 1
                    raise ValueError("duplicate exact prompt")
                seen_prompts.add(user)
                if user.strip() in exact_texts or answer.strip() in exact_texts:
                    contamination_count += 1
                    raise ValueError("exact benchmark prompt or stock response reused")
                if any(re.search(r"\bdef\s+" + re.escape(name) + r"\s*\(", user + "\n" + answer)
                       for name in banned_functions):
                    contamination_count += 1
                    raise ValueError("benchmark function definition reused")
                if any(term in user + answer for term in banned_paths | banned_symbols):
                    contamination_count += 1
                    raise ValueError("benchmark path or tool symbol reused")
                for case in row["checks"].get("cases", []):
                    if json.dumps([case["args"], case["expected"]], sort_keys=True) in baseline_pairs:
                        contamination_count += 1
                        raise ValueError("exact benchmark test input/output pair reused")
                family_splits[(row["category"], row["family"])].add(split)
                if number > len(originals):
                    if row["source"] != NEW_SOURCE:
                        raise ValueError("new row has wrong source tag")
                    new_rows.append(row)
                combined.append(row)
            except Exception as error:
                errors.append(f"{location}: {type(error).__name__}: {error}")
    overlap = [f"{category}/{family}" for (category, family), splits in family_splits.items() if len(splits) > 1]
    if overlap:
        errors.append("families cross train and validation: " + ", ".join(overlap))
    if not 60 <= len(new_rows) <= 100:
        errors.append(f"expected 60–100 new examples, found {len(new_rows)}")
    new_categories = collections.Counter(row["category"] for row in new_rows)
    if set(new_categories) != stage2.CATEGORIES:
        errors.append("new examples do not cover all eight requested categories")
    if any(count > 25 for count in new_categories.values()):
        errors.append("one new category exceeds 25 examples")
    stats = {
        "total_examples": len(combined),
        "train_examples": len(split_rows.get("train", [])),
        "validation_examples": len(split_rows.get("validation", [])),
        "new_examples": len(new_rows),
        "new_train_examples": max(0, len(split_rows.get("train", [])) - 130),
        "new_validation_examples": max(0, len(split_rows.get("validation", [])) - 40),
        "category_counts": dict(sorted(collections.Counter(row["category"] for row in combined).items())),
        "new_category_counts": dict(sorted(new_categories.items())),
        "new_difficulty_counts": dict(sorted(collections.Counter(row["difficulty"] for row in new_rows).items())),
        "duplicate_exact_prompts": duplicate_count,
        "benchmark_contamination_count": contamination_count,
        "family_split_overlap": overlap,
        "dataset_hashes": {path.name: sha256(path) for _, path, _ in FILES if path.is_file()},
        "validation_errors": errors,
        "validation_error_count": len(errors),
    }
    (HERE / "experiment_b_stats.json").write_text(json.dumps(stats, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(stats, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(validate())
