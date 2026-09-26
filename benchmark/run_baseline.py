#!/usr/bin/env python3
"""Run the fixed Stage 1 tasks against the installed stock Ollama model."""

import argparse
import ast
import datetime as dt
import hashlib
import json
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path


MODEL = "qwen2.5-coder:3b"
API = "http://127.0.0.1:11434"
ROOT = Path(__file__).resolve().parents[1]
TASKS = Path(__file__).with_name("tasks.json")
OUTPUT = ROOT / "results" / "baseline"
OPTIONS = {"temperature": 0, "num_predict": 512, "seed": 42}


def request(endpoint, payload=None, timeout=180):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        API + endpoint,
        data=data,
        headers={"Content-Type": "application/json"},
        method="GET" if data is None else "POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.load(response)


def code_only(raw):
    text = raw.strip()
    match = re.search(r"```(?:python|py|diff|json)?[ \t]*\n(.*?)\n```", text, re.DOTALL | re.IGNORECASE)
    return match.group(1) if match else text


def check_python_shape(code):
    tree = ast.parse(code)
    if not tree.body or any(not isinstance(node, ast.FunctionDef) for node in tree.body):
        raise ValueError("response must contain only function definitions")
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom, ast.Global, ast.Nonlocal)):
            raise ValueError("imports and global access are not allowed")
        if isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            raise ValueError("dunder attributes are not allowed")
        if isinstance(node, ast.Name) and node.id in {"open", "exec", "eval", "compile", "__import__", "input"}:
            raise ValueError("file/process access is not allowed")


HARNESS = r'''
import json, sys
payload = json.load(sys.stdin)
allowed = {name: getattr(__builtins__, name) for name in (
    "abs", "all", "any", "bool", "dict", "enumerate", "filter", "float", "int",
    "len", "list", "map", "max", "min", "range", "reversed", "round", "set",
    "sorted", "str", "sum", "tuple", "zip")}
scope = {"__builtins__": allowed}
exec(compile(payload["code"], "<model response>", "exec"), scope)
failures = []
for index, case in enumerate(payload["cases"], 1):
    try:
        before = json.loads(json.dumps(case["args"]))
        actual = scope[case["function"]](*case["args"])
        if actual != case["expected"] or type(actual) is not type(case["expected"]):
            failures.append({"case": index, "expected": case["expected"], "actual": actual})
        if case.get("unchanged_args") and case["args"] != before:
            failures.append({"case": index, "error": "input arguments were mutated"})
    except Exception as error:
        failures.append({"case": index, "error": type(error).__name__ + ": " + str(error)})
print(json.dumps({"passed": not failures, "failures": failures}, default=repr))
'''


def validate_python(code, cases):
    check_python_shape(code)
    with tempfile.TemporaryDirectory(prefix="syfer-benchmark-") as temp:
        result = subprocess.run(
            [sys.executable, "-I", "-B", "-c", HARNESS],
            input=json.dumps({"code": code, "cases": cases}),
            text=True, capture_output=True, cwd=temp, timeout=5, check=False,
        )
    if result.returncode:
        return False, (result.stderr or result.stdout).strip()[-600:]
    report = json.loads(result.stdout)
    return report["passed"], report["failures"]


def apply_single_file_diff(source, diff, path):
    """Apply one ordinary unified diff, checking every context/deletion line."""
    lines = [line + "\n" for line in diff.strip().splitlines()]
    if len(lines) < 4 or lines[0].rstrip("\n") != "--- a/" + path or lines[1].rstrip("\n") != "+++ b/" + path:
        raise ValueError("expected a unified diff with exact file headers")
    old = source.splitlines(keepends=True)
    new = []
    old_pos = 0
    index = 2
    while index < len(lines):
        header = re.fullmatch(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@.*", lines[index].rstrip("\n"))
        if not header:
            raise ValueError("invalid hunk header")
        start, old_count, new_start, new_count = map(int, (header.group(1), header.group(2) or "1", header.group(3), header.group(4) or "1"))
        if start - 1 < old_pos or new_start - 1 != len(new) + start - 1 - old_pos:
            raise ValueError("hunk positions do not match")
        new.extend(old[old_pos:start - 1])
        old_pos = start - 1
        index += 1
        consumed = produced = 0
        while index < len(lines) and not lines[index].startswith("@@ "):
            line = lines[index]
            if not line or line[0] not in " +-":
                raise ValueError("invalid diff line")
            content = line[1:]
            if line[0] in " -":
                if old_pos >= len(old) or old[old_pos] != content:
                    raise ValueError("diff context does not match source")
                old_pos += 1
                consumed += 1
            if line[0] in " +":
                new.append(content)
                produced += 1
            index += 1
        if consumed != old_count or produced != new_count:
            raise ValueError("hunk line counts do not match")
    if old_pos == 0:
        raise ValueError("diff has no hunks")
    new.extend(old[old_pos:])
    return "".join(new)


def validate(task, raw):
    kind = task["kind"]
    if kind == "python":
        return validate_python(code_only(raw), task["cases"])
    if kind == "patch":
        patched = apply_single_file_diff(task["source"], code_only(raw), task["path"])
        return validate_python(patched, task["cases"])
    if kind == "tool_call":
        expected = json.dumps(task["expected"], separators=(",", ":"), ensure_ascii=False)
        return raw == expected, "exact match" if raw == expected else "response differs from exact minified mock tool call"
    if kind == "json_fields":
        data = json.loads(code_only(raw))
        expected = task["expected_fields"]
        keys = set(expected) | ({"explanation"} if "explanation" in task["prompt"] else set())
        passed = isinstance(data, dict) and set(data) == keys and all(data.get(k) == v for k, v in expected.items())
        if "explanation" in keys:
            passed = passed and isinstance(data.get("explanation"), str) and bool(data["explanation"].strip())
        return passed, "expected fields and exact keys" if passed else "incorrect JSON fields or extra/missing keys"
    raise ValueError("unknown validator: " + kind)


def save_json(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def make_summary(run_dir, results, elapsed, model_id):
    by_category = {}
    for item in results:
        row = by_category.setdefault(item["category"], {"passed": 0, "total": 0})
        row["total"] += 1
        row["passed"] += int(item["passed"])
    passed = sum(item["passed"] for item in results)
    summary = {
        "model": MODEL, "model_id": model_id, "task_count": len(results),
        "passed": passed, "failed": len(results) - passed,
        "total_runtime_seconds": round(elapsed, 3), "by_category": by_category,
        "tasks": results,
    }
    save_json(run_dir / "summary.json", summary)
    lines = ["# Stock model baseline", "", f"Model: `{MODEL}` (ID `{model_id}`)",
             f"Tasks: {len(results)} | Passed: {passed} | Failed: {len(results) - passed} | Runtime: {elapsed:.2f} s", "",
             "| Category | Passed | Total |", "| --- | ---: | ---: |"]
    for category, row in by_category.items():
        lines.append(f"| {category} | {row['passed']} | {row['total']} |")
    lines.extend(["", "## Failed tasks", ""])
    failures = [item for item in results if not item["passed"]]
    lines.extend(f"- `{item['id']}`: {item['detail']}" for item in failures)
    if not failures:
        lines.append("None.")
    (run_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, help="Run only the first N tasks for a smoke check")
    args = parser.parse_args()
    tasks = json.loads(TASKS.read_text(encoding="utf-8"))
    if args.limit is not None:
        tasks = tasks[:args.limit]
    if len({task["id"] for task in tasks}) != len(tasks):
        parser.error("task IDs must be unique")
    try:
        installed = request("/api/tags", timeout=10)["models"]
    except (urllib.error.URLError, TimeoutError, KeyError) as error:
        parser.exit(2, f"Cannot read local Ollama model list: {error}\n")
    match = next((model for model in installed if model.get("name") == MODEL), None)
    if match is None:
        parser.exit(2, f"Required local model {MODEL} is not installed; no model will be pulled.\n")
    run_id = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    run_dir = OUTPUT / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    tasks_bytes = TASKS.read_bytes()
    runner_bytes = Path(__file__).read_bytes()
    save_json(run_dir / "tasks_snapshot.json", tasks)
    save_json(run_dir / "run_config.json", {
        "model": MODEL, "model_id": match.get("digest", "unknown"),
        "options": OPTIONS, "tasks_file": str(TASKS.relative_to(ROOT)),
        "tasks_sha256": hashlib.sha256(tasks_bytes).hexdigest(),
        "runner_sha256": hashlib.sha256(runner_bytes).hexdigest(),
        "tasks": [task["id"] for task in tasks], "started_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
    })
    results = []
    started = time.monotonic()
    for task in tasks:
        task_started = time.monotonic()
        raw = ""
        try:
            response = request("/api/generate", {
                "model": MODEL, "prompt": task["prompt"], "stream": False, "options": OPTIONS,
            })
            raw = response["response"]
            (run_dir / (task["id"] + ".txt")).write_text(raw, encoding="utf-8")
            passed, detail = validate(task, raw)
            error = None
        except Exception as exc:
            passed, detail, error = False, str(exc), type(exc).__name__
            (run_dir / (task["id"] + ".txt")).write_text(raw, encoding="utf-8")
        item = {"id": task["id"], "category": task["category"], "passed": bool(passed),
                "runtime_seconds": round(time.monotonic() - task_started, 3),
                "detail": detail, "error": error, "raw_response_file": task["id"] + ".txt"}
        results.append(item)
        save_json(run_dir / "progress.json", results)
        print(f"{'PASS' if passed else 'FAIL'} {task['id']} ({item['runtime_seconds']:.2f}s)", flush=True)
    summary = make_summary(run_dir, results, time.monotonic() - started, match.get("digest", "unknown"))
    print(f"Saved {summary['passed']}/{summary['task_count']} results to {run_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
