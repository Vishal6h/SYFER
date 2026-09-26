#!/usr/bin/env python3
"""Validate every SYFER Stage 2 record and write dataset/stats.json."""

import ast
import collections
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
FILES = (HERE / "syfer_train.jsonl", HERE / "syfer_validation.jsonl")
CATEGORIES = {
    "Simple coding", "Bug fixing", "Code explanation", "Patch generation",
    "Multi-step debugging", "Tool-call formatting", "Test-driven fixing",
    "Small repository reasoning",
}
DIFFICULTIES = {"easy", "medium", "hard"}
ALLOWED_TOOLS = {"lookup_symbol", "read_doc", "search_notes"}


HARNESS = r'''
import json, sys
payload = json.load(sys.stdin)
names = ("abs", "all", "any", "bool", "dict", "enumerate", "filter", "float",
         "int", "len", "list", "map", "max", "min", "range", "reversed", "round",
         "set", "sorted", "str", "sum", "tuple", "zip")
scope = {"__builtins__": {name: getattr(__builtins__, name) for name in names}}
exec(compile(payload["code"], "<dataset answer>", "exec"), scope)
problems = []
for i, item in enumerate(payload["cases"], 1):
    try:
        args = item["args"]
        before = json.loads(json.dumps(args))
        actual = scope[item["function"]](*args)
        expected = item["expected"]
        if actual != expected or type(actual) is not type(expected):
            problems.append(f"case {i}: expected {expected!r}, got {actual!r}")
        if item.get("unchanged_args") and args != before:
            problems.append(f"case {i}: input arguments changed")
    except Exception as error:
        problems.append(f"case {i}: {type(error).__name__}: {error}")
print(json.dumps(problems))
'''


def check_code_shape(code):
    tree = ast.parse(code)
    if not tree.body or any(not isinstance(node, ast.FunctionDef) for node in tree.body):
        raise ValueError("code must contain only function definitions")
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom, ast.Global, ast.Nonlocal)):
            raise ValueError("imports or global access in answer")
        if isinstance(node, ast.Name) and node.id in {"open", "exec", "eval", "compile", "__import__", "input"}:
            raise ValueError("file or process access in answer")
        if isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            raise ValueError("dunder access in answer")


def check_code(code, cases):
    check_code_shape(code)
    if not isinstance(cases, list) or len(cases) < 2:
        raise ValueError("code answer needs at least two test cases")
    with tempfile.TemporaryDirectory(prefix="syfer-dataset-check-") as temp:
        result = subprocess.run([sys.executable, "-I", "-B", "-c", HARNESS],
                                input=json.dumps({"code": code, "cases": cases}),
                                text=True, capture_output=True, cwd=temp, timeout=5, check=False)
    if result.returncode:
        raise ValueError("code failed to run: " + result.stderr.strip()[-300:])
    problems = json.loads(result.stdout)
    if problems:
        raise ValueError("; ".join(problems))


def apply_full_file_diff(source, diff, path):
    """Validate and apply the full-file unified diff format used in this dataset."""
    lines = diff.splitlines()
    if len(lines) < 4 or lines[:2] != [f"--- a/{path}", f"+++ b/{path}"]:
        raise ValueError("bad unified diff file headers")
    match = re.fullmatch(r"@@ -1,(\d+) \+1,(\d+) @@", lines[2])
    if not match:
        raise ValueError("bad unified diff hunk header")
    old_lines, new_lines = [], []
    for line in lines[3:]:
        if not line or line[0] not in "-+ ":
            raise ValueError("bad unified diff body line")
        if line[0] in "- ":
            old_lines.append(line[1:])
        if line[0] in "+ ":
            new_lines.append(line[1:])
    if len(old_lines) != int(match.group(1)) or len(new_lines) != int(match.group(2)):
        raise ValueError("unified diff hunk count mismatch")
    if old_lines != source.splitlines():
        raise ValueError("unified diff does not match source")
    return "\n".join(new_lines) + "\n"


def check_explanation(user, decoded):
    snippet = user.rsplit("\n\n", 1)[-1]
    with tempfile.TemporaryDirectory(prefix="syfer-explanation-check-") as temp:
        result = subprocess.run([sys.executable, "-I", "-B", "-c", snippet],
                                text=True, capture_output=True, cwd=temp, timeout=5, check=False)
    if result.returncode:
        raise ValueError("explanation snippet failed to run")
    try:
        printed = ast.literal_eval(result.stdout.strip())
    except (ValueError, SyntaxError) as error:
        raise ValueError("explanation snippet printed an unsupported value") from error
    if printed != decoded["output"] or type(printed) is not type(decoded["output"]):
        raise ValueError("explanation output disagrees with executed snippet")


def check_repository(user, decoded):
    files = {}
    functions = {}
    calls = {}
    for line in user.splitlines():
        match = re.match(r"^([\w.-]+\.py):\s*(.*)$", line)
        if not match:
            continue
        path, content = match.groups()
        files[path] = content
        for function in re.findall(r"\bdef\s+([A-Za-z_]\w*)\s*\(", content):
            functions[function] = path
        for caller, callee in re.findall(r"\bdef\s+([A-Za-z_]\w*)\s*\([^)]*\):\s*return\s+([A-Za-z_]\w*)\s*\(", content):
            calls[caller] = callee
    if not files or decoded["file"] not in files:
        raise ValueError("repository answer names a missing file")
    if "function" in decoded:
        if functions.get(decoded["function"]) != decoded["file"]:
            raise ValueError("repository function is not defined in named file")
    else:
        chain = decoded.get("chain")
        start = re.search(r"(?:full|complete) (?:function )?call chain from ([A-Za-z_]\w*)", user)
        if not start or not isinstance(chain, list) or not chain or chain[0] != start.group(1):
            raise ValueError("repository chain does not start at requested entry")
        actual = [chain[0]]
        while actual[-1] in calls and calls[actual[-1]] in functions and len(actual) <= len(functions):
            actual.append(calls[actual[-1]])
        if chain != actual or functions.get(chain[-1]) != decoded["file"]:
            raise ValueError("repository chain or terminal file is incorrect")


def check_record(row):
    required = {"messages", "category", "source", "difficulty", "family", "checks"}
    if not isinstance(row, dict) or set(row) != required:
        raise ValueError("required record fields missing or extra")
    if row["category"] not in CATEGORIES or row["difficulty"] not in DIFFICULTIES:
        raise ValueError("unknown category or difficulty")
    if not isinstance(row["source"], str) or not row["source"].strip():
        raise ValueError("empty source")
    if not isinstance(row["family"], str) or not row["family"].strip():
        raise ValueError("empty family")
    messages = row["messages"]
    if not isinstance(messages, list) or len(messages) != 3:
        raise ValueError("messages must contain exactly system, user, assistant")
    if [message.get("role") for message in messages] != ["system", "user", "assistant"]:
        raise ValueError("invalid message roles or order")
    if any(not isinstance(message, dict) or set(message) != {"role", "content"} or
           not isinstance(message["content"], str) or not message["content"].strip()
           for message in messages):
        raise ValueError("empty or malformed message")
    answer = messages[2]["content"]
    checks = row["checks"]
    if not isinstance(checks, dict) or "kind" not in checks:
        raise ValueError("missing checks")
    kind = checks["kind"]
    if row["category"] in {"Simple coding", "Bug fixing", "Multi-step debugging", "Test-driven fixing"} and kind != "python":
        raise ValueError("coding category needs Python checks")
    if row["category"] == "Patch generation" and kind != "patch":
        raise ValueError("patch category needs patch checks")
    if row["category"] in {"Code explanation", "Tool-call formatting", "Small repository reasoning"} and kind != "json":
        raise ValueError("structured category needs JSON checks")
    if kind == "python":
        check_code(answer, checks["cases"])
    elif kind == "patch":
        patched = apply_full_file_diff(checks["source"], answer, checks["path"])
        if patched != checks["expected_source"]:
            raise ValueError("patch result differs from curated target")
        check_code(patched, checks["cases"])
    elif kind == "json":
        decoded = json.loads(answer)
        if decoded != checks["expected"] or not isinstance(decoded, dict):
            raise ValueError("JSON answer differs from expected fields")
        if row["category"] == "Tool-call formatting":
            if answer != json.dumps(decoded, separators=(",", ":"), ensure_ascii=False):
                raise ValueError("tool JSON is not exactly minified")
            if set(decoded) != {"tool", "arguments"} or decoded["tool"] not in ALLOWED_TOOLS or not isinstance(decoded["arguments"], dict):
                raise ValueError("malformed mock tool call")
        elif row["category"] == "Code explanation":
            if set(decoded) != {"output", "explanation"} or not isinstance(decoded["explanation"], str) or not decoded["explanation"].strip():
                raise ValueError("malformed explanation JSON")
            check_explanation(messages[1]["content"], decoded)
        elif row["category"] == "Small repository reasoning":
            if set(decoded) not in ({"file", "function"}, {"file", "chain"}):
                raise ValueError("malformed repository JSON")
            check_repository(messages[1]["content"], decoded)
    else:
        raise ValueError("unknown check kind")


def baseline_terms():
    tasks = json.loads((ROOT / "benchmark" / "tasks.json").read_text(encoding="utf-8"))
    final_run = max((p for p in (ROOT / "results" / "baseline").iterdir() if p.is_dir()), key=lambda p: p.name)
    exact_texts = {task["prompt"].strip() for task in tasks}
    exact_texts.update((final_run / f"{task['id']}.txt").read_text(encoding="utf-8").strip() for task in tasks)
    function_names = set()
    banned_paths = set()
    banned_symbols = set()
    baseline_case_pairs = set()
    for task in tasks:
        function_names.update(re.findall(r"\bdef\s+([A-Za-z_]\w*)\s*\(", task["prompt"]))
        for test in task.get("cases", []):
            function_names.add(test["function"])
            baseline_case_pairs.add(json.dumps([test["args"], test["expected"]], sort_keys=True))
        if "path" in task:
            banned_paths.add(task["path"])
        if task["kind"] == "tool_call":
            banned_symbols.add(task["expected"]["arguments"]["symbol"])
    return exact_texts, function_names, banned_paths, banned_symbols, baseline_case_pairs


def main():
    errors = []
    rows = []
    rows_by_split = collections.defaultdict(list)
    split_counts = {}
    duplicate_prompts = 0
    seen_prompts = set()
    seen_records = set()
    family_splits = collections.defaultdict(set)
    exact_texts, banned_functions, banned_paths, banned_symbols, baseline_case_pairs = baseline_terms()
    contamination_count = 0
    for path in FILES:
        count = 0
        if not path.exists():
            errors.append(f"missing file: {path.name}")
            continue
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            location = f"{path.name}:{line_number}"
            try:
                row = json.loads(line)
                check_record(row)
                user = row["messages"][1]["content"]
                answer = row["messages"][2]["content"]
                if user in seen_prompts:
                    duplicate_prompts += 1
                    raise ValueError("duplicate exact prompt")
                seen_prompts.add(user)
                fingerprint = (user, answer)
                if fingerprint in seen_records:
                    raise ValueError("duplicate exact example")
                seen_records.add(fingerprint)
                if user.strip() in exact_texts or answer.strip() in exact_texts:
                    contamination_count += 1
                    raise ValueError("exact benchmark prompt/response copied")
                if any(re.search(r"\bdef\s+" + re.escape(name) + r"\s*\(", user + "\n" + answer) for name in banned_functions):
                    contamination_count += 1
                    raise ValueError("benchmark function definition reused")
                if any(term in user + answer for term in banned_paths | banned_symbols):
                    contamination_count += 1
                    raise ValueError("benchmark path or tool symbol reused")
                for test in row["checks"].get("cases", []):
                    if json.dumps([test["args"], test["expected"]], sort_keys=True) in baseline_case_pairs:
                        contamination_count += 1
                        raise ValueError("exact benchmark test input/output pair reused")
                family_splits[(row["category"], row["family"])].add(path.name)
                rows.append(row)
                rows_by_split[path.stem.replace("syfer_", "")].append(row)
                count += 1
            except Exception as error:
                errors.append(f"{location}: {type(error).__name__}: {error}")
        split_counts[path.stem.replace("syfer_", "")] = count
    overlap = [f"{category}/{family}" for (category, family), splits in family_splits.items() if len(splits) > 1]
    if overlap:
        errors.append("families span train and validation: " + ", ".join(overlap))
    category_counts = dict(sorted(collections.Counter(row["category"] for row in rows).items()))
    difficulty_counts = dict(sorted(collections.Counter(row["difficulty"] for row in rows).items()))
    category_by_split = {
        split: dict(sorted(collections.Counter(row["category"] for row in split_rows).items()))
        for split, split_rows in rows_by_split.items()
    }
    if set(category_counts) != CATEGORIES:
        errors.append("missing dataset category")
    if not 150 <= len(rows) <= 300:
        errors.append("total example count is outside 150–300")
    stats = {
        "total_examples": len(rows), "train_examples": split_counts.get("train", 0),
        "validation_examples": split_counts.get("validation", 0),
        "category_counts": category_counts, "difficulty_counts": difficulty_counts,
        "category_counts_by_split": category_by_split,
        "duplicate_exact_prompts": duplicate_prompts,
        "benchmark_contamination_count": contamination_count,
        "family_split_overlap": overlap,
        "validation_error_count": len(errors), "validation_errors": errors,
    }
    (HERE / "stats.json").write_text(json.dumps(stats, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(stats, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
