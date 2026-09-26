#!/usr/bin/env python3
"""Deterministically author 200 D1 examples from 100 distinct task families.

Each family has two related but separately checked instances. No model is used.
The companion validator executes every reference and checks contamination.
"""

import difflib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
NAMES = ("copper", "willow")
SOURCE = "experiment_d_authored_v1"
SYSTEM = {
    "Simple coding": "Return only raw Python function definitions; no prose, fences, imports or example calls.",
    "Bug fixing": "Fix the Python code. Return only raw function definitions; no prose or fences.",
    "Multi-step debugging": "Fix every described issue. Return only raw Python function definitions.",
    "Test-driven fixing": "Read every case and return only raw Python function definitions.",
    "Patch generation": "Return only one raw, minimal unified diff with valid file headers and hunk counts; no prose or fences.",
    "Tool-call formatting": "Return one bare JSON object and nothing else; no prose or fences.",
    "Code explanation": "Return one bare JSON object with exactly output and reason; no prose or fences.",
    "Small repository reasoning": "Return one bare JSON object with exactly output and reason; no prose or fences.",
}


def render(value, name, index):
    return value.replace("@N@", name).replace("@I@", str(index))


def row(category, family, prompt, answer, checks, difficulty=None):
    if difficulty is None:
        difficulty = ("easy" if category in {"Simple coding","Bug fixing"} else
                      "hard" if category in {"Small repository reasoning","Multi-step debugging"} else
                      "medium")
    return {
        "messages": [
            {"role": "system", "content": SYSTEM[category]},
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": answer},
        ],
        "category": category, "source": SOURCE, "difficulty": difficulty,
        "family": family, "response_mode": checks["response_mode"],
        "contract_version": "D1", "checks": checks,
    }


def code_case(function, args, expected, unchanged=False):
    case = {"function": function, "args": args, "expected": expected}
    if unchanged:
        case["unchanged_args"] = True
    return case


def code_examples():
    """Eight genuinely different families in each of four rehearsal categories."""
    specs = [
        # Category, family, requested behavior, answer, cases, optional broken code.
        ("Simple coding", "d_simple_weave", "Write @N@_weave(a,b): alternate values from equally long lists, starting with a; do not mutate either input.",
         "def @N@_weave(a,b):\n    return [item for pair in zip(a,b) for item in pair]",
         [("@N@_weave", [[1,2],[7,8]], [1,7,2,8]), ("@N@_weave", [[],[]], [])], None),
        ("Simple coding", "d_simple_prefix_products", "Write @N@_prefix_products(numbers): return cumulative products; the empty list returns [].",
         "def @N@_prefix_products(numbers):\n    product = 1\n    result = []\n    for number in numbers:\n        product *= number\n        result.append(product)\n    return result",
         [("@N@_prefix_products", [[2,3,4]], [2,6,24]), ("@N@_prefix_products", [[-2,0,4]], [-2,0,0]), ("@N@_prefix_products", [[]], [])], None),
        ("Simple coding", "d_simple_token_lengths", "Write @N@_token_lengths(text): split on arbitrary whitespace and return each token's length in order.",
         "def @N@_token_lengths(text):\n    return [len(token) for token in text.split()]",
         [("@N@_token_lengths", ["a  moon\tstar"], [1,4,4]), ("@N@_token_lengths", ["   "], [])], None),
        ("Simple coding", "d_simple_pairwise_max", "Write @N@_pairwise_max(left,right): for equally long integer lists, return the larger element at each position.",
         "def @N@_pairwise_max(left,right):\n    return [max(a,b) for a,b in zip(left,right)]",
         [("@N@_pairwise_max", [[2,8],[5,3]], [5,8]), ("@N@_pairwise_max", [[],[]], [])], None),
        ("Simple coding", "d_simple_even_position_sum", "Write @N@_even_position_sum(values): sum elements at zero-based even positions, including index zero.",
         "def @N@_even_position_sum(values):\n    return sum(values[::2])",
         [("@N@_even_position_sum", [[9,2,4,8]], 13), ("@N@_even_position_sum", [[]], 0)], None),
        ("Simple coding", "d_simple_common_prefix", "Write @N@_common_prefix(a,b): return the longest shared prefix of two strings.",
         "def @N@_common_prefix(a,b):\n    out = []\n    for x,y in zip(a,b):\n        if x != y:\n            break\n        out.append(x)\n    return ''.join(out)",
         [("@N@_common_prefix", ["cable","cabin"], "cab"), ("@N@_common_prefix", ["x","y"], "")], None),
        ("Simple coding", "d_simple_digit_weight", "Write @N@_digit_weight(text): return the sum of decimal digits in text, ignoring all nondigits.",
         "def @N@_digit_weight(text):\n    return sum(int(ch) for ch in text if '0' <= ch <= '9')",
         [("@N@_digit_weight", ["a7b2"], 9), ("@N@_digit_weight", ["none"], 0)], None),
        ("Simple coding", "d_simple_staircase", "Write @N@_staircase(n): for nonnegative n return [[0],[0,1],...,[0,...,n-1]].",
         "def @N@_staircase(n):\n    return [list(range(i)) for i in range(1,n+1)]",
         [("@N@_staircase", [3], [[0],[0,1],[0,1,2]]), ("@N@_staircase", [0], [])], None),

        ("Bug fixing", "d_bug_sign_count", "Fix @N@_sign_count: count negative integers, including negative values after zero.",
         "def @N@_sign_count(values):\n    return sum(1 for value in values if value < 0)",
         [("@N@_sign_count", [[-3,0,-2,5]], 2), ("@N@_sign_count", [[]], 0)],
         "def @N@_sign_count(values):\n    return sum(1 for value in values if value <= 0)"),
        ("Bug fixing", "d_bug_mirror_pair", "Fix @N@_mirror_pair: return whether two strings are reverses of one another, respecting case.",
         "def @N@_mirror_pair(left,right):\n    return left[::-1] == right",
         [("@N@_mirror_pair", ["Ab","bA"], True), ("@N@_mirror_pair", ["ab","ab"], False)],
         "def @N@_mirror_pair(left,right):\n    return left == right"),
        ("Bug fixing", "d_bug_list_partition", "Fix @N@_partition: return [values below pivot, values at or above pivot], retaining input order and without mutation.",
         "def @N@_partition(values,pivot):\n    return [[v for v in values if v < pivot],[v for v in values if v >= pivot]]",
         [("@N@_partition", [[4,2,4,1],4], [[2,1],[4,4]]), ("@N@_partition", [[],3], [[],[]])],
         "def @N@_partition(values,pivot):\n    return [[v for v in values if v <= pivot],[v for v in values if v > pivot]]"),
        ("Bug fixing", "d_bug_key_total", "Fix @N@_key_total: sum values of a list of [key,amount] rows for the requested key; rows with other keys remain irrelevant.",
         "def @N@_key_total(rows,key):\n    return sum(amount for name,amount in rows if name == key)",
         [("@N@_key_total", [[["A",3],["B",9],["A",2]],"A"], 5), ("@N@_key_total", [[],"Z"], 0)],
         "def @N@_key_total(rows,key):\n    return sum(amount for name,amount in rows if name != key)"),
        ("Bug fixing", "d_bug_middle_gap", "Fix @N@_middle_gap: return max(values)-min(values) for nonempty lists, including negative-only lists.",
         "def @N@_middle_gap(values):\n    return max(values) - min(values)",
         [("@N@_middle_gap", [[-9,-2,-5]], 7), ("@N@_middle_gap", [[4]], 0)],
         "def @N@_middle_gap(values):\n    return max(values) + min(values)"),
        ("Bug fixing", "d_bug_suffix_filter", "Fix @N@_suffix_filter(words,suffix): retain words ending with suffix, case sensitively, in original order.",
         "def @N@_suffix_filter(words,suffix):\n    return [word for word in words if word.endswith(suffix)]",
         [("@N@_suffix_filter", [["sing","ring","singer"],"ing"], ["sing","ring"]), ("@N@_suffix_filter", [[],"x"], [])],
         "def @N@_suffix_filter(words,suffix):\n    return [word for word in words if word.startswith(suffix)]"),
        ("Bug fixing", "d_bug_scale_zero", "Fix @N@_scale(values,factor): multiply every element including zeros; preserve list length and input.",
         "def @N@_scale(values,factor):\n    return [value * factor for value in values]",
         [("@N@_scale", [[0,2,-3],4], [0,8,-12]), ("@N@_scale", [[],2], [])],
         "def @N@_scale(values,factor):\n    return [value * factor for value in values if value]"),
        ("Bug fixing", "d_bug_pair_alignment", "Fix @N@_pair_alignment(left,right): count positions with equal values in equally long lists.",
         "def @N@_pair_alignment(left,right):\n    return sum(a == b for a,b in zip(left,right))",
         [("@N@_pair_alignment", [[1,2,3],[1,9,3]], 2), ("@N@_pair_alignment", [[],[]], 0)],
         "def @N@_pair_alignment(left,right):\n    return sum(a != b for a,b in zip(left,right))"),

        ("Multi-step debugging", "d_debug_range_sum", "Fix both issues: for inclusive integer endpoints in either order, sum every integer between them; equal endpoints return that endpoint.",
         "def @N@_range_sum(a,b):\n    low,high = min(a,b),max(a,b)\n    return sum(range(low,high+1))",
         [("@N@_range_sum", [2,4], 9), ("@N@_range_sum", [4,2], 9), ("@N@_range_sum", [-1,-1], -1)],
         "def @N@_range_sum(a,b):\n    return sum(range(a,b))"),
        ("Multi-step debugging", "d_debug_assignments", "Fix both issues: parse semicolon-separated key=value assignments into a dictionary; trim surrounding whitespace, ignore empty segments, and let later keys overwrite earlier ones.",
         "def @N@_assignments(text):\n    result = {}\n    for segment in text.split(';'):\n        if not segment.strip():\n            continue\n        key,value = segment.split('=',1)\n        result[key.strip()] = value.strip()\n    return result",
         [("@N@_assignments", ["a=1; ; b = 2;a=3"], {"a":"3","b":"2"}), ("@N@_assignments", [""], {})],
         "def @N@_assignments(text):\n    result = {}\n    for segment in text.split(';'):\n        key,value = segment.split('=')\n        result[key] = value\n    return result"),
        ("Multi-step debugging", "d_debug_pairs", "Fix both issues: return products of successive complete pairs of numbers; ignore one trailing unpaired number and allow empty input.",
         "def @N@_pair_products(values):\n    return [values[i] * values[i+1] for i in range(0,len(values)-1,2)]",
         [("@N@_pair_products", [[2,3,4,5,9]], [6,20]), ("@N@_pair_products", [[]], [])],
         "def @N@_pair_products(values):\n    return [values[i] + values[i+1] for i in range(0,len(values),2)]"),
        ("Multi-step debugging", "d_debug_mode_flags", "Fix both issues: process the whole list; output 'high' for >=10, 'low' for <0, and 'mid' otherwise.",
         "def @N@_bands(values):\n    result = []\n    for value in values:\n        result.append('high' if value >= 10 else 'low' if value < 0 else 'mid')\n    return result",
         [("@N@_bands", [[-1,0,10,5]], ["low","mid","high","mid"]), ("@N@_bands", [[]], [])],
         "def @N@_bands(values):\n    out = []\n    for value in values[:-1]:\n        out.append('high' if value > 10 else 'mid')\n    return out"),
        ("Multi-step debugging", "d_debug_column_sum", "Fix both issues: sum every column of a nonempty rectangular numeric grid; zero-width rows return [].",
         "def @N@_column_sums(grid):\n    return [sum(row[j] for row in grid) for j in range(len(grid[0]))]",
         [("@N@_column_sums", [[[1,2],[3,4],[5,6]]], [9,12]), ("@N@_column_sums", [[[]]], [])],
         "def @N@_column_sums(grid):\n    return [sum(grid[j]) for j in range(len(grid))]"),
        ("Multi-step debugging", "d_debug_clamp_series", "Fix both issues: clamp each value to inclusive [low,high] and preserve order, including empty input.",
         "def @N@_clamp_series(values,low,high):\n    return [min(high,max(low,value)) for value in values]",
         [("@N@_clamp_series", [[-3,2,12],0,9], [0,2,9]), ("@N@_clamp_series", [[],0,1], [])],
         "def @N@_clamp_series(values,low,high):\n    return [max(high,min(low,value)) for value in sorted(values)]"),
        ("Multi-step debugging", "d_debug_word_counts", "Fix both issues: count case-insensitive whitespace-delimited words and ignore empty whitespace; return a dictionary.",
         "def @N@_word_counts(text):\n    result = {}\n    for word in text.lower().split():\n        result[word] = result.get(word,0) + 1\n    return result",
         [("@N@_word_counts", ["A b A"], {"a":2,"b":1}), ("@N@_word_counts", ["  "], {})],
         "def @N@_word_counts(text):\n    result = {}\n    for word in text.split(' '):\n        result[word] = 1\n    return result"),
        ("Multi-step debugging", "d_debug_diagonal", "Fix both issues: for a square grid, return the sum of the anti-diagonal; handle one-cell grids.",
         "def @N@_anti_diagonal(grid):\n    n = len(grid)\n    return sum(grid[i][n-1-i] for i in range(n))",
         [("@N@_anti_diagonal", [[[1,2],[3,4]]], 5), ("@N@_anti_diagonal", [[[7]]], 7)],
         "def @N@_anti_diagonal(grid):\n    return sum(grid[i][i] for i in range(len(grid)-1))"),

        ("Test-driven fixing", "d_tdd_divisible_flags", "Tests: input [2,3,4], divisor 2 -> [true,false,true]; empty list -> []; divisor is positive. Write @N@_divisible_flags.",
         "def @N@_divisible_flags(values,divisor):\n    return [value % divisor == 0 for value in values]",
         [("@N@_divisible_flags", [[2,3,4],2], [True,False,True]), ("@N@_divisible_flags", [[],5], [])], None),
        ("Test-driven fixing", "d_tdd_remove_at", "Tests: [5,8,9], index 1 -> [5,9]; index 0 removes first; negative indices follow Python. Write @N@_remove_at without changing input.",
         "def @N@_remove_at(values,index):\n    position = index % len(values)\n    return values[:position] + values[position+1:]",
         [("@N@_remove_at", [[5,8,9],1], [5,9]), ("@N@_remove_at", [[5,8,9],-1], [5,8])], None),
        ("Test-driven fixing", "d_tdd_product_except", "Tests: [2,3,4] -> [12,8,6]; [0,5] -> [5,0]; [] -> []. Write @N@_other_products.",
         "def @N@_other_products(values):\n    result = []\n    for i in range(len(values)):\n        product = 1\n        for value in values[:i] + values[i+1:]:\n            product *= value\n        result.append(product)\n    return result",
         [("@N@_other_products", [[2,3,4]], [12,8,6]), ("@N@_other_products", [[0,5]], [5,0]), ("@N@_other_products", [[]], [])], None),
        ("Test-driven fixing", "d_tdd_first_long", "Tests: ['a','bbb','cc'], minlen 2 -> 'bbb'; no match -> null. Write @N@_first_long.",
         "def @N@_first_long(words,minlen):\n    for word in words:\n        if len(word) >= minlen:\n            return word\n    return None",
         [("@N@_first_long", [["a","bbb","cc"],2], "bbb"), ("@N@_first_long", [["a"],3], None)], None),
        ("Test-driven fixing", "d_tdd_transpose", "Tests: [[1,2],[3,4]] -> [[1,3],[2,4]]; [[],[]] -> []. Write @N@_transpose for nonempty rectangular grids.",
         "def @N@_transpose(grid):\n    return [list(column) for column in zip(*grid)]",
         [("@N@_transpose", [[[1,2],[3,4]]], [[1,3],[2,4]]), ("@N@_transpose", [[[],[]]], [])], None),
        ("Test-driven fixing", "d_tdd_exactly_one", "Tests: [false,true,false] -> true; [true,true] -> false; [] -> false. Write @N@_exactly_one.",
         "def @N@_exactly_one(flags):\n    return sum(bool(flag) for flag in flags) == 1",
         [("@N@_exactly_one", [[False,True,False]], True), ("@N@_exactly_one", [[True,True]], False), ("@N@_exactly_one", [[]], False)], None),
        ("Test-driven fixing", "d_tdd_nonempty_lines", "Tests: 'a\\n\\nb' -> ['a','b']; ' ' -> [' ']; '' -> []. Write @N@_nonempty_lines, removing empty lines but preserving spaces.",
         "def @N@_nonempty_lines(text):\n    return [line for line in text.splitlines() if line != '']",
         [("@N@_nonempty_lines", ["a\n\nb"], ["a","b"]), ("@N@_nonempty_lines", [" "], [" "]), ("@N@_nonempty_lines", [""], [])], None),
        ("Test-driven fixing", "d_tdd_weighted_total", "Tests: values [2,4], weights [3,5] -> 26; both empty -> 0. Write @N@_weighted_total for equal-length lists.",
         "def @N@_weighted_total(values,weights):\n    return sum(value*weight for value,weight in zip(values,weights))",
         [("@N@_weighted_total", [[2,4],[3,5]], 26), ("@N@_weighted_total", [[],[]], 0)], None),
    ]
    rows = []
    for category, family, instruction, answer, cases, broken in specs:
        for index, name in enumerate(NAMES):
            prompt = render(instruction, name, index)
            if broken:
                prompt += "\n\nCurrent implementation:\n" + render(broken, name, index)
            prompt += "\nReturn only raw Python function definitions, with no imports, prose, fences or example calls."
            concrete = [code_case(render(fn,name,index),args,expected,True) for fn,args,expected in cases]
            rows.append(row(category,family,prompt,render(answer,name,index)+"\n",
                            {"response_mode":"python_code","cases":concrete}))
    return rows


def patch_examples():
    """Twenty distinct edit operations; difflib authors valid minimal hunks."""
    specs = [
        ("d_patch_divisor", "Use floor division so the return is an integer.", "return total / count", "return total // count", "def calc(total,count)", [[9,2,4],[8,2,4]]),
        ("d_patch_toggle", "Toggle the boolean before returning it.", "return enabled", "return not enabled", "def calc(enabled)", [[True,False],[False,True]]),
        ("d_patch_strip_suffix", "Remove one trailing exclamation mark if present.", "return text.rstrip('!')", "return text[:-1] if text.endswith('!') else text", "def calc(text)", [["wow!!","wow!"],["plain","plain"]]),
        ("d_patch_count_spaces", "Count literal ASCII spaces, including repeated spaces.", "return len(text.split(' '))", "return text.count(' ')", "def calc(text)", [["a  b",2],["ab",0]]),
        ("d_patch_abs_difference", "Return absolute difference of two integers.", "return left - right", "return abs(left - right)", "def calc(left,right)", [[2,8,6],[9,4,5]]),
        ("d_patch_remove_terminal", "Remove only the last element, preserving earlier equal elements.", "return values[:-2]", "return values[:-1]", "def calc(values)", [[[3,3,4],[3,3]],[[7],[]]]),
        ("d_patch_leap_guard", "A year is leap when divisible by 4 except centuries not divisible by 400.", "return year % 4 == 0", "return year % 400 == 0 or (year % 4 == 0 and year % 100 != 0)", "def calc(year)", [[1900,False],[2000,True],[2024,True]]),
        ("d_patch_floor_to_even", "Return the largest even integer no greater than the input.", "return value - 1", "return value - (value % 2)", "def calc(value)", [[6,6],[7,6],[-1,-2]]),
        ("d_patch_join_path", "Join path segments with exactly one slash, after trimming outer slashes from each segment.", "return left + '/' + right", "return left.strip('/') + '/' + right.strip('/')", "def calc(left,right)", [["a/","/b","a/b"],["a","b","a/b"]]),
        ("d_patch_casefold_match", "Compare strings case insensitively using casefold.", "return left == right", "return left.casefold() == right.casefold()", "def calc(left,right)", [["ABC","abc",True],["a","b",False]]),
        ("d_patch_blank_vs_none", "Return the fallback only when the value is None; an empty string is valid.", "return value or fallback", "return fallback if value is None else value", "def calc(value,fallback)", [["","x",""],[None,"x","x"]]),
        ("d_patch_trim_one", "Trim only one leading newline, leaving any further newline intact.", "return text.lstrip('\\n')", "return text[1:] if text.startswith('\\n') else text", "def calc(text)", [["\n\na","\na"],["a","a"]]),
        ("d_patch_insert_guard", "Return zero when the list is empty; otherwise return its first member.", "return values[0]", "return values[0] if values else 0", "def calc(values)", [[[],0],[[6],6]]),
        ("d_patch_delete_duplicate", "The result should contain the input value once, not twice; remove the redundant append.", "out = [value]\n    out.append(value)\n    return out", "out = [value]\n    return out", "def calc(value)", [[3,[3]],[0,[0]]]),
        ("d_patch_newline_exact", "Add exactly one terminal newline if absent; leave existing newline unchanged.", "return text + '\\n'", "return text if text.endswith('\\n') else text + '\\n'", "def calc(text)", [["a\n","a\n"],["b","b\n"]]),
        ("d_patch_multiline_limit", "Clamp the total to the quota, but never return a negative number.", "total = amount + bonus\n    return min(total, quota)", "total = amount + bonus\n    bounded = max(0, total)\n    return min(bounded, quota)", "def calc(amount,bonus,quota)", [[-5,2,10,0],[8,4,10,10]]),
        ("d_patch_multi_hunk", "In calc, count vowels case insensitively and include y as a vowel. Preserve the normalization line and helper.", "vowels = 'aeiou'\n    normalized = text.lower()\n    return sum(ch in vowels for ch in text)", "vowels = 'aeiouy'\n    normalized = text.lower()\n    return sum(ch in vowels for ch in normalized)", "def calc(text)", [["Yay",3],["BCD",0]]),
        ("d_patch_whitespace", "Preserve the two spaces before the comment; change the increment from two to one.", "return value + 2  # increment", "return value + 1  # increment", "def calc(value)", [[1,2],[0,1]]),
        ("d_patch_sort_stable", "Return a new list sorted by the absolute value of each integer, preserving stable ties.", "return sorted(values)", "return sorted(values, key=abs)", "def calc(values)", [[[-3,2,-2],[2,-2,-3]],[[0], [0]]]),
        ("d_patch_ordinal_limit", "Return only the first n items, including the case n is zero.", "return values[:n+1]", "return values[:n]", "def calc(values,n)", [[[4,5,6],2,[4,5]],[[4,5],0,[]]]),
    ]
    rows = []
    for family, instruction, old_body, new_body, signature, case_values in specs:
        for index,name in enumerate(NAMES):
            path = f"{name}_{family[2:]}.py"
            old = f"{signature}:\n    {old_body}\n\ndef retain(value):\n    return value * 3\n"
            new = f"{signature}:\n    {new_body}\n\ndef retain(value):\n    return value * 3\n"
            # A few operations deliberately require insertion, deletion or more than one hunk.
            context = 0 if family == "d_patch_multi_hunk" else 2
            diff = "".join(difflib.unified_diff(old.splitlines(keepends=True),new.splitlines(keepends=True),
                                            fromfile=f"a/{path}",tofile=f"b/{path}",n=context))
            cases = [code_case("calc",values[:-1],values[-1],True) for values in case_values]
            cases.append(code_case("retain",[4],12))
            prompt = (f"Edit {path}. {instruction} Preserve retain unchanged. Return only a raw, minimal "
                      f"unified diff with exact --- a/{path} and +++ b/{path} headers and correct hunk counts; "
                      f"no prose or fences.\n\nCurrent file:\n{old}")
            rows.append(row("Patch generation",family,prompt,diff,
                            {"response_mode":"unified_diff","path":path,"source":old,
                             "expected_source":new,"preserve_functions":["retain"],"cases":cases}))
    return rows


def schema(value):
    if isinstance(value, dict):
        return "{" + ", ".join(f"{key}: {schema(item)}" for key,item in value.items()) + "}"
    if isinstance(value, list):
        return "array<" + (schema(value[0]) if value else "any") + ">"
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    return "string"


def tool_examples():
    """Eighteen mock API operations, each with a distinct argument contract."""
    specs = [
        ("d_tool_locate_module","Find the module that defines @N@_parser.","locate_module",{"symbol":"@N@_parser"},"list_packages"),
        ("d_tool_compare_revisions","Compare revisions @N@_r1 and @N@_r2, with context lines 3.","compare_revisions",{"base":"@N@_r1","head":"@N@_r2","context":3},"show_revision"),
        ("d_tool_select_tests","Select suites smoke and @N@_unit in that order; require strict mode.","select_tests",{"suites":["smoke","@N@_unit"],"strict":True},"run_test"),
        ("d_tool_open_span","Open @N@.py from line 5 through line 12, inclusive.","open_span",{"file":"@N@.py","span":{"start":5,"end":12}},"open_file"),
        ("d_tool_trace_symbol","Trace symbol @N@_handle in package @N@pkg, depth 2.","trace_symbol",{"target":{"package":"@N@pkg","symbol":"@N@_handle"},"depth":2},"locate_module"),
        ("d_tool_pin_dependency","Pin package @N@lib at version 2.@I@.4; allow prerelease false.","pin_dependency",{"package":"@N@lib","version":"2.@I@.4","allow_prerelease":False},"list_dependencies"),
        ("d_tool_plan_review","Plan reviewing @N@_api then @N@_cli, each with mode read.","plan_review",{"steps":[{"path":"@N@_api.py","mode":"read"},{"path":"@N@_cli.py","mode":"read"}]},"review_file"),
        ("d_tool_record_measurement","Record latency 2.5 ms for @N@_worker with tags stable and small.","record_measurement",{"name":"latency","value":2.5,"unit":"ms","tags":["stable","small"],"owner":"@N@_worker"},"emit_log"),
        ("d_tool_open_ticket","Open issue @N@-17 with priority 2; no assignee is known, so assignee is null.","open_ticket",{"id":"@N@-17","priority":2,"assignee":None},"find_ticket"),
        ("d_tool_filter_cases","Filter case IDs 4 and 7 by labels @N@ and stable; require all labels.","filter_cases",{"ids":[4,7],"filter":{"labels":["@N@","stable"],"match_all":True}},"list_cases"),
        ("d_tool_set_timeout","Set timeout for @N@_job to 45 seconds; apply to retries too.","set_timeout",{"job":"@N@_job","seconds":45,"scope":{"retries":True}},"get_timeout"),
        ("d_tool_queue_checks","Queue checks typecheck, lint and @N@_unit in that order, without execution.","queue_checks",{"checks":["typecheck","lint","@N@_unit"],"execute":False},"run_checks"),
        ("d_tool_find_import","Find importers of @N@.codec, including indirect imports.","find_importers",{"module":"@N@.codec","include_indirect":True},"find_definition"),
        ("d_tool_suggest_edit","Suggest replacing text old@N@ with new@N@ in @N@.txt, but do not apply.","suggest_edit",{"path":"@N@.txt","replacement":{"old":"old@N@","new":"new@N@"},"apply":False},"apply_edit"),
        ("d_tool_label_commit","Label commit @N@123 with labels reviewed and safe in that order.","label_commit",{"commit":"@N@123","labels":["reviewed","safe"]},"inspect_commit"),
        ("d_tool_route_alert","Route alert @N@_warn to channel dev with severity low and muted false.","route_alert",{"alert":"@N@_warn","route":{"channel":"dev","severity":"low","muted":False}},"create_alert"),
        ("d_tool_read_symbols","Read symbols @N@_parse and @N@_write from @N@_core.py; exclude bodies.","read_symbols",{"path":"@N@_core.py","names":["@N@_parse","@N@_write"],"include_bodies":False},"read_file"),
        ("d_tool_plan_migration","Plan migration from v1 to v2 for @N@_db with two phases: inspect then verify.","plan_migration",{"database":"@N@_db","versions":{"from":"v1","to":"v2"},"phases":["inspect","verify"]},"run_migration"),
    ]
    rows = []
    for family, request, tool, arguments, decoy in specs:
        for index,name in enumerate(NAMES):
            args = json.loads(render(json.dumps(arguments),name,index))
            expected = {"tool":tool,"arguments":args}
            prompt = (f"Mock tools available: {tool} and {decoy}. No tool is actually invoked. "
                      f"{render(request,name,index)} Select the correct tool. Reply with exactly one JSON object "
                      f"having only root keys tool (string) and arguments (object). For {tool}, arguments must "
                      f"have exactly this typed schema: {schema(args)}. No other keys, prose or fences. "
                      f"JSON whitespace and object key order are irrelevant.")
            rows.append(row("Tool-call formatting",family,prompt,
                            json.dumps(expected,separators=(",",":")),
                            {"response_mode":"tool_call_json","expected":expected}))
    return rows


def explanation_examples():
    """Fourteen independent Python semantics with explicit D1 reason tags."""
    specs = [
        ("d_explain_negative_floor","floor_division_rounds_down","print(-7 // 3)"),
        ("d_explain_chained_comparison","comparison_chain_is_joint","x = 4\nprint(2 < x < 5)"),
        ("d_explain_tuple_repeat","tuple_repetition_concatenates","item = (3, 8)\nprint(list(item * 2))"),
        ("d_explain_dict_update_order","update_replaces_value","mapping = {'a': 1, 'b': 2}\nmapping.update({'a': 7})\nprint(mapping['a'])"),
        ("d_explain_zip_shortest","zip_stops_at_shortest","print(list(map(list, zip([1, 2, 3], ['x']))))"),
        ("d_explain_empty_all","all_empty_is_true","print(all([]))"),
        ("d_explain_sorted_key","sort_key_uses_length","print(sorted(['pear', 'fig', 'plum'], key=len))"),
        ("d_explain_set_union","union_does_not_mutate_left","left = {1, 2}\nright = left | {3}\nprint([sorted(left), sorted(right)])"),
        ("d_explain_augmented_alias","in_place_list_addition_mutates_alias","a = [2]\nb = a\na += [4]\nprint(b)"),
        ("d_explain_unary_negation","boolean_negation_returns_boolean","print(not 0)"),
        ("d_explain_star_unpack","star_capture_is_list","first, *middle, last = (4, 5, 6, 7)\nprint(middle)"),
        ("d_explain_divmod","divmod_returns_quotient_remainder","print(list(divmod(17, 5)))"),
        ("d_explain_fstring_alignment","fstring_right_aligns","print(f'{5:>3}')"),
        ("d_explain_enumerate_start","enumerate_honors_start","print(list(map(list, enumerate(['x', 'y'], start=4))))"),
    ]
    alternatives = {
        "d_explain_negative_floor":"print(-10 // 4)",
        "d_explain_chained_comparison":"x = 6\nprint(2 < x < 5)",
        "d_explain_tuple_repeat":"item = ('a',)\nprint(list(item * 3))",
        "d_explain_dict_update_order":"mapping = {'x': 4}\nmapping.update({'x': 0, 'y': 8})\nprint(mapping['x'])",
        "d_explain_zip_shortest":"print(list(map(list, zip([1], ['a', 'b']))))",
        "d_explain_empty_all":"values = []\nprint(all(value > 0 for value in values))",
        "d_explain_sorted_key":"print(sorted(['z', 'abcd', 'xy'], key=len))",
        "d_explain_set_union":"left = {4}\nright = left | {5, 6}\nprint([sorted(left), sorted(right)])",
        "d_explain_augmented_alias":"a = ['x']\nb = a\na += ['y', 'z']\nprint(b)",
        "d_explain_unary_negation":"print(not [])",
        "d_explain_star_unpack":"first, *middle, last = (1, 2, 3)\nprint(middle)",
        "d_explain_divmod":"print(list(divmod(20, 6)))",
        "d_explain_fstring_alignment":"print(f'{9:>4}')",
        "d_explain_enumerate_start":"print(list(map(list, enumerate(['a'], start=9))))",
    }
    rows = []
    for family,tag,snippet in specs:
        for index,name in enumerate(NAMES):
            # Two distinct concrete inputs within the same language-behavior family.
            concrete = snippet if index == 0 else alternatives[family]
            lines = concrete.splitlines()
            output_line = next(i for i in range(len(lines)-1,-1,-1) if lines[i].startswith("print("))
            expression = lines[output_line][len("print("):-1]
            lines[output_line] = f"print(json.dumps({expression}))"
            concrete = "import json\n" + "\n".join(lines)
            prompt = ("Trace the Python snippet. Return only bare JSON with exactly output "
                      "(the JSON value represented by printed output) and reason "
                      f"(the literal string {tag!r}); no other keys, prose or fences.\n\n{concrete}")
            # The trusted snippet is run by the validator; this seed is replaced by its oracle.
            rows.append(row("Code explanation",family,prompt,"",
                            {"response_mode":"explanation_json","snippet":concrete,
                             "expected":{"output":None,"reason":tag}}))
    return rows


def repository_examples():
    """Sixteen distinct small cross-file execution paths, all oracle checked."""
    specs = [
        ("d_repo_alias_multiplier","aliased_import_is_used",
         "FACTOR = 3 + @I@\ndef times(x):\n    return x * FACTOR\n",
         "from @N@_core import times as scale\ndef answer():\n    return scale(5)\n",
         "from @N@_api import answer\nprint(json.dumps(answer()))\n"),
        ("d_repo_reexport_constant","reexport_points_to_constant",
         "LIMIT = 9 + @I@\n",
         "from @N@_core import LIMIT as MAX_ITEMS\ndef answer():\n    return MAX_ITEMS - 2\n",
         "from @N@_api import answer\nprint(json.dumps(answer()))\n"),
        ("d_repo_wrapper_order","wrappers_compose_in_call_order",
         "def double(fn):\n    def wrapped(x):\n        return 2 * fn(x)\n    return wrapped\n",
         "from @N@_core import double\ndef base(x):\n    return x + 3 + @I@\nanswer = double(base)\n",
         "from @N@_api import answer\nprint(json.dumps(answer(4)))\n"),
        ("d_repo_registry_order","registration_preserves_insertion_order",
         "handlers = []\ndef register(fn):\n    handlers.append(fn)\n",
         "from @N@_core import handlers, register\nregister(lambda x: x + 2)\nregister(lambda x: x * 3)\ndef answer(x):\n    return [fn(x) for fn in handlers]\n",
         "from @N@_api import answer\nprint(json.dumps(answer(3 + @I@)))\n"),
        ("d_repo_error_fallback","caller_catches_value_error",
         "def parse(text):\n    return int(text)\n",
         "from @N@_core import parse\ndef answer(text):\n    try:\n        return parse(text)\n    except ValueError:\n        return -1\n",
         "from @N@_api import answer\nprint(json.dumps(answer('bad')))\n"),
        ("d_repo_config_layers","later_layer_overrides_earlier",
         "DEFAULT = {'retries': 2, 'mode': 'safe'}\n",
         "from @N@_core import DEFAULT\ndef answer():\n    return {**DEFAULT, **{'retries': 4 + @I@}}\n",
         "from @N@_api import answer\nprint(json.dumps(answer()))\n"),
        ("d_repo_shadowed_parameter","parameter_shadows_imported_name",
         "rate = 10\n",
         "from @N@_core import rate\ndef answer(rate):\n    return rate + 1\n",
         "from @N@_api import answer\nprint(json.dumps(answer(4 + @I@)))\n"),
        ("d_repo_three_step","calls_cross_three_modules",
         "def normalize(x):\n    return x - 1\n",
         "from @N@_core import normalize\ndef answer(x):\n    return normalize(x) ** 2\n",
         "from @N@_api import answer\nprint(json.dumps(answer(5 + @I@)))\n"),
        ("d_repo_class_override","subclass_method_wins",
         "class Base:\n    def score(self,x):\n        return x + 1\n",
         "from @N@_core import Base\nclass Child(Base):\n    def score(self,x):\n        return x * 2\ndef answer(x):\n    return Child().score(x)\n",
         "from @N@_api import answer\nprint(json.dumps(answer(6 + @I@)))\n"),
        ("d_repo_imported_binding","from_import_binding_keeps_old_value",
         "LEVEL = 2\ndef change():\n    global LEVEL\n    LEVEL = 9\n",
         "from @N@_core import LEVEL, change\ndef answer():\n    change()\n    return LEVEL\n",
         "from @N@_api import answer\nprint(json.dumps(answer()))\n"),
        ("d_repo_module_attribute","module_attribute_sees_update",
         "VALUE = 1\ndef change():\n    global VALUE\n    VALUE = 5 + @I@\n",
         "import @N@_core\ndef answer():\n    @N@_core.change()\n    return @N@_core.VALUE\n",
         "from @N@_api import answer\nprint(json.dumps(answer()))\n"),
        ("d_repo_lazy_lookup","import_inside_function_runs_on_call",
         "def label():\n    return 'ready'\n",
         "def answer():\n    from @N@_core import label\n    return label().upper()\n",
         "from @N@_api import answer\nprint(json.dumps(answer()))\n"),
        ("d_repo_exception_translation","api_translates_exception_type",
         "def fetch(key):\n    raise KeyError(key)\n",
         "from @N@_core import fetch\ndef answer():\n    try:\n        fetch('missing')\n    except KeyError:\n        raise ValueError('unavailable')\n",
         "from @N@_api import answer\ntry:\n    answer()\nexcept ValueError as error:\n    print(json.dumps(str(error)))\n"),
        ("d_repo_callback_capture","registered_closure_keeps_multiplier",
         "callbacks = {}\ndef add(name, fn):\n    callbacks[name] = fn\n",
         "from @N@_core import callbacks, add\ndef install(factor):\n    add('main', lambda x: x * factor)\ninstall(4 + @I@)\ndef answer(x):\n    return callbacks['main'](x)\n",
         "from @N@_api import answer\nprint(json.dumps(answer(3)))\n"),
        ("d_repo_pipeline_map","imported_transform_maps_sequence",
         "def transform(x):\n    return x * x\n",
         "from @N@_core import transform\ndef answer(values):\n    return list(map(transform, values))\n",
         "from @N@_api import answer\nprint(json.dumps(answer([1,2,3 + @I@])))\n"),
        ("d_repo_finally_mutation","finally_runs_before_return",
         "events = []\ndef finish():\n    events.append('closed')\n",
         "from @N@_core import events, finish\ndef answer():\n    try:\n        return 7 + @I@\n    finally:\n        finish()\n",
         "from @N@_api import answer, events\nvalue = answer()\nprint(json.dumps([value, events]))\n"),
    ]
    rows = []
    for family,tag,core,api,main in specs:
        for index,name in enumerate(NAMES):
            files = {
                f"{name}_core.py":render(core,name,index),
                f"{name}_api.py":render(api,name,index),
                "main.py":"import json\n" + render(main,name,index),
            }
            prompt = ("The following three virtual Python files are in one directory. Trace `python main.py`. "
                      "Return only bare JSON with exactly output (the JSON value printed by main.py) "
                      f"and reason (the literal string {tag!r}). No other keys, prose or fences.\n\n" +
                      "\n".join(f"# {path}\n{content}" for path,content in files.items()))
            rows.append(row("Small repository reasoning",family,prompt,"",
                            {"response_mode":"repository_reasoning_json","files":files,
                             "entry":"main.py","expected":{"output":None,"reason":tag}}))
    return rows


VALIDATION_FAMILIES = {
    "d_patch_divisor","d_patch_casefold_match","d_patch_newline_exact","d_patch_sort_stable",
    "d_tool_open_span","d_tool_plan_review","d_tool_open_ticket","d_tool_plan_migration",
    "d_repo_wrapper_order","d_repo_shadowed_parameter","d_repo_finally_mutation",
    "d_explain_zip_shortest","d_explain_set_union","d_explain_fstring_alignment",
    "d_simple_prefix_products","d_bug_list_partition","d_bug_scale_zero",
    "d_debug_assignments","d_debug_word_counts","d_tdd_product_except",
}


def build():
    # Import only the frozen scorer; it never queries a model.
    import sys
    sys.path.insert(0,str(ROOT / "benchmark/experiment_d_dev"))
    import validate_d_dev as scorer
    rows = code_examples() + patch_examples() + tool_examples() + explanation_examples() + repository_examples()
    for item in rows:
        checks = item["checks"]
        if item["response_mode"] in {"explanation_json","repository_reasoning_json"}:
            checks["expected"]["output"] = scorer.run_oracle(checks)
            item["messages"][2]["content"] = json.dumps(checks["expected"],separators=(",",":"),ensure_ascii=False)
    train = [item for item in rows if item["family"] not in VALIDATION_FAMILIES]
    validation = [item for item in rows if item["family"] in VALIDATION_FAMILIES]
    if len(rows) != 200 or len(train) != 160 or len(validation) != 40:
        raise ValueError(f"wrong generated counts: {len(rows)}, {len(train)}, {len(validation)}")
    for path,data in ((HERE / "experiment_d_train.jsonl",train),
                      (HERE / "experiment_d_validation.jsonl",validation)):
        with path.open("w",encoding="utf-8") as stream:
            for item in data:
                stream.write(json.dumps(item,ensure_ascii=False,separators=(",",":")) + "\n")
    return train,validation


if __name__ == "__main__":
    training,validation = build()
    print(f"Wrote {len(training)} train and {len(validation)} validation D1 examples")
