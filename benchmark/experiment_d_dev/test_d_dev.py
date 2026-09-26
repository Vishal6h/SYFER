"""No-model tests of the versioned D1 benchmark and scorer."""

import difflib
import json
import unittest

try:
    from . import validate_d_dev as d
except ImportError:
    import validate_d_dev as d


class DDevelopmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tasks = {task["id"]: task for task in json.loads(d.TASKS.read_text(encoding="utf-8"))}

    def test_references_and_contamination(self):
        report = d.validate_benchmark()
        self.assertEqual(report["task_count"], 32)
        self.assertEqual(report["validated_references"], 32)
        self.assertEqual(report["error_count"], 0, report["errors"])
        self.assertEqual(report["contamination"], dict.fromkeys(report["contamination"], 0))
        self.assertEqual(report["category_counts"], {category: 4 for category in sorted(d.CATEGORIES)})

    def test_tool_json_is_semantic_but_strict_about_schema(self):
        task = self.tasks["ddev_tool_catalog_exact"]
        expected = task["expected"]
        reversed_order = json.dumps({"arguments": expected["arguments"], "tool": expected["tool"]},
                                    indent=2)
        self.assertTrue(d.validate_response(task, "  \n" + reversed_order + "\n")[0])
        self.assertFalse(d.validate_response(task, json.dumps({**expected, "extra": 1}))[0])
        with self.assertRaisesRegex(ValueError, "duplicate JSON key"):
            d.validate_response(task, '{"tool":"catalog_lookup","tool":"catalog_lookup","arguments":{}}')
        with self.assertRaises(ValueError):
            d.validate_response(task, "```json\n" + task["reference"] + "\n```")

    def test_iter_is_available_and_nested_types_are_checked(self):
        code = "def subsequence(short, long):\n    it = iter(long)\n    return all(char in it for char in short)\n"
        cases = [{"function": "subsequence", "args": ["ace", "abcde"], "expected": True},
                 {"function": "subsequence", "args": ["aec", "abcde"], "expected": False}]
        self.assertTrue(d.validate_python(code, cases)[0])
        self.assertFalse(d.validate_python("def value():\n    return [True]\n",
                                           [{"function": "value", "args": [], "expected": [1]}])[0])
        with self.assertRaises(ValueError):
            d.validate_python("Here:\n```python\n" + code + "```", cases)

    def test_diff_preserves_blank_context_and_trailing_spaces(self):
        task = self.tasks["ddev_patch_terminal_newline"]
        patched = d.apply_unified_diff(task["source"], task["reference"], task["path"])
        self.assertTrue(patched.endswith("\n\n"))
        old = "def value():\n    return 1\n"
        new = "def value():\n    return 2  \n"
        diff = "".join(difflib.unified_diff(old.splitlines(keepends=True),
                                            new.splitlines(keepends=True),
                                            fromfile="a/x.py", tofile="b/x.py"))
        self.assertEqual(d.apply_unified_diff(old, diff, "x.py"), new)
        with self.assertRaisesRegex(ValueError, "hunk line counts"):
            d.apply_unified_diff(old, diff.replace("@@ -1,2 +1,2 @@", "@@ -1,2 +1,3 @@"), "x.py")

    def test_patch_rejects_unrelated_change_and_unprefixed_blank_context(self):
        task = self.tasks["ddev_patch_line_endings"]
        old = task["source"]
        changed = old.replace("return '>' + value", "return str(value)")
        changed = changed.replace("return text.replace('\\r\\n', '\\n')",
                                  "return text.replace('\\r\\n', '\\n').replace('\\r', '\\n')")
        diff = "".join(difflib.unified_diff(old.splitlines(keepends=True),
                                            changed.splitlines(keepends=True),
                                            fromfile="a/" + task["path"],
                                            tofile="b/" + task["path"]))
        passed, detail = d.validate_response(task, diff)
        self.assertFalse(passed)
        self.assertIn("unrelated function changed", detail)
        bad = task["reference"].replace(" \n", "\n")
        with self.assertRaisesRegex(ValueError, "invalid diff line"):
            d.validate_response(task, bad)

    def test_standard_zero_length_insertion_and_deletion_hunks(self):
        self.assertEqual(d.apply_unified_diff("", "--- a/x.py\n+++ b/x.py\n@@ -0,0 +1 @@\n+value = 1\n", "x.py"),
                         "value = 1\n")
        self.assertEqual(d.apply_unified_diff("a\n", "--- a/x.py\n+++ b/x.py\n@@ -1,0 +2 @@\n+b\n", "x.py"),
                         "a\nb\n")
        self.assertEqual(d.apply_unified_diff("a\n", "--- a/x.py\n+++ b/x.py\n@@ -1 +0,0 @@\n-a\n", "x.py"),
                         "")


if __name__ == "__main__":
    unittest.main()
