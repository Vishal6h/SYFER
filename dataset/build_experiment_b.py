#!/usr/bin/env python3
"""Build small, deterministic Experiment B additions and combined splits."""

import difflib
import json
from pathlib import Path

from build_dataset import SYSTEM, case, fill


HERE = Path(__file__).resolve().parent
NAMES = ("jade", "maple", "quartz", "violet")
SOURCE = "targeted_experiment_b_v1"
VALIDATION_FAMILIES = {
    "b_unique_text", "b_latest_status", "b_explain_condition",
    "b_patch_compact", "b_repo_distractor",
}


def record(category, family, difficulty, user, answer, checks):
    return {"messages": [
        {"role": "system", "content": SYSTEM[category]},
        {"role": "user", "content": user},
        {"role": "assistant", "content": answer},
    ], "category": category, "source": SOURCE, "difficulty": difficulty,
        "family": family, "checks": checks}


def code_family(category, family, objective, answer, cases, before=None, difficulty="medium"):
    rows = []
    for name in NAMES:
        goal = fill(objective, name)
        if before is None:
            user = (f"Implement this small Python behavior: {goal}\n"
                    "Return only function definitions; no imports or example calls.")
        else:
            user = (f"{goal}\n\nExisting implementation:\n{fill(before, name).strip()}\n\n"
                    "Return only corrected function definitions; no imports or example calls.")
        rows.append(record(category, family, difficulty, user, fill(answer, name).strip() + "\n",
                           {"kind": "python", "cases": fill(cases, name)}))
    return rows


def patch_family(family, objective, before, after, cases):
    rows = []
    for name in NAMES:
        path = f"{name}_{family[2:]}.py"
        old = fill(before, name).strip() + "\n"
        new = fill(after, name).strip() + "\n"
        diff = "".join(difflib.unified_diff(old.splitlines(keepends=True), new.splitlines(keepends=True),
                                            fromfile=f"a/{path}", tofile=f"b/{path}",
                                            n=max(len(old.splitlines()), len(new.splitlines()))))
        user = (f"Edit {path} to {fill(objective, name)} Keep unrelated behavior. "
                f"Reply only with a unified diff for a/{path} and b/{path}; counts and context must match.\n\n"
                f"Current file:\n{old}")
        rows.append(record("Patch generation", family, "medium", user, diff,
                           {"kind": "patch", "path": path, "source": old,
                            "expected_source": new, "cases": fill(cases, name)}))
    return rows


def json_family(category, family, make, difficulty="medium"):
    rows = []
    for index, name in enumerate(NAMES):
        user, expected = make(name, index)
        answer = json.dumps(expected, separators=(",", ":"), ensure_ascii=False)
        rows.append(record(category, family, difficulty, user, answer,
                           {"kind": "json", "expected": expected}))
    return rows


def build_new():
    rows = []
    add = rows.extend

    # Stable distinctness across strings, keyed records, and characters.
    add(code_family("Simple coding", "b_unique_labels",
        "Write @N@_labels_once(labels). Return the first spelling of each label, treating labels with different letter case as the same key; preserve arrival order.",
        "def @N@_labels_once(labels):\n    seen = set()\n    result = []\n    for label in labels:\n        key = label.lower()\n        if key not in seen:\n            seen.add(key)\n            result.append(label)\n    return result",
        [case("@N@_labels_once", [["Red","blue","RED","green","BLUE"]], ["Red","blue","green"]),
         case("@N@_labels_once", [["A","a","B"]], ["A","B"]),
         case("@N@_labels_once", [["solo"]], ["solo"])], difficulty="easy"))
    add(code_family("Simple coding", "b_unique_records",
        "Write @N@_first_records(rows). Rows are dictionaries with an integer 'id'. Return a new list keeping the first row for each id, including its original payload.",
        "def @N@_first_records(rows):\n    seen = set()\n    kept = []\n    for row in rows:\n        if row['id'] not in seen:\n            seen.add(row['id'])\n            kept.append(row)\n    return kept",
        [case("@N@_first_records", [[{"id":7,"name":"first"},{"id":2,"name":"other"},{"id":7,"name":"later"}]],
              [{"id":7,"name":"first"},{"id":2,"name":"other"}], True),
         case("@N@_first_records", [[{"id":0},{"id":0}]], [{"id":0}], True),
         case("@N@_first_records", [[{"id":-1}]], [{"id":-1}], True)]))
    add(code_family("Simple coding", "b_unique_text",
        "Write @N@_first_chars(text). Build a string containing each character at its first appearance; spaces and letter case are significant.",
        "def @N@_first_chars(text):\n    seen = set()\n    result = []\n    for char in text:\n        if char not in seen:\n            seen.add(char)\n            result.append(char)\n    return ''.join(result)",
        [case("@N@_first_chars", ["cocoa"], "coa"), case("@N@_first_chars", ["Aa A"], "Aa "),
         case("@N@_first_chars", [""], "")], difficulty="easy"))

    # Last-match state is initialized before the loop and updated on every match.
    add(code_family("Bug fixing", "b_last_nonblank",
        "Fix @N@_last_nonblank(notes) to report the final position containing non-whitespace text; return -1 if every note is blank.",
        "def @N@_last_nonblank(notes):\n    found = -1\n    for position, note in enumerate(notes):\n        if note.strip():\n            found = position\n    return found",
        [case("@N@_last_nonblank", [["ready","  ","done"," "]], 2),
         case("@N@_last_nonblank", [[" ","\t"]], -1),
         case("@N@_last_nonblank", [[]], -1)],
        "def @N@_last_nonblank(notes):\n    for position, note in enumerate(notes):\n        if note.strip():\n            return position\n    return found"))
    add(code_family("Bug fixing", "b_last_true",
        "Fix @N@_last_true to give the final index with a true flag; no true flag returns -1, including empty input.",
        "def @N@_last_true(flags):\n    position = -1\n    for index, flag in enumerate(flags):\n        if flag:\n            position = index\n    return position",
        [case("@N@_last_true", [[True,False,True,False]], 2),
         case("@N@_last_true", [[False,False]], -1), case("@N@_last_true", [[]], -1)],
        "def @N@_last_true(flags):\n    for index, flag in enumerate(flags):\n        if flag:\n            position = index\n    return position"))
    add(code_family("Bug fixing", "b_latest_status",
        "Fix @N@_latest_status: return the status of the last record with the requested code, or None when absent. Earlier matching records must not win.",
        "def @N@_latest_status(records, code):\n    status = None\n    for record in records:\n        if record['code'] == code:\n            status = record['status']\n    return status",
        [case("@N@_latest_status", [[{"code":"a","status":"open"},{"code":"b","status":"ok"},{"code":"a","status":"closed"}],"a"], "closed"),
         case("@N@_latest_status", [[{"code":"b","status":"ok"}],"a"], None),
         case("@N@_latest_status", [[],"a"], None)],
        "def @N@_latest_status(records, code):\n    for record in records:\n        if record['code'] == code:\n            status = record['status']\n    return status"))

    # JSON output types and keys are as important as tracing the code.
    def explain_range(name, index):
        values = [index + 4, index + 8, index + 12, index + 16, index + 20]
        snippet = f"numbers = {values!r}\nprint(sum(numbers[2:5]))"
        expected = {"output": sum(values[2:5]),
                    "explanation": "The slice starts at index 2 and includes the remaining three numbers, whose sum is printed."}
        return ("Trace the code. Reply with only a JSON object containing exactly integer output and string explanation.\n\n"
                + snippet, expected)
    def explain_condition(name, index):
        amount = 4 + index
        snippet = f"score = {amount}\nscore += 3\nprint(score * 2 if score > 5 else score)"
        expected = {"output": (amount + 3) * 2,
                    "explanation": "The updated score is above five, so the expression prints twice that score."}
        return ("Evaluate this Python snippet. Return only JSON with exactly the keys output (an integer) and explanation (a nonempty string).\n\n"
                + snippet, expected)
    add(json_family("Code explanation", "b_explain_range", explain_range))
    add(json_family("Code explanation", "b_explain_condition", explain_condition))

    # Patch examples include context lines and exact hunk lengths.
    add(patch_family("b_patch_fields", "split semicolon-separated fields, strip outer whitespace, and omit empty fields.",
        "def @N@_fields(text):\n    parts = text.split(';')\n    return parts",
        "def @N@_fields(text):\n    parts = text.split(';')\n    return [part.strip() for part in parts if part.strip()]",
        [case("@N@_fields", [" a ; ; b  "], ["a","b"]), case("@N@_fields", [" ; "], [])]))
    add(patch_family("b_patch_spaces", "collapse whitespace inside a display name to single spaces and remove outer whitespace.",
        "def @N@_display_name(text):\n    return text.strip()\n\ndef @N@_unchanged(value):\n    return value",
        "def @N@_display_name(text):\n    return ' '.join(text.split())\n\ndef @N@_unchanged(value):\n    return value",
        [case("@N@_display_name", ["  Ada   Lovelace  "], "Ada Lovelace"),
         case("@N@_display_name", ["A\tB\nC"], "A B C"),
         case("@N@_unchanged", [5], 5)]))
    add(patch_family("b_patch_compact", "keep only nonblank lines after stripping their outer whitespace.",
        "def @N@_compact_lines(text):\n    return text.split('\\n')",
        "def @N@_compact_lines(text):\n    return [line.strip() for line in text.splitlines() if line.strip()]",
        [case("@N@_compact_lines", [" one \n \n two  "], ["one","two"]),
         case("@N@_compact_lines", [" \n "], [])]))

    # Multi-file call chains include a distractor function that is never called.
    def repo_chain(name, index):
        user = (f"Virtual files:\n{name}_entry.py: from {name}_route import route; def launch(items): return route(items)\n"
                f"{name}_route.py: from {name}_clean import prepare; def route(items): return prepare(items)\n"
                f"{name}_clean.py: from {name}_count import tally; def prepare(items): return tally(items)\n"
                f"{name}_count.py: def tally(items): return len(items)\n"
                f"{name}_unused.py: def tally_unused(items): return 99\n"
                "Which file computes the final length, and what is the complete call chain from launch? "
                "Return only JSON with exactly file and chain (array of function names).")
        return user, {"file": f"{name}_count.py", "chain": ["launch","route","prepare","tally"]}
    def repo_owner(name, index):
        user = (f"Virtual files:\n{name}_cli.py: from {name}_service import dispatch; def main(arg): return dispatch(arg)\n"
                f"{name}_service.py: from {name}_encode import encode; def dispatch(arg): return encode(arg)\n"
                f"{name}_encode.py: def encode(arg): return str(arg)\n"
                f"{name}_misc.py: def decode(arg): return arg\n"
                "Which file defines the function that converts the argument to text? "
                "Return only JSON with exactly file and function.")
        return user, {"file": f"{name}_encode.py", "function": "encode"}
    def repo_distractor(name, index):
        user = (f"Virtual files:\n{name}_start.py: from {name}_pipeline import transform; def begin(data): return transform(data)\n"
                f"{name}_pipeline.py: from {name}_math import measure; def transform(data): return measure(data)\n"
                f"{name}_math.py: def measure(data): return sum(data)\n"
                f"{name}_preview.py: def preview(data): return len(data)\n"
                "Where is the numeric sum computed, and what is the full call chain from begin? "
                "Return only JSON with exactly file and chain (array of names).")
        return user, {"file": f"{name}_math.py", "chain": ["begin","transform","measure"]}
    add(json_family("Small repository reasoning", "b_repo_chain", repo_chain))
    add(json_family("Small repository reasoning", "b_repo_owner", repo_owner))
    add(json_family("Small repository reasoning", "b_repo_distractor", repo_distractor))

    # Rehearsal for behaviors that Experiment A already handled well.
    def tool_lookup(name, index):
        symbol = f"{name}_format_cell"
        return (f"Mock tool format: one minified JSON object only, with tool lookup_symbol and arguments.symbol. "
                f"Look up {symbol}.", {"tool":"lookup_symbol","arguments":{"symbol":symbol}})
    def tool_doc(name, index):
        doc_id = f"{name}-reference-{index+3}"
        return (f"Mock tool format: one minified JSON object only, with tool read_doc and arguments.doc_id. "
                f"Read {doc_id}.", {"tool":"read_doc","arguments":{"doc_id":doc_id}})
    add(json_family("Tool-call formatting", "b_tool_lookup", tool_lookup, difficulty="easy"))
    add(json_family("Tool-call formatting", "b_tool_doc", tool_doc, difficulty="easy"))
    add(code_family("Multi-step debugging", "b_parse_total",
        "Fix both functions. @N@_parse_parts reads colon-separated nonblank integers; @N@_total_parts sums them, returning zero for blank input.",
        "def @N@_parse_parts(text):\n    return [int(part.strip()) for part in text.split(':') if part.strip()]\n\ndef @N@_total_parts(text):\n    return sum(@N@_parse_parts(text))",
        [case("@N@_parse_parts", [" 3 : : 8 "], [3,8]), case("@N@_total_parts", [" 3 : : 8 "], 11),
         case("@N@_total_parts", [" : "], 0)],
        "def @N@_parse_parts(text):\n    return [int(part) for part in text.split(':')]\n\ndef @N@_total_parts(text):\n    return len(@N@_parse_parts(text))", difficulty="hard"))
    add(code_family("Multi-step debugging", "b_cart_summary",
        "Fix both functions. @N@_add_unit returns a new counts dict with one unit added; @N@_unit_total sums all counts. Keep the input unchanged.",
        "def @N@_add_unit(counts, item):\n    updated = counts.copy()\n    updated[item] = updated.get(item, 0) + 1\n    return updated\n\ndef @N@_unit_total(counts):\n    return sum(counts.values())",
        [case("@N@_add_unit", [{"pen":2},"pen"], {"pen":3}, True),
         case("@N@_add_unit", [{},"book"], {"book":1}, True),
         case("@N@_unit_total", [{"cup":4,"pad":1}], 5)],
        "def @N@_add_unit(counts, item):\n    counts[item] = 1\n    return counts\n\ndef @N@_unit_total(counts):\n    return len(counts)", difficulty="hard"))
    add(code_family("Test-driven fixing", "b_tdd_bounds",
        "Tests require @N@_within_index(values, position) to return the item at a valid index, or None for negative/out-of-range positions. Fix the code and preserve valid indexing.",
        "def @N@_within_index(values, position):\n    return values[position] if 0 <= position < len(values) else None",
        [case("@N@_within_index", [[4,6],1], 6), case("@N@_within_index", [[4,6],-1], None),
         case("@N@_within_index", [[],0], None)],
        "def @N@_within_index(values, position):\n    return values[position]"))
    add(code_family("Test-driven fixing", "b_tdd_threshold",
        "Tests require @N@_at_least(values, limit) to keep numbers equal to or above limit in order, including duplicates. Fix the boundary check.",
        "def @N@_at_least(values, limit):\n    return [value for value in values if value >= limit]",
        [case("@N@_at_least", [[2,4,4,7],4], [4,4,7]),
         case("@N@_at_least", [[1,2],3], []), case("@N@_at_least", [[],0], [])],
        "def @N@_at_least(values, limit):\n    return [value for value in values if value > limit]"))

    assert len(rows) == 80, len(rows)
    return rows


def write_jsonl(path, rows):
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def main():
    new_rows = build_new()
    old_train = [json.loads(line) for line in (HERE / "syfer_train.jsonl").read_text(encoding="utf-8").splitlines()]
    old_validation = [json.loads(line) for line in (HERE / "syfer_validation.jsonl").read_text(encoding="utf-8").splitlines()]
    new_train = [row for row in new_rows if row["family"] not in VALIDATION_FAMILIES]
    new_validation = [row for row in new_rows if row["family"] in VALIDATION_FAMILIES]
    assert len(new_train) == 60 and len(new_validation) == 20
    write_jsonl(HERE / "experiment_b_train.jsonl", old_train + new_train)
    write_jsonl(HERE / "experiment_b_validation.jsonl", old_validation + new_validation)
    print(f"Wrote {len(new_rows)} new examples; combined train {len(old_train)+len(new_train)}, "
          f"validation {len(old_validation)+len(new_validation)}")


if __name__ == "__main__":
    main()
