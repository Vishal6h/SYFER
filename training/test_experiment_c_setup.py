"""CPU-only checks for the separate Experiment C setup."""

import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import preflight_experiment_c as preflight
import train_experiment_c
from train_qlora import MODEL_ID, MODEL_REVISION, make_training_arguments, sha256


sys.path.insert(0, str(preflight.ROOT / "dataset"))
import build_experiment_c  # noqa: E402
import validate_experiment_c as dataset_validation  # noqa: E402


class ExperimentCSetupTests(unittest.TestCase):
    def test_static_preflight_and_fresh_base(self):
        report = preflight.check(local=True)
        self.assertEqual(report["errors"], [])
        self.assertTrue(report["static_checks_passed"])
        config = json.loads(preflight.CONFIG.read_text(encoding="utf-8"))
        self.assertEqual(config["model_id"], MODEL_ID)
        self.assertEqual(config["model_revision"], MODEL_REVISION)
        self.assertEqual(config["output_root"], "training/output/experiment_c")
        self.assertEqual(config["training"], preflight.EXPECTED_TRAINING)
        self.assertEqual(config["lora"], preflight.EXPECTED_LORA)

    def test_generated_data_matches_checked_in_hashes(self):
        train, validation = build_experiment_c.build()
        disk_train = [json.loads(line) for line in preflight.TRAIN.read_text().splitlines()]
        disk_validation = [json.loads(line) for line in preflight.VALIDATION.read_text().splitlines()]
        self.assertEqual((train, validation), (disk_train, disk_validation))
        config = json.loads(preflight.CONFIG.read_text())
        self.assertEqual(sha256(preflight.TRAIN), config["train_sha256"])
        self.assertEqual(sha256(preflight.VALIDATION), config["validation_sha256"])

    def test_training_arguments_do_not_load_model_or_start_training(self):
        config = json.loads(preflight.CONFIG.read_text())
        args = make_training_arguments(config, Path("unused"), False, False,
                                       lambda **values: SimpleNamespace(**values))
        self.assertEqual(args.num_train_epochs, 1)
        self.assertEqual(args.max_steps, -1)
        self.assertEqual(args.gradient_accumulation_steps, 8)
        self.assertEqual(args.learning_rate, 0.00005)
        self.assertEqual(args.warmup_steps, 0.05)
        self.assertEqual(args.eval_strategy, "epoch")

    def test_validator_rejects_bad_tool_json_and_patch(self):
        train, validation = build_experiment_c.build()
        for category, bad_answer in (("Tool-call formatting", '{"tool":"wrong"}'),
                                     ("Patch generation", "```diff\n--- a/wrong.py\n```")):
            example = next(row for row in train + validation if row["category"] == category)
            changed = json.loads(json.dumps(example))
            changed["messages"][2]["content"] = bad_answer
            with self.assertRaises((ValueError, KeyError)):
                dataset_validation.check_record(changed)

    def test_train_mode_requires_host_preflight_before_core_train(self):
        with patch.object(sys, "argv", ["train_experiment_c.py", "--train"]), \
             patch.object(train_experiment_c, "check", return_value={"errors": ["CUDA unavailable"]}), \
             patch.object(train_experiment_c.core, "train") as train:
            with self.assertRaises(SystemExit):
                train_experiment_c.main()
            train.assert_not_called()


if __name__ == "__main__":
    unittest.main()
