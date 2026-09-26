"""No-model checks that Experiment B stays separate from Experiment A."""

import json
import unittest
from pathlib import Path
from types import SimpleNamespace

from preflight_experiment_b import CONFIG, OUTPUT, TRAIN, VALIDATION, check
from train_qlora import OUTPUT_ROOT, make_training_arguments, report_paths


class ExperimentBSetupTests(unittest.TestCase):
    def test_static_preflight_and_separate_output(self):
        report = check(local=True)
        self.assertEqual(report["errors"], [])
        self.assertTrue(report["static_checks_passed"])
        self.assertNotEqual(OUTPUT, OUTPUT_ROOT)

    def test_one_epoch_from_pinned_base_and_combined_hashes(self):
        config = json.loads(CONFIG.read_text(encoding="utf-8"))
        args = make_training_arguments(config, Path("unused"), False, False,
                                       lambda **values: SimpleNamespace(**values))
        self.assertEqual(args.num_train_epochs, 1)
        self.assertEqual(args.max_steps, -1)
        self.assertEqual(args.gradient_accumulation_steps, 8)
        self.assertEqual(args.warmup_steps, 0.05)
        self.assertEqual(config["lora"]["rank"], 16)
        paths = report_paths(config, TRAIN, VALIDATION, OUTPUT)
        self.assertEqual(paths["train_sha256"], config["train_sha256"])
        self.assertEqual(paths["validation_sha256"], config["validation_sha256"])


if __name__ == "__main__":
    unittest.main()
