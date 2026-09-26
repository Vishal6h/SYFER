#!/usr/bin/env python3
"""Validate the final holdout and audit it against all earlier task material."""

import ast
import collections
import difflib
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
TASKS = HERE / "tasks.json"
sys.path.insert(0, str(ROOT / "benchmark"))
import run_baseline as baseline  # noqa: E402: import the frozen executable validators.


CATEGORIES = {"Simple coding", "Bug fixing", "Code explanation", "Patch generation",
              "Multi-step debugging", "Tool-call formatting", "Test-driven fixing",
              "Small repository reasoning"}
EARLIER = (ROOT / "dataset/syfer_train.jsonl", ROOT / "dataset/syfer_validation.jsonl",
           ROOT / "dataset/experiment_b_train.jsonl", ROOT / "dataset/experiment_b_validation.jsonl",
           ROOT / "benchmark/tasks.json")
FORBIDDEN_DEVELOPMENT_FUNCTIONS = {"unique_in_order", "last_index", "slug", "sum_amounts",
                                   "build_report"}


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalized(text):
    return " ".join(re.findall(r"[a-z0-9]+", text.casefold()))


def output_signature(task):
    """Compare complete expected-answer vectors, not ubiquitous scalar values."""
    if task["kind"] in {"python", "patch"}:
        value = [case["expected"] for case in task["cases"]]
    else:
        value = task["expected"]
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def same_value_type(actual, expected):
    if type(actual) is not type(expected):
        return False
    if isinstance(expected, dict):
        return set(actual) == set(expected) and all(same_value_type(actual[k], v)
                                                    for k, v in expected.items())
    if isinstance(expected, list):
        return len(actual) == len(expected) and all(same_value_type(a, b)
                                                    for a, b in zip(actual, expected))
    return actual == expected


def validate_response(task, raw):
    """One deterministic scoring function shared by all future model runs."""
    kind = task["kind"]
    if kind == "python":
        return baseline.validate_python(baseline.code_only(raw), task["cases"])
    if kind == "patch":
        patched = baseline.apply_single_file_diff(task["source"], baseline.code_only(raw), task["path"])
        return baseline.validate_python(patched, task["cases"])
    if kind == "tool_call":
        expected = json.dumps(task["expected"], separators=(",", ":"), ensure_ascii=False)
        return raw == expected, "exact minified mock call" if raw == expected else "mock call differs"
    if kind == "json":
        parsed = json.loads(raw.strip())
        passed = same_value_type(parsed, task["expected"])
        return passed, "exact JSON schema and values" if passed else "JSON schema, type, or value differs"
    raise ValueError(f"unknown task kind: {kind}")


def run_oracle(task):
    """Execute authored explanation/repository snippets in isolated directories."""
    with tempfile.TemporaryDirectory(prefix="syfer-holdout-oracle-") as temporary:
        directory = Path(temporary)
        if task["category"] == "Code explanation":
            source = task["prompt"].split("\n\n", 1)[1]
            (directory / "snippet.py").write_text(source + "\n", encoding="utf-8")
            command = [sys.executable, "-I", "-B", "snippet.py"]
        else:
            for name, source in task["files"].items():
                if Path(name).name != name or not name.endswith(".py"):
                    raise ValueError(f"unsafe virtual file name: {name}")
                (directory / name).write_text(source, encoding="utf-8")
            command = [sys.executable, "-B", task["entry"]]
        result = subprocess.run(command, cwd=directory, text=True, capture_output=True,
                                timeout=5, check=False)
    if result.returncode:
        raise ValueError(f"oracle failed: {result.stderr.strip()[-300:]}")
    observed = result.stdout.strip()
    if task["category"] == "Code explanation":
        observed = ast.literal_eval(observed)
        def lists(value):
            return [lists(item) for item in value] if isinstance(value, (list, tuple)) else value
        observed = lists(observed)
    else:
        expected_output = task["expected"]["output"]
        observed = int(observed) if type(expected_output) is int else observed
    return observed


def earlier_material():
    prompts = []
    signatures = set()
    individual_outputs = set()
    families = set()
    for path in EARLIER:
        if path.suffix == ".jsonl":
            entries = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
            for entry in entries:
                prompts.append((path.name, entry["messages"][1]["content"], entry["category"]))
                families.add(normalized(entry["family"]))
                checks = entry["checks"]
                if checks["kind"] in {"python", "patch"}:
                    signatures.add(json.dumps([case["expected"] for case in checks["cases"]],
                                              sort_keys=True, separators=(",", ":"), ensure_ascii=False))
                    individual_outputs.update(json.dumps(case["expected"], sort_keys=True,
                                                         separators=(",", ":"), ensure_ascii=False)
                                              for case in checks["cases"])
                elif "expected" in checks:
                    signatures.add(json.dumps(checks["expected"], sort_keys=True,
                                              separators=(",", ":"), ensure_ascii=False))
                    individual_outputs.add(json.dumps(checks["expected"], sort_keys=True,
                                                      separators=(",", ":"), ensure_ascii=False))
        else:
            for entry in json.loads(path.read_text(encoding="utf-8")):
                prompts.append((path.name, entry["prompt"], entry["category"]))
                families.add(normalized(entry["id"]))
                if "cases" in entry:
                    signatures.add(json.dumps([case["expected"] for case in entry["cases"]],
                                              sort_keys=True, separators=(",", ":"), ensure_ascii=False))
                    individual_outputs.update(json.dumps(case["expected"], sort_keys=True,
                                                         separators=(",", ":"), ensure_ascii=False)
                                              for case in entry["cases"])
                elif "expected_fields" in entry or "expected" in entry:
                    signature = json.dumps(entry.get("expected_fields", entry.get("expected")),
                                           sort_keys=True, separators=(",", ":"), ensure_ascii=False)
                    signatures.add(signature)
                    individual_outputs.add(signature)
    return prompts, signatures, individual_outputs, families


def audit_contamination(tasks):
    old_prompts, old_outputs, old_single_outputs, old_families = earlier_material()
    exact_prompts = {text for _, text, _ in old_prompts}
    normalized_prompts = {normalized(text) for _, text, _ in old_prompts}
    errors = []
    most_similar = []
    ordinary_output_overlap = []
    counts = collections.Counter()
    for task in tasks:
        prompt = task["prompt"]
        norm = normalized(prompt)
        if prompt in exact_prompts:
            counts["exact_prompt_matches"] += 1
            errors.append(f"{task['id']}: exact earlier prompt")
        if norm in normalized_prompts:
            counts["normalized_text_matches"] += 1
            errors.append(f"{task['id']}: normalized earlier prompt")
        if output_signature(task) in old_outputs:
            counts["exact_expected_output_vector_matches"] += 1
            errors.append(f"{task['id']}: full expected-output vector matches earlier material")
        case_outputs = ([case["expected"] for case in task["cases"]]
                        if task["kind"] in {"python", "patch"} else [task["expected"]])
        overlaps = [value for value in case_outputs if json.dumps(value, sort_keys=True,
                    separators=(",", ":"), ensure_ascii=False) in old_single_outputs]
        if overlaps:
            counts["individual_expected_output_matches"] += len(overlaps)
            ordinary_output_overlap.append({"task": task["id"], "matches": overlaps})
        if normalized(task["id"].removeprefix("fh_")) in old_families:
            counts["family_name_matches"] += 1
            errors.append(f"{task['id']}: task family matches earlier material")
        if any(re.search(r"\b" + re.escape(name) + r"\b", prompt) for name in
               FORBIDDEN_DEVELOPMENT_FUNCTIONS):
            counts["known_development_function_matches"] += 1
            errors.append(f"{task['id']}: known development-task function reused")
        matches = []
        for source, earlier, category in old_prompts:
            if category != task["category"]:
                continue
            old_norm = normalized(earlier)
            ratio = difflib.SequenceMatcher(None, norm, old_norm, autojunk=False).ratio()
            left, right = set(norm.split()), set(old_norm.split())
            overlap = len(left & right) / len(left | right)
            matches.append((ratio, overlap, source))
            if ratio >= 0.82 and overlap >= 0.68:
                counts["suspicious_similarity_matches"] += 1
                errors.append(f"{task['id']}: suspicious similarity to {source}: ratio={ratio:.2f}, tokens={overlap:.2f}")
        if matches:
            ratio, overlap, source = max(matches)
            most_similar.append({"task": task["id"], "source": source,
                                 "text_similarity": round(ratio, 3), "token_overlap": round(overlap, 3)})
    return counts, most_similar, ordinary_output_overlap, errors


def validate_holdout():
    tasks = json.loads(TASKS.read_text(encoding="utf-8"))
    errors = []
    distribution = collections.Counter(task["category"] for task in tasks)
    if len(tasks) != 32 or distribution != {category: 4 for category in CATEGORIES}:
        errors.append("expected exactly 32 tasks, four in each category")
    if len({task["id"] for task in tasks}) != len(tasks):
        errors.append("duplicate task IDs")
    if len({normalized(task["prompt"]) for task in tasks}) != len(tasks):
        errors.append("duplicate normalized holdout prompts")
    if len({output_signature(task) for task in tasks}) != len(tasks):
        errors.append("duplicate expected-output vectors within holdout")
    validated_references = 0
    for task in tasks:
        try:
            if not task["prompt"].strip() or not task["reference"].strip():
                raise ValueError("empty prompt or reference")
            passed, detail = validate_response(task, task["reference"])
            if not passed:
                raise ValueError(f"reference failed its own validator: {detail}")
            if task["category"] in {"Code explanation", "Small repository reasoning"}:
                actual = run_oracle(task)
                if actual != task["expected"]["output"] or type(actual) is not type(task["expected"]["output"]):
                    raise ValueError(f"oracle output {actual!r} disagrees with expected output")
            if task["kind"] == "tool_call":
                expected = task["expected"]
                if set(expected) != {"tool", "arguments"} or not isinstance(expected["arguments"], dict):
                    raise ValueError("malformed mock tool-call schema")
            validated_references += 1
        except Exception as error:
            errors.append(f"{task.get('id', '<missing>')}: {type(error).__name__}: {error}")
    contamination_counts, most_similar, ordinary_output_overlap, contamination_errors = audit_contamination(tasks)
    errors.extend(contamination_errors)
    report = {"task_count": len(tasks), "category_counts": dict(sorted(distribution.items())),
              "reference_answers_validated": validated_references,
              "contamination_counts": {key: contamination_counts[key] for key in
                                       ("exact_prompt_matches", "normalized_text_matches",
                                        "exact_expected_output_vector_matches",
                                        "individual_expected_output_matches", "family_name_matches",
                                        "known_development_function_matches", "suspicious_similarity_matches")},
              "individual_output_overlap": ordinary_output_overlap,
              "most_similar_by_task": most_similar, "tasks_sha256": sha256(TASKS),
              "validation_errors": errors, "validation_error_count": len(errors)}
    return report


def main():
    report = validate_holdout()
    print(json.dumps(report, indent=2))
    return 0 if report["validation_error_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
