"""Static tests only: no model inference and no holdout response collection."""

import copy
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import evaluate_final_holdout as evaluator  # noqa: E402
import validate_holdout as holdout  # noqa: E402


class HoldoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tasks = json.loads(holdout.TASKS.read_text(encoding="utf-8"))
        cls.by_id = {task["id"]: task for task in cls.tasks}

    def test_all_references_oracles_and_contamination_checks(self):
        report = holdout.validate_holdout()
        self.assertEqual(report["task_count"], 32)
        self.assertEqual(report["reference_answers_validated"], 32)
        self.assertEqual(set(report["category_counts"].values()), {4})
        self.assertEqual(report["validation_errors"], [])
        for key in ("exact_prompt_matches", "normalized_text_matches",
                    "exact_expected_output_vector_matches", "family_name_matches",
                    "known_development_function_matches", "suspicious_similarity_matches"):
            self.assertEqual(report["contamination_counts"][key], 0)

    def test_python_patch_json_and_tool_validators_reject_bad_responses(self):
        bad = {
            "fh_digital_root": "def digital_root(number):\n    return -999",
            "fh_patch_perimeter": self.by_id["fh_patch_perimeter"]["reference"].replace("@@ -", "@@ -99,"),
            "fh_negative_floor": '{"output":-3,"reason":"floor_division_rounds_down","extra":1}',
            "fh_repo_import_binding": '{"output":9,"reason":"imported_name_is_bound"}',
            "fh_tool_queue": self.by_id["fh_tool_queue"]["reference"] + "\n",
        }
        for task_id, response in bad.items():
            with self.subTest(task=task_id):
                try:
                    passed, _ = holdout.validate_response(self.by_id[task_id], response)
                except ValueError:
                    passed = False
                self.assertFalse(passed)

    def test_contamination_detects_copied_earlier_prompt(self):
        copied = copy.deepcopy(self.by_id["fh_digital_root"])
        copied["prompt"] = json.loads((holdout.ROOT / "benchmark/tasks.json").read_text())[0]["prompt"]
        counts, _, _, errors = holdout.audit_contamination([copied])
        self.assertGreater(counts["exact_prompt_matches"], 0)
        self.assertTrue(errors)

    def test_freeze_hashes_and_stock_check_load_no_model(self):
        self.assertEqual(holdout.sha256(holdout.TASKS), evaluator.TASKS_SHA256)
        self.assertEqual(holdout.sha256(Path(holdout.__file__)), evaluator.VALIDATOR_SHA256)
        tasks, adapter, weights = evaluator.check("stock")
        self.assertEqual(len(tasks), 32)
        self.assertIsNone(adapter)
        self.assertIsNone(weights)
        with patch("sys.argv", ["evaluate_final_holdout.py", "--model", "stock", "--check"]):
            self.assertEqual(evaluator.main(), 0)

    def test_pinned_generation_settings_and_disjoint_outputs(self):
        self.assertEqual(evaluator.OPTIONS, {"temperature": 0, "num_predict": 512, "seed": 42})
        self.assertEqual(set(evaluator.ADAPTERS), {"experiment_a", "experiment_b"})
        roots = {str(evaluator.OUTPUT_ROOT / name) for name in ("stock", "experiment_a", "experiment_b")}
        self.assertEqual(len(roots), 3)


if __name__ == "__main__":
    unittest.main()
