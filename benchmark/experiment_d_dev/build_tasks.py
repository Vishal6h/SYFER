#!/usr/bin/env python3
"""Author the 32 D-development tasks once, before D dataset creation."""

import difflib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
TASKS = []


def case(function, args, expected, unchanged=False):
    item = {"function": function, "args": args, "expected": expected}
    if unchanged:
        item["unchanged_args"] = True
    return item


def code(task_id, category, prompt, reference, cases):
    TASKS.append({"id": "ddev_" + task_id, "category": category,
                  "response_mode": "python_code", "prompt": prompt,
                  "reference": reference, "cases": cases})


def explanation(task_id, snippet, output, reason, output_type):
    prompt = ("Trace the following Python program. Return one bare JSON object with exactly "
              f"output ({output_type}) and reason (string). reason must be the literal tag "
              f"{reason}. Do not use prose or Markdown fences.\n\n{snippet}")
    expected = {"output": output, "reason": reason}
    TASKS.append({"id": "ddev_" + task_id, "category": "Code explanation",
                  "response_mode": "explanation_json", "prompt": prompt,
                  "snippet": snippet, "expected": expected,
                  "reference": json.dumps(expected, separators=(",", ":"))})


def patch(task_id, path, instruction, old, new, cases, preserve, context=2):
    diff = "".join(difflib.unified_diff(old.splitlines(keepends=True),
                                        new.splitlines(keepends=True),
                                        fromfile="a/" + path, tofile="b/" + path,
                                        n=context))
    prompt = (f"Return only a raw unified diff for {path}. Use --- a/{path} and +++ b/{path}. "
              f"{instruction} Preserve the unrelated functions named {', '.join(preserve)}. "
              "Every context line, including a blank one, needs its leading space; hunk counts "
              f"must be correct. No prose or Markdown fences.\n\nCurrent file:\n{old}")
    TASKS.append({"id": "ddev_" + task_id, "category": "Patch generation",
                  "response_mode": "unified_diff", "prompt": prompt, "path": path,
                  "source": old, "preserve_functions": preserve,
                  "reference": diff, "cases": cases})


def tool(task_id, prompt, expected):
    TASKS.append({"id": "ddev_" + task_id, "category": "Tool-call formatting",
                  "response_mode": "tool_call_json", "prompt": prompt,
                  "expected": expected,
                  "reference": json.dumps(expected, separators=(",", ":"))})


def repository(task_id, files, entry, output, reason, output_type):
    listing = "\n".join(name + ":\n" + content.rstrip("\n") for name, content in files.items())
    prompt = ("Virtual repository files:\n" + listing + "\n\nWhat does " + entry +
              " print? Return one bare JSON object with exactly output (" + output_type +
              ") and reason (string). reason must be the literal tag " + reason +
              ". No extra keys, prose, or Markdown fences.")
    expected = {"output": output, "reason": reason}
    TASKS.append({"id": "ddev_" + task_id, "category": "Small repository reasoning",
                  "response_mode": "repository_reasoning_json", "prompt": prompt,
                  "files": files, "entry": entry, "expected": expected,
                  "reference": json.dumps(expected, separators=(",", ":"))})


def build():
    TASKS.clear()
    code("encode_runs", "Simple coding",
         "Write encode_runs(text): return a list of [character, run_length] lists for each consecutive run in text. Preserve case; empty text returns []. Return only raw Python function definitions, no imports, prose, or fences.",
         "def encode_runs(text):\n    result = []\n    for char in text:\n        if result and result[-1][0] == char:\n            result[-1][1] += 1\n        else:\n            result.append([char, 1])\n    return result\n",
         [case("encode_runs", ["aaabbc"], [["a", 3], ["b", 2], ["c", 1]]),
          case("encode_runs", [""], []), case("encode_runs", ["abBA"], [["a", 1], ["b", 1], ["B", 1], ["A", 1]])])
    code("adjacent_gap", "Simple coding",
         "Write largest_adjacent_gap(values): return the largest absolute difference between neighboring integers in the input order, or 0 for fewer than two items. Do not sort or mutate the list. Return only raw Python function definitions, no imports, prose, or fences.",
         "def largest_adjacent_gap(values):\n    return max((abs(values[i] - values[i - 1]) for i in range(1, len(values))), default=0)\n",
         [case("largest_adjacent_gap", [[3, 11, 4]], 8, True),
          case("largest_adjacent_gap", [[7]], 0), case("largest_adjacent_gap", [[-3, -9, 2]], 11)])
    code("spreadsheet_label", "Simple coding",
         "Write spreadsheet_label(number) for a positive integer: use one-based spreadsheet columns A through Z, then AA, AB, and so on. Return a string. Return only raw Python function definitions, no imports, prose, or fences.",
         "def spreadsheet_label(number):\n    result = ''\n    while number:\n        number -= 1\n        result = chr(ord('A') + number % 26) + result\n        number //= 26\n    return result\n",
         [case("spreadsheet_label", [1], "A"), case("spreadsheet_label", [26], "Z"),
          case("spreadsheet_label", [27], "AA"), case("spreadsheet_label", [52], "AZ"),
          case("spreadsheet_label", [703], "AAA")])
    code("alternate_letters", "Simple coding",
         "Write alternate_letters(text): the first alphabetic character becomes lowercase, the next uppercase, and so on; nonletters remain unchanged and do not advance the alternation. Return a string. Return only raw Python function definitions, no imports, prose, or fences.",
         "def alternate_letters(text):\n    result = []\n    count = 0\n    for char in text:\n        if char.isalpha():\n            result.append(char.lower() if count % 2 == 0 else char.upper())\n            count += 1\n        else:\n            result.append(char)\n    return ''.join(result)\n",
         [case("alternate_letters", ["a-bC"], "a-Bc"), case("alternate_letters", ["X Y"], "x Y"),
          case("alternate_letters", [""], "")])

    code("power_of_two", "Bug fixing",
         "Fix is_power_of_two(number) for nonnegative integers: 1, 2, 4, 8, ... are powers of two; zero and other integers are not. Return only raw Python function definitions, no imports, prose, or fences.\n\nCurrent code:\ndef is_power_of_two(number):\n    return number % 2 == 0",
         "def is_power_of_two(number):\n    return number > 0 and number & (number - 1) == 0\n",
         [case("is_power_of_two", [1], True), case("is_power_of_two", [2], True),
          case("is_power_of_two", [3], False), case("is_power_of_two", [0], False),
          case("is_power_of_two", [16], True), case("is_power_of_two", [18], False)])
    code("cycle_index", "Bug fixing",
         "Fix cycle_index(index, size) for a positive size: map any positive or negative integer index into 0..size-1 using wraparound. Return only raw Python function definitions, no imports, prose, or fences.\n\nCurrent code:\ndef cycle_index(index, size):\n    return index - size if index >= size else index",
         "def cycle_index(index, size):\n    return index % size\n",
         [case("cycle_index", [-1, 5], 4), case("cycle_index", [12, 5], 2),
          case("cycle_index", [3, 5], 3), case("cycle_index", [-12, 5], 3)])
    code("first_colon", "Bug fixing",
         "Fix split_first_colon(text): return a two-element list [before, after] split at only the first colon. If there is no colon, after is empty. Return only raw Python function definitions, no imports, prose, or fences.\n\nCurrent code:\ndef split_first_colon(text):\n    return text.split(':')",
         "def split_first_colon(text):\n    if ':' not in text:\n        return [text, '']\n    return text.split(':', 1)\n",
         [case("split_first_colon", ["a:b:c"], ["a", "b:c"]),
          case("split_first_colon", ["plain"], ["plain", ""]),
          case("split_first_colon", [":x"], ["", "x"])])
    code("triangle_rule", "Bug fixing",
         "Fix valid_triangle(a,b,c): return a boolean for strictly positive integer sides that form a nondegenerate triangle. Check every triangle inequality. Return only raw Python function definitions, no imports, prose, or fences.\n\nCurrent code:\ndef valid_triangle(a, b, c):\n    return a + b >= c",
         "def valid_triangle(a, b, c):\n    return a > 0 and b > 0 and c > 0 and a + b > c and a + c > b and b + c > a\n",
         [case("valid_triangle", [3, 4, 5], True), case("valid_triangle", [1, 1, 2], False),
          case("valid_triangle", [0, 4, 4], False), case("valid_triangle", [5, 1, 1], False),
          case("valid_triangle", [2, 2, 3], True), case("valid_triangle", [10, 4, 7], True),
          case("valid_triangle", [10, 1, 1], False)])

    explanation("closure_binding", "functions = [lambda: index for index in range(3)]\nprint([function() for function in functions])",
                [2, 2, 2], "closure_reads_late_bound_name", "array of three integers")
    explanation("live_dict_view", "mapping = {'a': 1}\nkeys = mapping.keys()\nmapping['b'] = 2\nprint(len(keys))",
                2, "dictionary_view_reflects_updates", "integer")
    explanation("set_add_result", "numbers = {1}\nresult = numbers.add(2)\nprint([len(numbers), int(result is None)])",
                [2, 1], "set_add_returns_none", "array of two integers")
    explanation("try_else", "try:\n    number = int('7')\nexcept ValueError:\n    number = 0\nelse:\n    number += 3\nprint(number)",
                10, "try_else_runs_without_exception", "integer")

    old = ("def prefix(value):\n    return '>' + value\n\ndef normalize_lines(text):\n"
           "    return text.replace('\\r\\n', '\\n')\n")
    new = old.replace("return text.replace('\\r\\n', '\\n')",
                      "return text.replace('\\r\\n', '\\n').replace('\\r', '\\n')")
    patch("patch_line_endings", "line_text.py",
          "Convert both CRLF and lone carriage returns to LF, without changing existing LF characters.",
          old, new, [case("normalize_lines", ["a\r\nb\rc"], "a\nb\nc"),
                     case("normalize_lines", ["x\ny"], "x\ny"), case("prefix", ["ok"], ">ok")],
          ["prefix"])
    old = ("def identity(value):\n    return value\n\ndef drop_one_newline(text):\n"
           "    return text.rstrip()\n\n")
    new = old.replace("return text.rstrip()", "return text[:-1] if text.endswith('\\n') else text")
    patch("patch_terminal_newline", "tail_text.py",
          "Remove exactly one final LF if present; retain spaces and any earlier LF. The source ends with an empty context line.",
          old, new, [case("drop_one_newline", ["a  \n"], "a  "),
                     case("drop_one_newline", ["a  "], "a  "),
                     case("drop_one_newline", ["\n\n"], "\n"), case("identity", [3], 3)],
          ["identity"], context=4)
    old = ("def dot_product(left, right):\n    return sum(a + b for a, b in zip(left, right))\n\n"
           "def identity(value):\n    return value\n\n"
           "def weighted_total(values, weights):\n    return sum(value + weight for value, weight in zip(values, weights))\n")
    new = old.replace("sum(a + b for a, b in zip(left, right))",
                      "sum(a * b for a, b in zip(left, right))").replace(
                      "sum(value + weight for value, weight in zip(values, weights))",
                      "sum(value * weight for value, weight in zip(values, weights))")
    patch("patch_weighted_products", "vectors.py",
          "Both dot_product and weighted_total must sum pairwise products, stopping at the shorter input. Keep identity unchanged.",
          old, new, [case("dot_product", [[2, 3], [4, 5]], 23),
                     case("dot_product", [[7], [2, 9]], 14),
                     case("weighted_total", [[1, 5], [10, 2]], 20),
                     case("identity", [17], 17)], ["identity"], context=1)
    old = ("def count_values(values):\n    return len(values)\n\n"
           "def select_positions(values, positions):\n    selected = []\n"
           "    for index in range(len(positions)):\n        selected.append(values[index])\n"
           "    return selected\n")
    new = old.replace("for index in range(len(positions)):\n        selected.append(values[index])",
                      "for position in positions:\n        selected.append(values[position])")
    patch("patch_position_selector", "select.py",
          "Select source elements at the requested positions, in the requested order, retaining duplicate positions.",
          old, new, [case("select_positions", [["a", "b", "c"], [2, 0]], ["c", "a"]),
                     case("select_positions", [[5, 6], []], []),
                     case("select_positions", [[5, 6], [1, 1]], [6, 6]),
                     case("count_values", [[1, 2, 3]], 3)], ["count_values"])

    code("debug_coordinates", "Multi-step debugging",
         "Fix both functions. parse_coordinate(text) accepts two comma-separated signed integers and returns [x,y]; manhattan_from_origin(text) returns abs(x)+abs(y). Return only raw Python function definitions, no imports, prose, or fences.\n\nCurrent code:\ndef parse_coordinate(text):\n    x, y = text.split(',')\n    return [int(y), int(x)]\n\ndef manhattan_from_origin(text):\n    x, y = parse_coordinate(text)\n    return abs(x - y)",
         "def parse_coordinate(text):\n    x, y = text.split(',')\n    return [int(x), int(y)]\n\ndef manhattan_from_origin(text):\n    x, y = parse_coordinate(text)\n    return abs(x) + abs(y)\n",
         [case("parse_coordinate", ["-3, 8"], [-3, 8]),
          case("manhattan_from_origin", ["-3, 8"], 11),
          case("parse_coordinate", ["0,-2"], [0, -2]),
          case("manhattan_from_origin", ["0,-2"], 2)])
    code("debug_path_segments", "Multi-step debugging",
         "Fix both functions. clean_segments(path) returns a list of nonempty slash-separated segments, discarding '.' segments but leaving '..' literal. path_depth(path) is the count of cleaned segments. Return only raw Python function definitions, no imports, prose, or fences.\n\nCurrent code:\ndef clean_segments(path):\n    return path.split('/')\n\ndef path_depth(path):\n    return len(path.split('/'))",
         "def clean_segments(path):\n    return [part for part in path.split('/') if part and part != '.']\n\ndef path_depth(path):\n    return len(clean_segments(path))\n",
         [case("clean_segments", ["/a//./b/"], ["a", "b"]),
          case("path_depth", ["/a//./b/"], 2),
          case("clean_segments", ["../x"], ["..", "x"]),
          case("path_depth", [""], 0)])
    code("debug_grades", "Multi-step debugging",
         "Fix both functions. grade_band(score) returns A for >=90, B for >=80, C for >=70, otherwise D. count_passing(scores) counts scores >=70. Return only raw Python function definitions, no imports, prose, or fences.\n\nCurrent code:\ndef grade_band(score):\n    if score > 90: return 'A'\n    if score > 80: return 'B'\n    if score > 70: return 'C'\n    return 'D'\n\ndef count_passing(scores):\n    return sum(score > 70 for score in scores)",
         "def grade_band(score):\n    if score >= 90: return 'A'\n    if score >= 80: return 'B'\n    if score >= 70: return 'C'\n    return 'D'\n\ndef count_passing(scores):\n    return sum(score >= 70 for score in scores)\n",
         [case("grade_band", [90], "A"), case("grade_band", [80], "B"),
          case("grade_band", [70], "C"), case("grade_band", [69], "D"),
          case("count_passing", [[69, 70, 80, 90]], 3)])
    code("debug_digit_product", "Multi-step debugging",
         "Fix both functions. digit_values(text) returns the decimal digit values found in text, in order, ignoring nondigits. digit_product(text) multiplies those values; the product of no digits is 1. Return only raw Python function definitions, no imports, prose, or fences.\n\nCurrent code:\ndef digit_values(text):\n    return [char for char in text if char.isdigit()]\n\ndef digit_product(text):\n    return sum(digit_values(text))",
         "def digit_values(text):\n    return [int(char) for char in text if char.isdigit()]\n\ndef digit_product(text):\n    product = 1\n    for digit in digit_values(text):\n        product *= digit\n    return product\n",
         [case("digit_values", ["a2-03"], [2, 0, 3]),
          case("digit_product", ["a2-03"], 0),
          case("digit_product", ["2x3y4"], 24),
          case("digit_product", ["abc"], 1)])

    tool("tool_catalog_exact",
         "Mock tools are catalog_lookup and catalog_search. Choose catalog_lookup for the exact package starlib, not a search query. Return one bare JSON object with exactly tool (string) and arguments (object); tool must be catalog_lookup. arguments must have exactly package (string) and version (null because none was requested). Use package starlib. No prose or Markdown fences; JSON whitespace and object-key order do not matter.",
         {"tool": "catalog_lookup", "arguments": {"package": "starlib", "version": None}})
    tool("tool_job_batch",
         "Mock tools are schedule_jobs and cancel_jobs. Choose schedule_jobs. Return one bare JSON object with exactly tool (string) and arguments (object). arguments must have exactly jobs (array) and dry_run (boolean). jobs has two objects in order: name lint, priority 1; name typecheck, priority 2. Each job object has exactly name (string) and priority (integer). dry_run is true. No prose or fences; JSON whitespace and object-key order do not matter.",
         {"tool": "schedule_jobs", "arguments": {"jobs": [{"name": "lint", "priority": 1},
                                                       {"name": "typecheck", "priority": 2}],
                                                "dry_run": True}})
    tool("tool_emit_metric",
         "Mock tools are read_metric and emit_metric. Choose emit_metric to record a new value. Return one bare JSON object with exactly tool (string) and arguments (object). arguments must have exactly name (string), labels (object), and value (integer); omit optional unit entirely. Set name queue_depth, labels to exactly region: west and service: api (both strings), and value to 7. No prose or fences; JSON whitespace and object-key order do not matter.",
         {"tool": "emit_metric", "arguments": {"name": "queue_depth",
                                                 "labels": {"region": "west", "service": "api"},
                                                 "value": 7}})
    tool("tool_archive_policy",
         "Mock tools are archive_item and restore_item. Choose archive_item. Return one bare JSON object with exactly tool (string) and arguments (object). arguments has exactly target (object) and options (object). target has exactly bucket (string) logs and key (string) 2025/entry. options has exactly retain_days (integer) 30 and notify (null, not omitted). No prose or fences; JSON whitespace and object-key order do not matter.",
         {"tool": "archive_item", "arguments": {"target": {"bucket": "logs", "key": "2025/entry"},
                                                  "options": {"retain_days": 30, "notify": None}}})

    code("tdd_monotonic", "Test-driven fixing",
         "Read these tests before fixing: monotonic([1,2,2]) -> True; [3,2,1] -> True; [1,3,2] -> False; [] -> True; [4] -> True. Nondecreasing or nonincreasing counts as monotonic. Return only raw Python function definitions, no imports, prose, or fences.\n\nCurrent code:\ndef monotonic(values):\n    return values == sorted(values)",
         "def monotonic(values):\n    return (all(values[i] <= values[i + 1] for i in range(len(values) - 1)) or\n            all(values[i] >= values[i + 1] for i in range(len(values) - 1)))\n",
         [case("monotonic", [[1, 2, 2]], True), case("monotonic", [[3, 2, 1]], True),
          case("monotonic", [[1, 3, 2]], False), case("monotonic", [[]], True),
          case("monotonic", [[4]], True)])
    code("tdd_suffix_sum", "Test-driven fixing",
         "Read these tests before fixing: largest_suffix_sum([2,-5,4]) -> 4; [-3,-2] -> 0; [1,2,3] -> 6; [] -> 0. The empty suffix is allowed. Return only raw Python function definitions, no imports, prose, or fences.\n\nCurrent code:\ndef largest_suffix_sum(values):\n    return max(values)",
         "def largest_suffix_sum(values):\n    total = 0\n    best = 0\n    for value in reversed(values):\n        total += value\n        best = max(best, total)\n    return best\n",
         [case("largest_suffix_sum", [[2, -5, 4]], 4),
          case("largest_suffix_sum", [[-3, -2]], 0),
          case("largest_suffix_sum", [[1, 2, 3]], 6),
          case("largest_suffix_sum", [[]], 0)])
    code("tdd_rotation", "Test-driven fixing",
         "Read these tests before fixing: is_rotation('abcd','cdab') -> True; ('abcd','acbd') -> False; ('','') -> True; ('a','aa') -> False. Return a boolean; preserve case. Return only raw Python function definitions, no imports, prose, or fences.\n\nCurrent code:\ndef is_rotation(left, right):\n    return sorted(left) == sorted(right)",
         "def is_rotation(left, right):\n    return len(left) == len(right) and right in left + left\n",
         [case("is_rotation", ["abcd", "cdab"], True),
          case("is_rotation", ["abcd", "acbd"], False),
          case("is_rotation", ["", ""], True),
          case("is_rotation", ["a", "aa"], False),
          case("is_rotation", ["abab", "baba"], True),
          case("is_rotation", ["ab", "ba"], True)])
    code("tdd_outer_quotes", "Test-driven fixing",
         "Read these tests before fixing: double-quoted hi becomes hi; single-quoted hi becomes hi; mismatched single/double quotes remain unchanged; x stays x; empty stays empty. Remove only one matching pair of outer single or double quotes. Return only raw Python function definitions, no imports, prose, or fences.\n\nCurrent code:\ndef strip_matching_quotes(text):\n    return text.strip(\"'\\\"\")",
         "def strip_matching_quotes(text):\n    if len(text) >= 2 and text[0] == text[-1] and text[0] in (\"'\", '\"'):\n        return text[1:-1]\n    return text\n",
         [case("strip_matching_quotes", ['"hi"'], "hi"),
          case("strip_matching_quotes", ["'hi'"], "hi"),
          case("strip_matching_quotes", ["'hi\""], "'hi\""),
          case("strip_matching_quotes", ["x"], "x"),
          case("strip_matching_quotes", [""], "")])

    repository("repo_reexport_math", {
        "rates.py": "def scale(value):\n    return value * 3\n",
        "api.py": "from rates import scale as amplify\ndef quote(value):\n    return amplify(value) + 2\n",
        "app.py": "from api import quote\nprint(quote(4))\n",
    }, "app.py", 14, "alias_preserved_through_reexport", "integer")
    repository("repo_callback_composition", {
        "registry.py": "HANDLERS = {}\ndef register(name, function):\n    HANDLERS[name] = function\n",
        "plugins.py": "from registry import register\ndef exclaim(text):\n    return text + '!'\nregister('shout', lambda text: exclaim(text.upper()))\n",
        "app.py": "import json\nimport plugins\nfrom registry import HANDLERS\nprint(json.dumps([HANDLERS['shout'](word) for word in ['go', 'up']]))\n",
    }, "app.py", ["GO!", "UP!"], "registration_runs_during_import", "array of two strings")
    repository("repo_exception_propagation", {
        "events.py": "EVENTS = []\n",
        "reader.py": "def read():\n    raise OSError('unavailable')\n",
        "service.py": "from events import EVENTS\nfrom reader import read\ndef fetch():\n    try:\n        return read()\n    finally:\n        EVENTS.append('finished')\n",
        "app.py": "import json\nfrom events import EVENTS\nfrom service import fetch\ntry:\n    fetch()\nexcept OSError:\n    pass\nprint(json.dumps(EVENTS))\n",
    }, "app.py", ["finished"], "finally_runs_during_propagation", "array of one string")
    repository("repo_config_precedence", {
        "defaults.py": "TIMEOUT = 5\n",
        "environment.py": "from defaults import TIMEOUT as BASE\ndef timeout(override):\n    return BASE if override is None else override\n",
        "app.py": "from environment import timeout\nprint(timeout(0))\n",
    }, "app.py", 0, "explicit_zero_override_wins", "integer")
    assert len(TASKS) == 32, len(TASKS)
    return TASKS


def main():
    rows = build()
    path = HERE / "tasks.json"
    path.write_text(json.dumps(rows, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {len(rows)} authored D-development tasks to {path}")


if __name__ == "__main__":
    main()
