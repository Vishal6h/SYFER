"""No-model regression tests for the frozen C development benchmark."""

import hashlib
import json
import sys
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "benchmark"))
import validate_c_dev as dev  # noqa: E402
import evaluate_experiment_c_dev as evaluation  # noqa: E402


class CDevelopmentTests(unittest.TestCase):
    def test_frozen_hashes_and_all_reference_answers(self):
        self.assertEqual(hashlib.sha256(dev.TASKS.read_bytes()).hexdigest(), evaluation.TASKS_SHA256)
        self.assertEqual(hashlib.sha256(Path(dev.__file__).read_bytes()).hexdigest(),
                         evaluation.VALIDATOR_SHA256)
        report = dev.validate()
        self.assertEqual(report["task_count"], 32)
        self.assertEqual(report["validated_references"], 32)
        self.assertEqual(report["error_count"], 0)
        for key in ("exact_prompt", "normalized_prompt", "expected_output_vector",
                    "family_name", "suspicious_similarity"):
            self.assertEqual(report["contamination"][key], 0, key)

    def test_stock_check_has_no_adapter_or_model_load(self):
        tasks, adapter, weights = evaluation.check("stock")
        self.assertEqual(len(tasks), 32)
        self.assertIsNone(adapter)
        self.assertIsNone(weights)

    def test_c_requires_explicit_completed_run(self):
        with self.assertRaisesRegex(ValueError, "required"):
            evaluation.select_adapter("experiment_c", None)
        with self.assertRaisesRegex(ValueError, "under training/output/experiment_c"):
            evaluation.select_adapter("experiment_c", ROOT / "training/output/experiment_b/fake")

    def test_reference_failure_is_detected(self):
        tasks = json.loads(dev.TASKS.read_text(encoding="utf-8"))
        task = next(item for item in tasks if item["category"] == "Tool-call formatting")
        passed, _ = dev.core.validate_response(task, '{"tool":"wrong","arguments":{}}')
        self.assertFalse(passed)


if __name__ == "__main__":
    unittest.main()
