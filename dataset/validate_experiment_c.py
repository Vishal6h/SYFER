#!/usr/bin/env python3
"""Validate all Experiment C records, split families, and benchmark isolation."""

import ast
import collections
import difflib
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
TRAIN = HERE / "experiment_c_train.jsonl"
VALIDATION = HERE / "experiment_c_validation.jsonl"
STATS = HERE / "experiment_c_stats.json"
SOURCE = "experiment_c_authored_v1"
sys.path.insert(0, str(ROOT / "benchmark"))
sys.path.insert(0, str(ROOT / "benchmark/experiment_c_dev"))
from final_holdout import validate_holdout as core  # noqa: E402
import validate_c_dev as c_dev  # noqa: E402


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_jsonl(path):
    records = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as error:
            raise ValueError(f"{path.name}:{number}: malformed JSON: {error}") from error
    return records


def snippet_output(snippet):
    with tempfile.TemporaryDirectory(prefix="syfer-c-explanation-") as temporary:
        result = subprocess.run([sys.executable, "-I", "-B", "-c", snippet], cwd=temporary,
                                text=True, capture_output=True, timeout=5, check=False)
    if result.returncode:
        raise ValueError(f"explanation snippet failed: {result.stderr.strip()[-300:]}")
    return ast.literal_eval(result.stdout.strip())


def check_record(row):
    required = {"messages", "category", "source", "difficulty", "family", "checks"}
    if not isinstance(row, dict) or set(row) != required:
        raise ValueError("record fields differ from the instruction-tuning schema")
    if (row["category"] not in core.CATEGORIES or row["source"] != SOURCE or
            row["difficulty"] not in {"easy", "medium", "hard"} or
            not isinstance(row["family"], str) or not row["family"].strip()):
        raise ValueError("invalid category, source, difficulty, or family")
    messages = row["messages"]
    if (not isinstance(messages, list) or len(messages) != 3 or
            [message.get("role") for message in messages] != ["system", "user", "assistant"] or
            any(not isinstance(message, dict) or set(message) != {"role", "content"} or
                not isinstance(message["content"], str) or not message["content"].strip()
                for message in messages)):
        raise ValueError("expected three nonempty system/user/assistant messages")
    user, answer = messages[1]["content"], messages[2]["content"]
    checks = row["checks"]
    kind = checks.get("kind") if isinstance(checks, dict) else None
    category = row["category"]
    if (category in {"Simple coding", "Bug fixing", "Multi-step debugging", "Test-driven fixing"}
            and kind != "python") or (category == "Patch generation" and kind != "patch") or (
            category in {"Code explanation", "Tool-call formatting", "Small repository reasoning"}
            and kind != "json"):
        raise ValueError("category and validator kind disagree")
    if kind == "python":
        if len(checks["cases"]) < 2:
            raise ValueError("code needs at least two executable cases")
        passed, detail = core.baseline.validate_python(answer, checks["cases"])
        if not passed:
            raise ValueError(f"code failed cases: {detail}")
    elif kind == "patch":
        if not answer.startswith(f"--- a/{checks['path']}\n+++ b/{checks['path']}\n") or "```" in answer:
            raise ValueError("patch needs raw exact file headers without Markdown")
        patched = core.baseline.apply_single_file_diff(checks["source"], answer, checks["path"])
        if patched != checks["expected_source"]:
            raise ValueError("patch does not produce the curated target")
        passed, detail = core.baseline.validate_python(patched, checks["cases"])
        if not passed:
            raise ValueError(f"patched code failed cases: {detail}")
    elif kind == "json":
        parsed = json.loads(answer)
        if not core.same_value_type(parsed, checks["expected"]):
            raise ValueError("JSON schema, type, or value differs from reference")
        if category == "Tool-call formatting":
            if (answer != json.dumps(parsed, separators=(",", ":"), ensure_ascii=False) or
                    set(parsed) != {"tool", "arguments"} or not isinstance(parsed["arguments"], dict)):
                raise ValueError("tool call is malformed or not exactly minified")
        elif category == "Code explanation":
            if set(parsed) != {"output", "explanation"} or not parsed["explanation"].strip():
                raise ValueError("explanation JSON needs output and nonempty explanation")
            actual = snippet_output(checks["snippet"])
            if not core.same_value_type(actual, parsed["output"]):
                raise ValueError("explanation disagrees with executed snippet")
        elif category == "Small repository reasoning":
            if set(parsed) != {"output", "explanation"} or not parsed["explanation"].strip():
                raise ValueError("repository JSON needs output and nonempty explanation")
            actual = core.run_oracle({"category": category, "files": checks["files"],
                                      "entry": checks["entry"], "expected": parsed})
            if not core.same_value_type(actual, parsed["output"]):
                raise ValueError("repository answer disagrees with isolated execution")
    else:
        raise ValueError(f"unknown validator kind: {kind}")


def benchmark_material():
    prompts = []
    vectors = set()
    for path in (ROOT / "benchmark/tasks.json", ROOT / "benchmark/final_holdout/tasks.json",
                 ROOT / "benchmark/experiment_c_dev/tasks.json"):
        for task in json.loads(path.read_text(encoding="utf-8")):
            prompts.append((path.name, task["category"], task["prompt"]))
            if "cases" in task:
                output = [case["expected"] for case in task["cases"]]
            else:
                output = task.get("expected", task.get("expected_fields"))
            vectors.add(json.dumps(output, sort_keys=True, separators=(",", ":"), ensure_ascii=False))
    return prompts, vectors


def earlier_dataset_prompts():
    prompts = []
    for name in ("syfer_train.jsonl", "syfer_validation.jsonl",
                 "experiment_b_train.jsonl", "experiment_b_validation.jsonl"):
        for row in read_jsonl(HERE / name):
            prompts.append(row["messages"][1]["content"])
    return prompts


def validate():
    errors = []
    by_split = {}
    for split, path in (("train", TRAIN), ("validation", VALIDATION)):
        try:
            by_split[split] = read_jsonl(path)
        except (OSError, ValueError) as error:
            by_split[split] = []
            errors.append(str(error))
    rows = by_split["train"] + by_split["validation"]
    seen_prompts = set()
    duplicate_prompts = 0
    families = collections.defaultdict(set)
    benchmark_prompts, benchmark_vectors = benchmark_material()
    prior_dataset = earlier_dataset_prompts()
    dataset_exact = set(prior_dataset)
    dataset_normalized = {core.normalized(prompt) for prompt in prior_dataset}
    exact_benchmark = {prompt for _, _, prompt in benchmark_prompts}
    normalized_benchmark = {core.normalized(prompt) for _, _, prompt in benchmark_prompts}
    exact_matches = normalized_matches = suspicious_matches = vector_matches = 0
    prior_dataset_matches = 0
    validated = 0
    for split, split_rows in by_split.items():
        for number, row in enumerate(split_rows, 1):
            location = f"{split}:{number}"
            try:
                check_record(row)
                prompt = row["messages"][1]["content"]
                if prompt in seen_prompts:
                    duplicate_prompts += 1
                    raise ValueError("duplicate exact prompt")
                seen_prompts.add(prompt)
                families[(row["category"], row["family"])].add(split)
                if prompt in exact_benchmark:
                    exact_matches += 1
                    raise ValueError("exact benchmark prompt reused")
                norm = core.normalized(prompt)
                if prompt in dataset_exact or norm in dataset_normalized:
                    prior_dataset_matches += 1
                    raise ValueError("earlier dataset prompt reused")
                if norm in normalized_benchmark:
                    normalized_matches += 1
                    raise ValueError("normalized benchmark prompt reused")
                checks = row["checks"]
                output = ([case["expected"] for case in checks["cases"]]
                          if checks["kind"] in {"python", "patch"} else checks["expected"])
                signature = json.dumps(output, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
                if signature in benchmark_vectors:
                    vector_matches += 1
                    raise ValueError("complete benchmark expected-output vector reused")
                for source, category, older in benchmark_prompts:
                    if category != row["category"]:
                        continue
                    old_norm = core.normalized(older)
                    ratio = difflib.SequenceMatcher(None, norm, old_norm, autojunk=False).ratio()
                    left, right = set(norm.split()), set(old_norm.split())
                    tokens = len(left & right) / len(left | right)
                    if ratio >= 0.82 and tokens >= 0.68:
                        suspicious_matches += 1
                        raise ValueError(f"suspicious similarity to {source}: {ratio:.2f}/{tokens:.2f}")
                validated += 1
            except Exception as error:
                errors.append(f"{location}: {type(error).__name__}: {error}")
    overlap = [f"{category}/{family}" for (category, family), splits in families.items() if len(splits) > 1]
    if overlap:
        errors.append("train/validation families overlap: " + ", ".join(overlap))
    if len(rows) != 120 or len(by_split["train"]) != 88 or len(by_split["validation"]) != 32:
        errors.append("expected exactly 120 new examples split 88/32")
    categories = collections.Counter(row["category"] for row in rows)
    expected_counts = {"Patch generation": 32, "Tool-call formatting": 24,
                       "Small repository reasoning": 24,
                       "Simple coding": 8, "Bug fixing": 8, "Code explanation": 8,
                       "Multi-step debugging": 8, "Test-driven fixing": 8}
    if categories != expected_counts:
        errors.append("category distribution differs from targeted C design")
    report = {"total_examples": len(rows), "train_examples": len(by_split["train"]),
              "validation_examples": len(by_split["validation"]),
              "validated_examples": validated,
              "category_counts": dict(sorted(categories.items())),
              "difficulty_counts": dict(sorted(collections.Counter(row["difficulty"] for row in rows).items())),
              "duplicate_exact_prompts": duplicate_prompts,
              "family_split_overlap": overlap,
              "earlier_dataset_prompt_matches": prior_dataset_matches,
              "benchmark_contamination": {"exact_prompt": exact_matches,
                                          "normalized_prompt": normalized_matches,
                                          "expected_output_vector": vector_matches,
                                          "suspicious_similarity": suspicious_matches},
              "hashes": {path.name: sha256(path) for path in (TRAIN, VALIDATION) if path.is_file()},
              "validation_errors": errors, "validation_error_count": len(errors)}
    STATS.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main():
    report = validate()
    print(json.dumps(report, indent=2))
    return 0 if report["validation_error_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
