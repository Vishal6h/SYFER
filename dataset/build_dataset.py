#!/usr/bin/env python3
"""Build the deterministic, locally authored Stage 2 SFT dataset."""

import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
NAMES = ("amber", "birch", "copper", "delta", "elm")
SYSTEM = {
    "Simple coding": "Write small, correct Python functions. Follow the requested output format exactly.",
    "Bug fixing": "Repair the stated bug with a minimal change. Preserve behavior outside the bug.",
    "Code explanation": "Trace the code accurately. Return only the requested JSON object.",
    "Patch generation": "Return a valid unified diff with accurate headers, hunk counts, and context.",
    "Multi-step debugging": "Find and fix every stated issue. Keep unrelated behavior intact.",
    "Tool-call formatting": "Use only the declared mock tool protocol. Do not execute any tool.",
    "Test-driven fixing": "Read every supplied test before changing code. Preserve passing behavior.",
    "Small repository reasoning": "Trace the supplied virtual repository carefully and answer in JSON.",
}


def fill(value, name):
    if isinstance(value, str):
        return value.replace("@N@", name)
    if isinstance(value, list):
        return [fill(item, name) for item in value]
    if isinstance(value, dict):
        return {key: fill(item, name) for key, item in value.items()}
    return value


def record(category, family, difficulty, user, answer, checks):
    return {
        "messages": [
            {"role": "system", "content": SYSTEM[category]},
            {"role": "user", "content": user},
            {"role": "assistant", "content": answer},
        ],
        "category": category,
        "source": "locally_curated_synthetic_v1",
        "difficulty": difficulty,
        "family": family,
        "checks": checks,
    }


def case(function, args, expected, unchanged=False):
    result = {"function": function, "args": args, "expected": expected}
    if unchanged:
        result["unchanged_args"] = True
    return result


def code_family(category, family, objective, answer, cases, before=None, difficulty="medium"):
    result = []
    for name in NAMES:
        task = fill(objective, name)
        code = fill(answer, name).strip() + "\n"
        if before is None:
            user = f"Implement this Python task: {task}\nReturn only Python function definitions, with no imports or example calls."
        else:
            user = f"{task}\n\nCurrent code:\n{fill(before, name).strip()}\n\nReturn only corrected Python function definitions, with no imports or example calls."
        result.append(record(category, family, difficulty, user, code,
                             {"kind": "python", "cases": fill(cases, name)}))
    return result


def patch_family(family, objective, before, after, cases, difficulty="medium"):
    result = []
    for name in NAMES:
        path = f"{name}_{family}.py"
        old = fill(before, name).strip() + "\n"
        new = fill(after, name).strip() + "\n"
        old_lines, new_lines = old.splitlines(), new.splitlines()
        # One full-file hunk is easy to inspect and has exact counts.
        diff = (f"--- a/{path}\n+++ b/{path}\n"
                f"@@ -1,{len(old_lines)} +1,{len(new_lines)} @@\n"
                + "".join("-" + line + "\n" for line in old_lines)
                + "".join("+" + line + "\n" for line in new_lines))
        user = (f"In {path}, {fill(objective, name)} Preserve unrelated behavior. "
                f"Return only a unified diff with exact --- a/{path} and +++ b/{path} headers.\n\nCurrent file:\n{old}")
        result.append(record("Patch generation", family, difficulty, user, diff,
                             {"kind": "patch", "path": path, "source": old,
                              "expected_source": new, "cases": fill(cases, name)}))
    return result


def json_family(category, family, make, difficulty="easy"):
    result = []
    for index, name in enumerate(NAMES):
        user, payload = make(name, index)
        answer = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
        result.append(record(category, family, difficulty, user, answer,
                             {"kind": "json", "expected": payload}))
    return result


def build():
    rows = []
    add = rows.extend

    # Three small standalone coding families.
    add(code_family("Simple coding", "running_totals",
        "Write @N@_running_totals(values), returning the sum after each integer in order. The empty list returns [].",
        "def @N@_running_totals(values):\n    total = 0\n    result = []\n    for value in values:\n        total += value\n        result.append(total)\n    return result",
        [case("@N@_running_totals", [[4,-2,7]], [4,2,9]), case("@N@_running_totals", [[0]], [0])], difficulty="easy"))
    add(code_family("Simple coding", "vowel_count",
        "Write @N@_vowel_count(text), counting the letters a, e, i, o, u without regard to case.",
        "def @N@_vowel_count(text):\n    return sum(char.lower() in 'aeiou' for char in text)",
        [case("@N@_vowel_count", ["MUSIC box"], 3), case("@N@_vowel_count", ["rhythm"], 0)], difficulty="easy"))
    add(code_family("Simple coding", "rotate_right",
        "Write @N@_rotate_right(values, steps), returning a new list rotated right by nonnegative steps. Empty input returns [].",
        "def @N@_rotate_right(values, steps):\n    if not values:\n        return []\n    shift = steps % len(values)\n    return values[-shift:] + values[:-shift] if shift else values[:]",
        [case("@N@_rotate_right", [[4,7,9,1],2], [9,1,4,7]), case("@N@_rotate_right", [[5,6],4], [5,6]), case("@N@_rotate_right", [[],6], [])], difficulty="medium"))

    # Six distinct bug types. Counterexamples cover each stated edge case.
    add(code_family("Bug fixing", "comma_fields",
        "Fix @N@_filled_fields so it counts nonblank comma-delimited fields. Spaces inside a field are allowed; blank or whitespace-only fields do not count.",
        "def @N@_filled_fields(text):\n    return sum(bool(part.strip()) for part in text.split(','))",
        [case("@N@_filled_fields", ["red, , blue,, green"], 3), case("@N@_filled_fields", [" , , "], 0), case("@N@_filled_fields", ["two words"], 1)],
        "def @N@_filled_fields(text):\n    return len(text.split(','))"))
    add(code_family("Bug fixing", "strict_threshold",
        "Fix @N@_first_above to return the first index whose number is strictly above threshold, or -1 if none.",
        "def @N@_first_above(values, threshold):\n    for index, value in enumerate(values):\n        if value > threshold:\n            return index\n    return -1",
        [case("@N@_first_above", [[8,8,11],8], 2), case("@N@_first_above", [[4,5],5], -1), case("@N@_first_above", [[],3], -1)],
        "def @N@_first_above(values, threshold):\n    for index, value in enumerate(values):\n        if value >= threshold:\n            return index\n    return -1"))
    add(code_family("Bug fixing", "closed_interval",
        "Fix @N@_within so both endpoints of the numeric interval count as inside.",
        "def @N@_within(value, lower, upper):\n    return lower <= value <= upper",
        [case("@N@_within", [3,3,9], True), case("@N@_within", [9,3,9], True), case("@N@_within", [10,3,9], False)],
        "def @N@_within(value, lower, upper):\n    return lower < value < upper"))
    add(code_family("Bug fixing", "nonzero_mean",
        "Fix @N@_mean_nonzero: ignore zero values, return their arithmetic mean, and return 0 if no nonzero values remain.",
        "def @N@_mean_nonzero(values):\n    kept = [value for value in values if value != 0]\n    return sum(kept) / len(kept) if kept else 0",
        [case("@N@_mean_nonzero", [[0,3,4]], 3.5), case("@N@_mean_nonzero", [[0,0]], 0), case("@N@_mean_nonzero", [[-2,2]], 0.0)],
        "def @N@_mean_nonzero(values):\n    return sum(values) // len(values)"))
    add(code_family("Bug fixing", "copy_append",
        "Fix @N@_with_item so it returns a new list with item appended and leaves the input list unchanged.",
        "def @N@_with_item(values, item):\n    return values + [item]",
        [case("@N@_with_item", [[7,8],9], [7,8,9], True), case("@N@_with_item", [[],4], [4], True)],
        "def @N@_with_item(values, item):\n    values.append(item)\n    return values"))
    add(code_family("Bug fixing", "common_sorted",
        "Fix @N@_common_sorted to return sorted distinct integers present in both input lists.",
        "def @N@_common_sorted(left, right):\n    return sorted(set(left) & set(right))",
        [case("@N@_common_sorted", [[7,3,7,1],[7,2,3]], [3,7]), case("@N@_common_sorted", [[1],[8]], [])],
        "def @N@_common_sorted(left, right):\n    return sorted(set(left) | set(right))"))

    # Six two-function repairs. Each answer fixes both faults.
    add(code_family("Multi-step debugging", "fee_pipeline",
        "Fix both functions. @N@_read_fees parses semicolon-separated whole numbers, skipping blanks. @N@_fee_total returns their sum; an empty input totals zero.",
        "def @N@_read_fees(text):\n    return [int(part.strip()) for part in text.split(';') if part.strip()]\n\ndef @N@_fee_total(text):\n    return sum(@N@_read_fees(text))",
        [case("@N@_read_fees", [" 4; ; 9;2 "], [4,9,2]), case("@N@_fee_total", ["4; ; 9;2"], 15), case("@N@_fee_total", [" ; "], 0)],
        "def @N@_read_fees(text):\n    return [int(part) for part in text.split(';')]\n\ndef @N@_fee_total(text):\n    return len(@N@_read_fees(text))", difficulty="hard"))
    add(code_family("Multi-step debugging", "name_match",
        "Fix both functions. @N@_clean_name strips outer spaces and lowercases a name. @N@_same_name compares two cleaned names.",
        "def @N@_clean_name(name):\n    return name.strip().lower()\n\ndef @N@_same_name(left, right):\n    return @N@_clean_name(left) == @N@_clean_name(right)",
        [case("@N@_clean_name", ["  Ada  "], "ada"), case("@N@_same_name", [" ADA ","ada"], True), case("@N@_same_name", ["Ada","Ed"], False)],
        "def @N@_clean_name(name):\n    return name.lower()\n\ndef @N@_same_name(left, right):\n    return left == right", difficulty="hard"))
    add(code_family("Multi-step debugging", "score_report",
        "Fix both functions. @N@_passing keeps scores at or above cutoff. @N@_pass_rate returns passing count divided by all scores, or 0 for empty input.",
        "def @N@_passing(scores, cutoff):\n    return [score for score in scores if score >= cutoff]\n\ndef @N@_pass_rate(scores, cutoff):\n    return len(@N@_passing(scores, cutoff)) / len(scores) if scores else 0",
        [case("@N@_passing", [[4,5,8],5], [5,8]), case("@N@_pass_rate", [[4,5,8,10],5], 0.75), case("@N@_pass_rate", [[],6], 0)],
        "def @N@_passing(scores, cutoff):\n    return [score for score in scores if score > cutoff]\n\ndef @N@_pass_rate(scores, cutoff):\n    return len(@N@_passing(scores, cutoff)) // len(scores)", difficulty="hard"))
    add(code_family("Multi-step debugging", "record_totals",
        "Fix both functions. @N@_increase returns a new record dict with its 'units' field increased by amount. @N@_units reads that field, defaulting to zero. Do not mutate the input.",
        "def @N@_increase(record, amount):\n    updated = record.copy()\n    updated['units'] = updated.get('units', 0) + amount\n    return updated\n\ndef @N@_units(record):\n    return record.get('units', 0)",
        [case("@N@_increase", [{"units":7,"name":"A"},4], {"units":11,"name":"A"}, True), case("@N@_increase", [{"name":"B"},3], {"units":3,"name":"B"}, True), case("@N@_units", [{"units":9}], 9), case("@N@_units", [{}], 0)],
        "def @N@_increase(record, amount):\n    record['units'] = amount\n    return record\n\ndef @N@_units(record):\n    return len(record)", difficulty="hard"))
    add(code_family("Multi-step debugging", "token_frequency",
        "Fix both functions. @N@_tokens splits on whitespace and lowercases tokens. @N@_frequency counts every occurrence in a dictionary.",
        "def @N@_tokens(text):\n    return [part.lower() for part in text.split()]\n\ndef @N@_frequency(text):\n    counts = {}\n    for token in @N@_tokens(text):\n        counts[token] = counts.get(token, 0) + 1\n    return counts",
        [case("@N@_tokens", ["Hi  HI\nthere"], ["hi","hi","there"]), case("@N@_frequency", ["Hi hi there"], {"hi":2,"there":1}), case("@N@_frequency", [" "], {})],
        "def @N@_tokens(text):\n    return text.split(' ')\n\ndef @N@_frequency(text):\n    return {token: 1 for token in @N@_tokens(text)}", difficulty="hard"))
    add(code_family("Multi-step debugging", "duration_max",
        "Fix both functions. @N@_minutes converts a nonnegative 'H:M' duration to total minutes. @N@_longest returns the greatest duration in minutes, or 0 for an empty list.",
        "def @N@_minutes(text):\n    hours, minutes = text.split(':')\n    return int(hours) * 60 + int(minutes)\n\ndef @N@_longest(values):\n    return max((@N@_minutes(value) for value in values), default=0)",
        [case("@N@_minutes", ["2:07"], 127), case("@N@_longest", [["0:45","1:02","0:59"]], 62), case("@N@_longest", [["0:00"]], 0)],
        "def @N@_minutes(text):\n    hours, minutes = text.split(':')\n    return int(hours) + int(minutes)\n\ndef @N@_longest(values):\n    return min(@N@_minutes(value) for value in values)", difficulty="hard"))

    # Six patch families use real single-file unified diffs built from the two versions.
    add(patch_family("trim_title", "make @N@_title remove surrounding whitespace while retaining interior spaces.",
        "def @N@_title(text):\n    return text.lstrip()",
        "def @N@_title(text):\n    return text.strip()",
        [case("@N@_title", ["  New  Item  "], "New  Item"), case("@N@_title", ["Ready"], "Ready")]))
    add(patch_family("safe_ratio", "make @N@_ratio return numerator / denominator, or 0 when denominator is zero.",
        "def @N@_ratio(numerator, denominator):\n    return numerator // denominator",
        "def @N@_ratio(numerator, denominator):\n    return numerator / denominator if denominator else 0",
        [case("@N@_ratio", [7,2], 3.5), case("@N@_ratio", [5,0], 0), case("@N@_ratio", [-4,2], -2.0)]))
    add(patch_family("contains_all", "make @N@_contains_all report whether every required value appears in available, including empty requirements.",
        "def @N@_contains_all(available, required):\n    return any(value in available for value in required)",
        "def @N@_contains_all(available, required):\n    return all(value in available for value in required)",
        [case("@N@_contains_all", [[2,4],[2,9]], False), case("@N@_contains_all", [[2,4],[4,2]], True), case("@N@_contains_all", [[2],[]], True)]))
    add(patch_family("keep_nonnegative", "make @N@_nonnegative retain zero and positive numbers in their original order.",
        "def @N@_nonnegative(values):\n    return [value for value in values if value > 0]",
        "def @N@_nonnegative(values):\n    return [value for value in values if value >= 0]",
        [case("@N@_nonnegative", [[-5,0,3,0]], [0,3,0]), case("@N@_nonnegative", [[-4,-1]], [])]))
    add(patch_family("first_prefix", "make @N@_first_prefix return the first string beginning with prefix, or None if absent.",
        "def @N@_first_prefix(values, prefix):\n    for value in values:\n        if value.startswith(prefix):\n            found = value\n    return found",
        "def @N@_first_prefix(values, prefix):\n    for value in values:\n        if value.startswith(prefix):\n            return value\n    return None",
        [case("@N@_first_prefix", [["axe","ant","bee"],"a"], "axe"), case("@N@_first_prefix", [["bee"],"z"], None), case("@N@_first_prefix", [[],"a"], None)]))
    add(patch_family("fraction_cap", "make @N@_cap_fraction limit numbers above 1 to 1 while leaving zero and negative values unchanged.",
        "def @N@_cap_fraction(value):\n    return max(value, 1)",
        "def @N@_cap_fraction(value):\n    return min(value, 1)",
        [case("@N@_cap_fraction", [2.5], 1), case("@N@_cap_fraction", [0.4], 0.4), case("@N@_cap_fraction", [-1], -1)]))

    # Four test-led repairs; the cases are visible in each user request.
    tdd_specs = [
        ("multiples", "@N@_count_multiples(values, divisor) counts all elements divisible by the nonzero divisor, including zero.",
         "def @N@_count_multiples(values, divisor):\n    return sum(value % divisor == 0 for value in values)",
         "def @N@_count_multiples(values, divisor):\n    return sum(value > 0 and value % divisor == 0 for value in values)",
         [case("@N@_count_multiples", [[0,6,-3,4],3], 3), case("@N@_count_multiples", [[],7], 0)]),
        ("clean_tags", "@N@_clean_tags(tags) strips and lowercases each tag, discarding blank tags, while preserving order.",
         "def @N@_clean_tags(tags):\n    return [tag.strip().lower() for tag in tags if tag.strip()]",
         "def @N@_clean_tags(tags):\n    return [tag.lower() for tag in tags]",
         [case("@N@_clean_tags", [["  Red "," ","BLUE"]], ["red","blue"]), case("@N@_clean_tags", [[" ","\t"]], [])]),
        ("longest_word", "@N@_longest_word(words) returns the first longest word, or an empty string when no words exist.",
         "def @N@_longest_word(words):\n    return max(words, key=len, default='')",
         "def @N@_longest_word(words):\n    return sorted(words, key=len)[-1]",
         [case("@N@_longest_word", [["wolf","pear","hi"]], "wolf"), case("@N@_longest_word", [[]], "")]),
        ("positive_squares", "@N@_positive_squares(values) squares only strictly positive numbers, preserving order.",
         "def @N@_positive_squares(values):\n    return [value * value for value in values if value > 0]",
         "def @N@_positive_squares(values):\n    return [value * value for value in values if value >= 0]",
         [case("@N@_positive_squares", [[-4,0,3,5]], [9,25]), case("@N@_positive_squares", [[-3,0]], [])]),
    ]
    for family, objective, answer, before, cases in tdd_specs:
        visible = "; ".join(f"{item['function']}({', '.join(repr(arg) for arg in item['args'])}) -> {item['expected']!r}" for item in cases)
        add(code_family("Test-driven fixing", family,
            f"Read these tests first: {visible}. Then fix the implementation. {objective} Keep passing behavior.",
            answer, cases, before, difficulty="medium"))

    # Three explanation families. Expected output is computed from the shown snippet.
    def explain_alias(name, index):
        number = 10 + index
        code = f"items = [{number}]\nalias = items\nalias.append({number + 2})\nprint(items)"
        return (f"What does this Python code print, and why? Return only JSON with keys output and explanation.\n\n{code}",
                {"output": [number, number + 2], "explanation": "alias and items refer to the same list, so append changes the printed list."})
    def explain_copy(name, index):
        number = 20 + index
        code = f"source = [{number}]\ncopy = source + [{number + 1}]\nprint(source)"
        return (f"What does this Python code print, and why? Return only JSON with keys output and explanation.\n\n{code}",
                {"output": [number], "explanation": "List concatenation creates a new list; source stays unchanged."})
    def explain_slice(name, index):
        start = 30 + 3 * index
        values = [start, start + 1, start + 2, start + 3]
        code = f"values = {values!r}\nprint(values[::2])"
        return (f"What does this Python code print, and why? Return only JSON with keys output and explanation.\n\n{code}",
                {"output": values[::2], "explanation": "A step of two selects indices 0 and 2."})
    for family, maker in (("alias_append", explain_alias), ("copy_concat", explain_copy), ("stride_two", explain_slice)):
        add(json_family("Code explanation", family, maker))

    # All mock tools share the same {tool, arguments} envelope, with new names and arguments.
    def tool_lookup(name, index):
        symbol = f"{name}_parse_headers"
        return (f"Mock protocol: reply with exactly one minified JSON object and no other text. "
                f"Shape: {{\"tool\":\"lookup_symbol\",\"arguments\":{{\"symbol\":\"NAME\"}}}}. "
                f"Look up {symbol} now.", {"tool": "lookup_symbol", "arguments": {"symbol": symbol}})
    def tool_doc(name, index):
        doc_id = f"{name}-guide-{index + 2}"
        return (f"Mock protocol: reply with exactly one minified JSON object and no other text. "
                f"Shape: {{\"tool\":\"read_doc\",\"arguments\":{{\"doc_id\":\"ID\"}}}}. "
                f"Read document {doc_id} now.", {"tool": "read_doc", "arguments": {"doc_id": doc_id}})
    def tool_search(name, index):
        query = f"{name} error handling"
        return (f"Mock protocol: reply with exactly one minified JSON object and no other text. "
                f"Shape: {{\"tool\":\"search_notes\",\"arguments\":{{\"query\":\"TEXT\",\"limit\":2}}}}. "
                f"Search for {query!r} with limit 2.", {"tool": "search_notes", "arguments": {"query": query, "limit": 2}})
    for family, maker in (("lookup", tool_lookup), ("read_doc", tool_doc), ("search_notes", tool_search)):
        add(json_family("Tool-call formatting", family, maker))

    # Virtual repositories use three separate reasoning patterns.
    def repo_chain(name, index):
        user = (f"Virtual files:\n{name}_entry.py: from {name}_flow import build; def launch(data): return build(data)\n"
                f"{name}_flow.py: from {name}_calc import combine; def build(data): return combine(data)\n"
                f"{name}_calc.py: def combine(data): return len(data)\n"
                "Which file computes the final value, and what is the full function call chain from launch? "
                "Return only JSON with keys file and chain (array of names).")
        return user, {"file": f"{name}_calc.py", "chain": ["launch", "build", "combine"]}
    def repo_owner(name, index):
        user = (f"Virtual files:\n{name}_ui.py: from {name}_format import format_row; def show(row): return format_row(row)\n"
                f"{name}_format.py: def format_row(row): return str(row['id'])\n"
                f"{name}_store.py: def get_row(key): return {{'id': key}}\n"
                "Which file defines the function that formats a row for display, and what is the function? "
                "Return only JSON with keys file and function.")
        return user, {"file": f"{name}_format.py", "function": "format_row"}
    def repo_config(name, index):
        user = (f"Virtual files:\n{name}_main.py: from {name}_service import start; def boot(cfg): return start(cfg)\n"
                f"{name}_service.py: from {name}_ports import choose_port; def start(cfg): return choose_port(cfg)\n"
                f"{name}_ports.py: def choose_port(cfg): return cfg.get('port', 9000)\n"
                "Where is the fallback port chosen, and what is the complete call chain from boot? "
                "Return only JSON with keys file and chain (array of names).")
        return user, {"file": f"{name}_ports.py", "chain": ["boot", "start", "choose_port"]}
    for family, maker in (("call_chain", repo_chain), ("function_owner", repo_owner), ("config_flow", repo_config)):
        add(json_family("Small repository reasoning", family, maker, difficulty="medium"))

    assert len(rows) == 170, len(rows)
    train, validation = [], []
    # Entire last family in each category is held out; no renamed sibling crosses the split.
    last_family = {}
    for item in rows:
        last_family[item["category"]] = item["family"]
    for item in rows:
        target = validation if item["family"] == last_family[item["category"]] else train
        target.append(item)
    for path, data in ((HERE / "syfer_train.jsonl", train), (HERE / "syfer_validation.jsonl", validation)):
        path.write_text("".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in data), encoding="utf-8")
    print(f"Wrote {len(rows)} examples: {len(train)} train, {len(validation)} validation")


if __name__ == "__main__":
    build()
