#!/usr/bin/env python3
"""Build 120 authored Experiment C examples from 30 distinct task families."""

import difflib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
NAMES = ("aster", "bloom", "cobalt", "dune")
SOURCE = "experiment_c_authored_v1"
VALIDATION_FAMILIES = {
    "c_patch_plural", "c_tool_batch", "c_repo_callback", "c_explain_unpack",
    "c_simple_enumerate", "c_bug_digits", "c_debug_polygon", "c_tdd_overlap",
}
SYSTEM = {
    "Simple coding": "Write small correct Python functions. Return only code.",
    "Bug fixing": "Correct the requested Python behavior while keeping unrelated behavior.",
    "Code explanation": "Trace the code and return exactly the requested JSON object.",
    "Patch generation": "Return only a valid unified diff. Preserve unrelated lines.",
    "Multi-step debugging": "Fix all stated issues and return only Python function definitions.",
    "Tool-call formatting": "Return only the exact minified mock-tool JSON object; no prose.",
    "Test-driven fixing": "Read the cases before fixing the function. Return only code.",
    "Small repository reasoning": "Reason across virtual files and return exactly the requested JSON object.",
}


def make(category, family, user, assistant, checks, difficulty="medium"):
    return {"messages": [{"role": "system", "content": SYSTEM[category]},
                         {"role": "user", "content": user},
                         {"role": "assistant", "content": assistant}],
            "category": category, "source": SOURCE, "difficulty": difficulty,
            "family": family, "checks": checks}


def case(function, args, expected, unchanged=False):
    result = {"function": function, "args": args, "expected": expected}
    if unchanged:
        result["unchanged_args"] = True
    return result


def code_family(category, family, goal, answer, cases, broken=None, difficulty="medium"):
    rows = []
    for name in NAMES:
        replace = lambda value: json.loads(json.dumps(value).replace("@N@", name))
        prompt = replace(goal)
        if broken is not None:
            prompt += "\n\nCurrent implementation:\n" + replace(broken).strip()
        prompt += "\nReturn only Python function definitions; no imports or example calls."
        rows.append(make(category, family, prompt, replace(answer).strip() + "\n",
                         {"kind": "python", "cases": replace(cases)}, difficulty))
    return rows


def patch_family(family, instruction, before, after, cases, difficulty="medium"):
    rows = []
    for name in NAMES:
        path = f"{name}_{family[2:]}.py"
        replace = lambda value: json.loads(json.dumps(value).replace("@N@", name))
        old, new = replace(before).strip() + "\n", replace(after).strip() + "\n"
        diff = "".join(difflib.unified_diff(old.splitlines(keepends=True), new.splitlines(keepends=True),
                                            fromfile=f"a/{path}", tofile=f"b/{path}",
                                            n=max(len(old.splitlines()), len(new.splitlines()))))
        prompt = (f"Edit {path}. {replace(instruction)} Reply only with a unified diff using "
                  f"--- a/{path} and +++ b/{path}; keep context and hunk counts correct.\n\n"
                  f"Current file:\n{old}")
        rows.append(make("Patch generation", family, prompt, diff,
                         {"kind": "patch", "path": path, "source": old,
                          "expected_source": new, "cases": replace(cases)}, difficulty))
    return rows


def json_family(category, family, make_prompt, difficulty="medium"):
    rows = []
    for index, name in enumerate(NAMES):
        prompt, expected, extra = make_prompt(name, index)
        answer = json.dumps(expected, separators=(",", ":"), ensure_ascii=False)
        rows.append(make(category, family, prompt, answer,
                         {"kind": "json", "expected": expected, **extra}, difficulty))
    return rows


def build():
    rows = []
    add = rows.extend

    # Patch families: full-context diffs, insertion/deletion, multiline changes.
    add(patch_family("c_patch_plural", "Use singular only when count is one; otherwise use plural.",
        "def @N@_label(count):\n    return str(count) + ' items'\n\ndef @N@_identity(x):\n    return x",
        "def @N@_label(count):\n    word = 'item' if count == 1 else 'items'\n    return str(count) + ' ' + word\n\ndef @N@_identity(x):\n    return x",
        [case("@N@_label", [1], "1 item"), case("@N@_label", [0], "0 items"),
         case("@N@_identity", [17], 17)], difficulty="easy"))
    add(patch_family("c_patch_windows", "Return sums of every complete window of positive size, including the final window.",
        "def @N@_windows(values, width):\n    return [sum(values[i:i + width]) for i in range(len(values) - width)]\n\ndef @N@_size(values):\n    return len(values)",
        "def @N@_windows(values, width):\n    return [sum(values[i:i + width]) for i in range(len(values) - width + 1)]\n\ndef @N@_size(values):\n    return len(values)",
        [case("@N@_windows", [[2,4,6,8],2], [6,10,14]),
         case("@N@_windows", [[5],1], [5]), case("@N@_size", [[1,2,3]], 3)]))
    add(patch_family("c_patch_percent", "Format a ratio as a percentage with one decimal digit.",
        "def @N@_percent(ratio):\n    return f'{ratio:.1f}%'\n\ndef @N@_unit():\n    return '%'",
        "def @N@_percent(ratio):\n    scaled = ratio * 100\n    return f'{scaled:.1f}%'\n\ndef @N@_unit():\n    return '%'",
        [case("@N@_percent", [0.125], "12.5%"), case("@N@_percent", [1], "100.0%"),
         case("@N@_unit", [], "%")]))
    add(patch_family("c_patch_unique_union", "Return sorted values appearing in either list, including negative values.",
        "def @N@_union(left, right):\n    return sorted(set(left) & set(right))\n\ndef @N@_count(values):\n    return len(values)",
        "def @N@_union(left, right):\n    return sorted(set(left) | set(right))\n\ndef @N@_count(values):\n    return len(values)",
        [case("@N@_union", [[-3,1,1],[2,-3]], [-3,1,2]),
         case("@N@_union", [[],[4]], [4]), case("@N@_count", [[5]], 1)]))
    add(patch_family("c_patch_middle", "Return the middle character for odd-length text and two middle characters for even-length text; empty text stays empty.",
        "def @N@_middle(text):\n    return text[len(text) // 2]\n\ndef @N@_unchanged(value):\n    return value",
        "def @N@_middle(text):\n    start = (len(text) - 1) // 2\n    end = len(text) // 2 + 1\n    return text[start:end]\n\ndef @N@_unchanged(value):\n    return value",
        [case("@N@_middle", ["planet"], "an"), case("@N@_middle", ["orbit"], "b"),
         case("@N@_middle", [""], ""), case("@N@_unchanged", [9], 9)]))
    add(patch_family("c_patch_drop_debug", "Remove the diagnostic print while retaining the computed result and helper.",
        "def @N@_double(value):\n    print('debug', value)\n    return value * 2\n\ndef @N@_triple(value):\n    return value * 3",
        "def @N@_double(value):\n    return value * 2\n\ndef @N@_triple(value):\n    return value * 3",
        [case("@N@_double", [7], 14), case("@N@_double", [0], 0),
         case("@N@_triple", [4], 12)]))
    add(patch_family("c_patch_normalize_flags", "Map each input flag to a boolean without dropping false entries.",
        "def @N@_flags(values):\n    return [bool(value) for value in values if value]\n\ndef @N@_count(values):\n    return len(values)",
        "def @N@_flags(values):\n    return [bool(value) for value in values]\n\ndef @N@_count(values):\n    return len(values)",
        [case("@N@_flags", [[1,0,"",2]], [True,False,False,True]),
         case("@N@_flags", [[]], []), case("@N@_count", [[0,1]], 2)]))
    add(patch_family("c_patch_wrap_angle", "Wrap any integer angle into 0 through 359 degrees.",
        "def @N@_angle(degrees):\n    return degrees\n\ndef @N@_full_turn():\n    return 360",
        "def @N@_angle(degrees):\n    return degrees % 360\n\ndef @N@_full_turn():\n    return 360",
        [case("@N@_angle", [-30], 330), case("@N@_angle", [725], 5),
         case("@N@_full_turn", [], 360)]))

    # Exact structured-output families, including selection, nesting, arrays and null.
    def tool_batch(name, index):
        path = f"src/{name}_engine.py"
        return (f"Mock protocol: one minified JSON object only. Select batch_inspect rather than open_single. "
                f"Inspect {path} at lines 4 and 9. Schema: tool and arguments with path string and lines integer array.",
                {"tool":"batch_inspect","arguments":{"path":path,"lines":[4,9]}}, {})
    def tool_single(name, index):
        doc = f"{name}-policy-{index+7}"
        return (f"Mock protocol: one minified JSON object only. Select open_single rather than batch_inspect. "
                f"Open document {doc}. Schema: tool and arguments with doc string.",
                {"tool":"open_single","arguments":{"doc":doc}}, {})
    def tool_schedule(name, index):
        return (f"Mock protocol: one minified JSON object only. Use schedule_checks. "
                f"Plan suites {name}_unit then {name}_integration in that order, with dry_run true. "
                "Schema: tool and arguments with suites array of strings and dry_run boolean.",
                {"tool":"schedule_checks","arguments":{"suites":[f"{name}_unit",f"{name}_integration"],"dry_run":True}}, {})
    def tool_report(name, index):
        return (f"Mock protocol: one minified JSON object only. Use report_issue. "
                f"Report severity {index+1} on module {name}_api; owner is intentionally unspecified and must be null. "
                "Schema: tool and arguments with severity integer, module string, and owner nullable string.",
                {"tool":"report_issue","arguments":{"severity":index+1,"module":f"{name}_api","owner":None}}, {})
    def tool_plan(name, index):
        return (f"Mock protocol: one minified JSON object only. Use plan_actions with two steps: "
                f"first inspect {name}_manifest, then validate {name}_tests. "
                "Schema: tool and arguments.steps array; each step has action and target strings.",
                {"tool":"plan_actions","arguments":{"steps":[{"action":"inspect","target":f"{name}_manifest"},
                                                            {"action":"validate","target":f"{name}_tests"}]}}, {})
    def tool_nested(name, index):
        return (f"Mock protocol: one minified JSON object only. Use stage_change. "
                f"For {name}_service.py, stage symbol {name}_handle with mode preview and tags safe,small. "
                "Schema: tool and arguments containing target object (path,symbol), mode string, tags array.",
                {"tool":"stage_change","arguments":{"target":{"path":f"{name}_service.py","symbol":f"{name}_handle"},
                                                       "mode":"preview","tags":["safe","small"]}}, {})
    for family, fn in (("c_tool_batch",tool_batch),("c_tool_single",tool_single),
                       ("c_tool_schedule",tool_schedule),("c_tool_report",tool_report),
                       ("c_tool_plan",tool_plan),("c_tool_nested",tool_nested)):
        add(json_family("Tool-call formatting", family, fn))

    # Code explanation with exact JSON values and a short explanation string.
    def explain_unpack(name, index):
        first, second = index + 3, index + 8
        snippet = f"pair = ({first}, {second})\nleft, right = pair\nprint(right - left)"
        return ("Trace the code. Return only JSON with exactly output (integer) and explanation (nonempty string).\n\n"+snippet,
                {"output":second-first,"explanation":"Tuple unpacking assigns each element before the subtraction."},
                {"snippet":snippet})
    def explain_truth(name, index):
        snippet = f"values = [0, {index+2}, 0]\nprint(any(values) and not all(values))"
        return ("Trace the code. Return only JSON with exactly output (boolean) and explanation (nonempty string).\n\n"+snippet,
                {"output":True,"explanation":"At least one element is truthy, but the zero elements make all false."},
                {"snippet":snippet})
    add(json_family("Code explanation","c_explain_unpack",explain_unpack))
    add(json_family("Code explanation","c_explain_truth",explain_truth))

    # Simple coding and bug-fixing rehearsal, intentionally different from benchmarks.
    add(code_family("Simple coding","c_simple_enumerate",
        "Write @N@_enumerate_values(items, first): return [index,item] pairs, numbering items consecutively from first.",
        "def @N@_enumerate_values(items, first):\n    return [[first + offset, item] for offset, item in enumerate(items)]",
        [case("@N@_enumerate_values", [["x","y"],5], [[5,"x"],[6,"y"]]),
         case("@N@_enumerate_values", [[],3], []),
         case("@N@_enumerate_values", [["solo"],-2], [[-2,"solo"]])]))
    add(code_family("Simple coding","c_simple_tiles",
        "Write @N@_tile_counts(length, tile): return how many complete positive-width tiles fit and the unused remainder as [count,remainder].",
        "def @N@_tile_counts(length, tile):\n    return [length // tile, length % tile]",
        [case("@N@_tile_counts", [23,6], [3,5]), case("@N@_tile_counts", [4,9], [0,4]),
         case("@N@_tile_counts", [16,4], [4,0])], difficulty="easy"))
    add(code_family("Bug fixing","c_bug_digits",
        "Fix @N@_digits_count(number) for nonnegative integers; zero has one decimal digit.",
        "def @N@_digits_count(number):\n    if number == 0:\n        return 1\n    count = 0\n    while number:\n        count += 1\n        number //= 10\n    return count",
        [case("@N@_digits_count", [0], 1), case("@N@_digits_count", [9090], 4),
         case("@N@_digits_count", [7], 1)],
        broken="def @N@_digits_count(number):\n    count = 0\n    while number:\n        count += 1\n        number //= 10\n    return count"))
    add(code_family("Bug fixing","c_bug_ranking",
        "Fix @N@_rank(points): return gold for at least 90, silver for at least 70, and bronze otherwise.",
        "def @N@_rank(points):\n    if points >= 90:\n        return 'gold'\n    if points >= 70:\n        return 'silver'\n    return 'bronze'",
        [case("@N@_rank", [94], "gold"), case("@N@_rank", [70], "silver"),
         case("@N@_rank", [20], "bronze")],
        broken="def @N@_rank(points):\n    if points >= 70:\n        return 'silver'\n    if points >= 90:\n        return 'gold'\n    return 'bronze'"))
    add(code_family("Multi-step debugging","c_debug_polygon",
        "Fix both functions. @N@_double_area computes twice the rectangle area; @N@_is_large checks whether actual area is at least limit.",
        "def @N@_double_area(width, height):\n    return 2 * width * height\n\ndef @N@_is_large(width, height, limit):\n    return @N@_double_area(width, height) >= 2 * limit",
        [case("@N@_double_area", [3,5], 30), case("@N@_is_large", [3,5,15], True),
         case("@N@_is_large", [3,5,16], False)],
        broken="def @N@_double_area(width, height):\n    return width + height\n\ndef @N@_is_large(width, height, limit):\n    return @N@_double_area(width, height) > limit"))
    add(code_family("Multi-step debugging","c_debug_scores",
        "Fix both functions. @N@_bonus_points adds two points to nonnegative scores only; @N@_best_bonus returns the maximum result or zero for empty input.",
        "def @N@_bonus_points(scores):\n    return [score + 2 for score in scores if score >= 0]\n\ndef @N@_best_bonus(scores):\n    values = @N@_bonus_points(scores)\n    return max(values) if values else 0",
        [case("@N@_bonus_points", [[-1,0,5]], [2,7]),
         case("@N@_best_bonus", [[-1,0,5]], 7), case("@N@_best_bonus", [[]], 0)],
        broken="def @N@_bonus_points(scores):\n    return [score + 2 for score in scores]\n\ndef @N@_best_bonus(scores):\n    return min(@N@_bonus_points(scores))"))
    add(code_family("Test-driven fixing","c_tdd_overlap",
        "Read the cases before fixing @N@_overlap_days(a_start,a_end,b_start,b_end). Ranges are inclusive integer days; return the number of common days, or zero.",
        "def @N@_overlap_days(a_start, a_end, b_start, b_end):\n    start = max(a_start, b_start)\n    end = min(a_end, b_end)\n    return max(0, end - start + 1)",
        [case("@N@_overlap_days", [1,5,4,8], 2),
         case("@N@_overlap_days", [1,2,5,6], 0), case("@N@_overlap_days", [3,3,3,3], 1)],
        broken="def @N@_overlap_days(a_start, a_end, b_start, b_end):\n    return min(a_end, b_end) - max(a_start, b_start)"))
    add(code_family("Test-driven fixing","c_tdd_bounded_add",
        "Read the cases before fixing @N@_bounded_add(value, delta, ceiling): add delta and cap only values above ceiling; negative results remain negative.",
        "def @N@_bounded_add(value, delta, ceiling):\n    return min(value + delta, ceiling)",
        [case("@N@_bounded_add", [8,5,10], 10),
         case("@N@_bounded_add", [3,-7,10], -4), case("@N@_bounded_add", [5,2,10], 7)],
        broken="def @N@_bounded_add(value, delta, ceiling):\n    return max(0, min(value + delta, ceiling))"))

    # Repository reasoning: all snippets use new files/names and exact outputs.
    def repo_callback(name,index):
        files={f"{name}_callbacks.py":f"def double(value):\n    return value * 2\n",
               f"{name}_runner.py":f"from {name}_callbacks import double\ndef apply(value, fn=double):\n    return fn(value) + 1\n",
               f"{name}_app.py":f"from {name}_runner import apply\nprint(apply({index+4}))\n"}
        output=2*(index+4)+1
        return ("Virtual repository:\n"+'\n'.join(f'{p}:\n{s.rstrip()}' for p,s in files.items())+
                "\nWhat integer does the app print? Return JSON with exactly output (integer) and explanation (string).",
                {"output":output,"explanation":"The default callback doubles the input before the runner adds one."},
                {"files":files,"entry":f"{name}_app.py"})
    def repo_alias(name,index):
        files={f"{name}_codec.py":"def wrap(value):\n    return '[' + value + ']'\n",
               f"{name}_bridge.py":f"from {name}_codec import wrap as decorate\ndef render(value):\n    return decorate(value)\n",
               f"{name}_app.py":f"from {name}_bridge import render\nprint(render('{name}'))\n"}
        return ("Virtual repository:\n"+'\n'.join(f'{p}:\n{s.rstrip()}' for p,s in files.items())+
                "\nWhat does the app print? Return JSON with exactly output (string) and explanation (string).",
                {"output":f"[{name}]","explanation":"The renamed import still refers to the wrapper in the codec module."},
                {"files":files,"entry":f"{name}_app.py"})
    def repo_exception(name,index):
        files={f"{name}_reader.py":"def load():\n    raise KeyError('missing')\n",
               f"{name}_service.py":f"from {name}_reader import load\ndef resolve():\n    try:\n        return load()\n    except KeyError:\n        raise ValueError('unavailable')\n",
               f"{name}_app.py":f"from {name}_service import resolve\ntry:\n    resolve()\nexcept ValueError as error:\n    print(str(error) + '-{index+1}')\n"}
        return ("Virtual repository:\n"+'\n'.join(f'{p}:\n{s.rstrip()}' for p,s in files.items())+
                "\nWhat does the app print? Return JSON with exactly output (string) and explanation (string).",
                {"output":f"unavailable-{index+1}","explanation":"The service translates a KeyError into ValueError, which the app handles."},
                {"files":files,"entry":f"{name}_app.py"})
    def repo_config(name,index):
        files={f"{name}_defaults.py":f"LIMIT = {index+10}\n",
               f"{name}_settings.py":f"from {name}_defaults import LIMIT\nACTIVE = LIMIT + 2\n",
               f"{name}_app.py":f"from {name}_settings import ACTIVE\nprint(ACTIVE)\n"}
        return ("Virtual repository:\n"+'\n'.join(f'{p}:\n{s.rstrip()}' for p,s in files.items())+
                "\nWhat integer does the app print? Return JSON with exactly output (integer) and explanation (string).",
                {"output":index+12,"explanation":"The settings module derives its active limit from the defaults constant."},
                {"files":files,"entry":f"{name}_app.py"})
    def repo_shadow(name,index):
        files={f"{name}_constants.py":"SCALE = 10\n",
               f"{name}_app.py":f"from {name}_constants import SCALE\ndef scale(value, SCALE):\n    return value + SCALE\nprint(scale({index+1}, 3))\n"}
        return ("Virtual repository:\n"+'\n'.join(f'{p}:\n{s.rstrip()}' for p,s in files.items())+
                "\nWhat integer does the app print? Return JSON with exactly output (integer) and explanation (string).",
                {"output":index+4,"explanation":"The function parameter shadows the imported constant inside the call."},
                {"files":files,"entry":f"{name}_app.py"})
    def repo_registry(name,index):
        files={f"{name}_catalog.py":"CHECKS = []\ndef register(fn):\n    CHECKS.append(fn)\n    return fn\n",
               f"{name}_plugins.py":f"from {name}_catalog import register\n@register\ndef score(value):\n    return value + {index+3}\n",
               f"{name}_app.py":f"import {name}_plugins\nfrom {name}_catalog import CHECKS\nprint(CHECKS[0]({index+5}))\n"}
        return ("Virtual repository:\n"+'\n'.join(f'{p}:\n{s.rstrip()}' for p,s in files.items())+
                "\nWhat integer does the app print? Return JSON with exactly output (integer) and explanation (string).",
                {"output":2*index+8,"explanation":"The decorator registers the score callback during import before the app invokes it."},
                {"files":files,"entry":f"{name}_app.py"})
    for family, fn in (("c_repo_callback",repo_callback),("c_repo_alias",repo_alias),
                       ("c_repo_exception",repo_exception),("c_repo_config",repo_config),
                       ("c_repo_shadow",repo_shadow),("c_repo_registry",repo_registry)):
        add(json_family("Small repository reasoning",family,fn))

    assert len(rows) == 120, len(rows)
    train = [row for row in rows if row["family"] not in VALIDATION_FAMILIES]
    validation = [row for row in rows if row["family"] in VALIDATION_FAMILIES]
    assert len(train) == 88 and len(validation) == 32
    return train, validation


def main():
    train, validation = build()
    for name, rows in (("experiment_c_train.jsonl", train),
                       ("experiment_c_validation.jsonl", validation)):
        (HERE / name).write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
                                 encoding="utf-8")
    print(f"Wrote {len(train)} training and {len(validation)} validation examples")


if __name__ == "__main__":
    main()
