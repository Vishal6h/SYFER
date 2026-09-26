#!/usr/bin/env python3
"""Versioned D1 benchmark scorer and read-only contamination audit.

This module never calls a model. All executable answers run in temporary
directories with a deliberately small set of safe Python builtins.
"""

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
TASKS = Path(__file__).with_name("tasks.json")
VERSION = "syfer-d-dev-validator-v2"
CATEGORIES = ("Simple coding", "Bug fixing", "Code explanation", "Patch generation",
              "Multi-step debugging", "Tool-call formatting", "Test-driven fixing",
              "Small repository reasoning")
MODES = {"Simple coding": "python_code", "Bug fixing": "python_code",
         "Code explanation": "explanation_json", "Patch generation": "unified_diff",
         "Multi-step debugging": "python_code", "Tool-call formatting": "tool_call_json",
         "Test-driven fixing": "python_code",
         "Small repository reasoning": "repository_reasoning_json"}
EARLIER = (
    ROOT / "benchmark/tasks.json",
    ROOT / "benchmark/final_holdout/tasks.json",
    ROOT / "benchmark/experiment_c_dev/tasks.json",
    ROOT / "dataset/syfer_train.jsonl",
    ROOT / "dataset/syfer_validation.jsonl",
    ROOT / "dataset/experiment_b_train.jsonl",
    ROOT / "dataset/experiment_b_validation.jsonl",
    ROOT / "dataset/experiment_c_train.jsonl",
    ROOT / "dataset/experiment_c_validation.jsonl",
)


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalized(value):
    return " ".join(re.findall(r"[a-z0-9]+", value.casefold()))


def same_type_value(actual, expected):
    if type(actual) is not type(expected):
        return False
    if isinstance(expected, dict):
        return set(actual) == set(expected) and all(
            same_type_value(actual[key], value) for key, value in expected.items())
    if isinstance(expected, list):
        return len(actual) == len(expected) and all(
            same_type_value(left, right) for left, right in zip(actual, expected))
    return actual == expected


def no_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def parse_json(raw):
    if "```" in raw:
        raise ValueError("JSON response must not use Markdown fences")
    return json.loads(raw, object_pairs_hook=no_duplicate_keys)


FORBIDDEN_NAMES = {"open", "exec", "eval", "compile", "__import__", "input", "breakpoint"}


def check_code_shape(raw):
    if "```" in raw:
        raise ValueError("Python response must be raw code, without Markdown fences")
    tree = ast.parse(raw)
    if not tree.body or any(not isinstance(node, ast.FunctionDef) for node in tree.body):
        raise ValueError("Python response must contain only complete function definitions")
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom, ast.Global, ast.Nonlocal)):
            raise ValueError("imports and global/nonlocal declarations are not allowed")
        if isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            raise ValueError("dunder attributes are not allowed")
        if isinstance(node, ast.Name) and node.id in FORBIDDEN_NAMES:
            raise ValueError("file/process access is not allowed")
    return tree


CODE_HARNESS = r'''
import json, sys
payload = json.load(sys.stdin)
allowed = {name: getattr(__builtins__, name) for name in (
    "abs", "all", "any", "bool", "chr", "dict", "enumerate", "filter",
    "float", "int", "iter", "next", "ord", "len", "list", "map", "max",
    "min", "range", "reversed", "round", "set", "sorted", "str", "sum",
    "tuple", "zip", "ValueError", "TypeError")}
scope = {"__builtins__": allowed}
exec(compile(payload["code"], "<candidate>", "exec"), scope)
def same_type_value(actual, expected):
    if type(actual) is not type(expected):
        return False
    if isinstance(expected, dict):
        return set(actual) == set(expected) and all(
            same_type_value(actual[key], value) for key, value in expected.items())
    if isinstance(expected, list):
        return len(actual) == len(expected) and all(
            same_type_value(left, right) for left, right in zip(actual, expected))
    return actual == expected
failures = []
for number, case in enumerate(payload["cases"], 1):
    try:
        before = json.loads(json.dumps(case["args"]))
        actual = scope[case["function"]](*case["args"])
        if not same_type_value(actual, case["expected"]):
            failures.append({"case": number, "expected": case["expected"], "actual": actual})
        if case.get("unchanged_args") and case["args"] != before:
            failures.append({"case": number, "error": "input arguments were mutated"})
    except Exception as error:
        failures.append({"case": number, "error": type(error).__name__ + ": " + str(error)})
print(json.dumps({"passed": not failures, "failures": failures}, default=repr))
'''


def validate_python(raw, cases):
    check_code_shape(raw)
    with tempfile.TemporaryDirectory(prefix="syfer-d-code-") as temporary:
        result = subprocess.run([sys.executable, "-I", "-B", "-c", CODE_HARNESS],
                                input=json.dumps({"code": raw, "cases": cases}),
                                text=True, capture_output=True, cwd=temporary, timeout=5,
                                check=False)
    if result.returncode:
        return False, (result.stderr or result.stdout).strip()[-600:]
    report = json.loads(result.stdout)
    return report["passed"], report["failures"]


HUNK = re.compile(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(?:.*)")


def apply_unified_diff(source, raw, path):
    """Apply one-file unified diff while preserving content whitespace.

    CRLF transport and one extra terminal empty line are tolerated. Whitespace
    *inside* context, deletion and addition lines is never stripped.
    """
    if "```" in raw:
        raise ValueError("diff response must be raw, without Markdown fences")
    if "\r\n" in raw:
        raw = raw.replace("\r\n", "\n")
    if raw.endswith("\n\n"):
        raw = raw[:-1]
    lines = raw.splitlines(keepends=True)
    if len(lines) < 4 or lines[0] != f"--- a/{path}\n" or lines[1] != f"+++ b/{path}\n":
        raise ValueError("diff needs exact single-file ---/+++ headers")
    # Standard no-final-newline markers apply to the preceding hunk line.
    prepared = lines[:2]
    for line in lines[2:]:
        if line.rstrip("\n") == "\\ No newline at end of file":
            if len(prepared) <= 2 or not prepared[-1].startswith((" ", "-", "+")):
                raise ValueError("orphan no-final-newline marker")
            prepared[-1] = prepared[-1].removesuffix("\n")
        else:
            prepared.append(line)
    old = source.splitlines(keepends=True)
    new = []
    old_pos = 0
    index = 2
    hunks = 0
    while index < len(prepared):
        header = HUNK.fullmatch(prepared[index].rstrip("\n"))
        if not header:
            raise ValueError("invalid hunk header")
        old_start = int(header.group(1))
        old_count = int(header.group(2) or "1")
        new_start = int(header.group(3))
        new_count = int(header.group(4) or "1")
        old_target = old_start if old_count == 0 else old_start - 1
        if old_start < 0 or (old_start == 0 and old_count != 0) or old_target < old_pos or old_target > len(old):
            raise ValueError("old hunk position does not match source")
        new.extend(old[old_pos:old_target])
        old_pos = old_target
        expected_new_start = len(new) if new_count == 0 else len(new) + 1
        if new_start != expected_new_start:
            raise ValueError("new hunk position does not match output")
        index += 1
        consumed = produced = 0
        while index < len(prepared) and not prepared[index].startswith("@@ "):
            line = prepared[index]
            if not line or line[0] not in " +-":
                raise ValueError("invalid diff line")
            content = line[1:]
            if line[0] in " -":
                if old_pos >= len(old) or old[old_pos] != content:
                    raise ValueError("diff context/deletion does not match source")
                old_pos += 1
                consumed += 1
            if line[0] in " +":
                new.append(content)
                produced += 1
            index += 1
        if (consumed, produced) != (old_count, new_count):
            raise ValueError("hunk line counts do not match")
        hunks += 1
    if not hunks:
        raise ValueError("diff has no hunks")
    new.extend(old[old_pos:])
    return "".join(new)


def function_source(source, name):
    tree = ast.parse(source)
    matches = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == name]
    if len(matches) != 1:
        raise ValueError(f"preserved function missing or ambiguous: {name}")
    return ast.get_source_segment(source, matches[0])


def run_oracle(task):
    """Execute trusted authored examples, not generated model code."""
    with tempfile.TemporaryDirectory(prefix="syfer-d-oracle-") as temporary:
        directory = Path(temporary)
        if task["response_mode"] == "explanation_json":
            (directory / "snippet.py").write_text(task["snippet"] + "\n", encoding="utf-8")
            command = [sys.executable, "-I", "-B", "snippet.py"]
        else:
            for name, content in task["files"].items():
                if Path(name).name != name or not name.endswith(".py"):
                    raise ValueError("unsafe virtual file name")
                (directory / name).write_text(content, encoding="utf-8")
            command = [sys.executable, "-B", task["entry"]]
        result = subprocess.run(command, cwd=directory, text=True, capture_output=True,
                                timeout=5, check=False)
    if result.returncode:
        raise ValueError(f"oracle failed: {result.stderr.strip()[-300:]}")
    output = json.loads(result.stdout.strip())
    return output


def validate_response(task, raw):
    """Return (passed, detail) for one D1 response. No model is queried."""
    mode = task["response_mode"]
    if mode == "python_code":
        return validate_python(raw, task["cases"])
    if mode == "unified_diff":
        patched = apply_unified_diff(task["source"], raw, task["path"])
        for name in task.get("preserve_functions", []):
            if function_source(task["source"], name) != function_source(patched, name):
                return False, f"unrelated function changed: {name}"
        return validate_python(patched, task["cases"])
    if mode in {"exact_json", "tool_call_json", "explanation_json", "repository_reasoning_json"}:
        parsed = parse_json(raw)
        expected = task["expected"]
        passed = same_type_value(parsed, expected)
        return passed, "exact parsed schema and values" if passed else "JSON schema, type or value differs"
    raise ValueError(f"unsupported response_mode: {mode}")


def earlier_material():
    prompts, vectors, families = [], set(), set()
    for path in EARLIER:
        rows = ([json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
                if path.suffix == ".jsonl" else json.loads(path.read_text(encoding="utf-8")))
        for row in rows:
            if path.suffix == ".jsonl":
                prompt = row["messages"][1]["content"]
                family = row["family"]
                checks = row["checks"]
                output = ([case["expected"] for case in checks["cases"]]
                          if checks["kind"] in {"python", "patch"} else checks["expected"])
            else:
                prompt = row["prompt"]
                family = row["id"]
                output = ([case["expected"] for case in row["cases"]]
                          if "cases" in row else row.get("expected", row.get("expected_fields")))
            prompts.append((path.name, row["category"], prompt))
            families.add(normalized(family))
            vectors.add(json.dumps(output, sort_keys=True, separators=(",", ":")))
    return prompts, vectors, families


def audit_contamination(tasks):
    prompts, vectors, families = earlier_material()
    exact = {prompt for _, _, prompt in prompts}
    normalized_old = {normalized(prompt) for _, _, prompt in prompts}
    counts = collections.Counter()
    errors = []
    closest = []
    for task in tasks:
        prompt = task["prompt"]
        norm = normalized(prompt)
        if prompt in exact:
            counts["exact_prompt"] += 1
            errors.append(f"{task['id']}: exact older prompt")
        if norm in normalized_old:
            counts["normalized_prompt"] += 1
            errors.append(f"{task['id']}: normalized older prompt")
        output = ([case["expected"] for case in task["cases"]]
                  if task["response_mode"] in {"python_code", "unified_diff"} else task["expected"])
        if json.dumps(output, sort_keys=True, separators=(",", ":")) in vectors:
            counts["expected_output_vector"] += 1
            errors.append(f"{task['id']}: older complete output vector")
        if normalized(task["id"].removeprefix("ddev_")) in families:
            counts["family_name"] += 1
            errors.append(f"{task['id']}: older family name")
        candidates = []
        for source, category, older in prompts:
            if category != task["category"]:
                continue
            other = normalized(older)
            ratio = difflib.SequenceMatcher(None, norm, other, autojunk=False).ratio()
            left, right = set(norm.split()), set(other.split())
            overlap = len(left & right) / len(left | right)
            candidates.append((ratio, overlap, source))
            if ratio >= 0.82 and overlap >= 0.68:
                counts["suspicious_similarity"] += 1
                errors.append(f"{task['id']}: suspicious similarity to {source}: {ratio:.2f}/{overlap:.2f}")
        if candidates:
            ratio, overlap, source = max(candidates)
            closest.append({"task": task["id"], "source": source,
                            "text_similarity": round(ratio, 3), "token_overlap": round(overlap, 3)})
    return ({name: counts[name] for name in ("exact_prompt", "normalized_prompt",
                                         "expected_output_vector", "family_name",
                                         "suspicious_similarity")}, closest, errors)


def validate_benchmark():
    tasks = json.loads(TASKS.read_text(encoding="utf-8"))
    errors = []
    categories = collections.Counter(task["category"] for task in tasks)
    if len(tasks) != 32 or categories != {category: 4 for category in CATEGORIES}:
        errors.append("expected exactly four tasks per category")
    if len({task["id"] for task in tasks}) != len(tasks):
        errors.append("duplicate task IDs")
    if len({normalized(task["prompt"]) for task in tasks}) != len(tasks):
        errors.append("duplicate normalized prompts")
    validated = 0
    for task in tasks:
        try:
            if task["response_mode"] != MODES[task["category"]]:
                raise ValueError("category/mode mismatch")
            if not task["prompt"].strip() or not task["reference"].strip():
                raise ValueError("empty prompt or reference")
            if "```" in task["reference"]:
                raise ValueError("reference contains Markdown fence")
            passed, detail = validate_response(task, task["reference"])
            if not passed:
                raise ValueError(f"reference failed: {detail}")
            if task["response_mode"] in {"explanation_json", "repository_reasoning_json"}:
                if set(task["expected"]) != {"output", "reason"}:
                    raise ValueError("reason-tag schema mismatch")
                if task["expected"]["reason"] not in task["prompt"]:
                    raise ValueError("reason tag is not explicit in prompt")
                if not same_type_value(run_oracle(task), task["expected"]["output"]):
                    raise ValueError("reference output differs from executable oracle")
            if task["response_mode"] == "tool_call_json":
                if set(task["expected"]) != {"tool", "arguments"} or not isinstance(task["expected"]["arguments"], dict):
                    raise ValueError("tool schema mismatch")
                if task["expected"]["tool"] not in task["prompt"]:
                    raise ValueError("tool name not stated in prompt")
            validated += 1
        except Exception as error:
            errors.append(f"{task.get('id')}: {type(error).__name__}: {error}")
    contamination, closest, contamination_errors = audit_contamination(tasks)
    errors.extend(contamination_errors)
    return {"task_count": len(tasks), "category_counts": dict(sorted(categories.items())),
            "validated_references": validated, "contamination": contamination,
            "closest_prior_prompts": closest, "tasks_sha256": sha256(TASKS),
            "validator_version": VERSION, "errors": errors, "error_count": len(errors)}


def main():
    report = validate_benchmark()
    print(json.dumps(report, indent=2))
    return 0 if not report["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
