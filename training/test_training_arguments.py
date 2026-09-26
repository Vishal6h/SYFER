"""CPU-only checks for the pinned Transformers TrainingArguments settings."""

import importlib.util
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from train_qlora import HERE, load_config, make_training_arguments


class TrainingArgumentsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = load_config(HERE / "config.json")

    def test_smoke_and_experiment_settings_without_model(self):
        with tempfile.TemporaryDirectory(dir=HERE) as directory:
            for smoke, expected_steps, expected_accumulation, expected_eval in (
                (True, 1, 1, "no"),
                (False, -1, self.config["training"]["gradient_accumulation_steps"], "epoch"),
            ):
                with self.subTest(smoke=smoke):
                    args = make_training_arguments(
                        self.config, Path(directory), smoke, False,
                        lambda **kwargs: SimpleNamespace(**kwargs),
                    )
                    self.assertEqual(args.max_steps, expected_steps)
                    self.assertEqual(args.gradient_accumulation_steps, expected_accumulation)
                    self.assertEqual(args.eval_strategy, expected_eval)
                    self.assertEqual(args.warmup_steps, self.config["training"]["warmup_ratio"])
                    self.assertEqual(args.save_strategy, "no")
                    self.assertEqual(args.logging_strategy, "steps")
                    self.assertTrue(args.fp16)
                    self.assertFalse(args.bf16)

    @unittest.skipUnless(importlib.util.find_spec("transformers"), "Transformers is not installed locally")
    def test_real_transformers_arguments_on_cpu(self):
        from transformers import TrainingArguments

        def cpu_arguments(**kwargs):
            # Construct the real API on CPU; precision selection is tested above.
            kwargs.update(fp16=False, bf16=False, use_cpu=True)
            return TrainingArguments(**kwargs)

        with tempfile.TemporaryDirectory(dir=HERE) as directory:
            for smoke in (True, False):
                with self.subTest(smoke=smoke):
                    args = make_training_arguments(
                        self.config, Path(directory), smoke, False, cpu_arguments,
                    )
                    self.assertEqual(args.max_steps, 1 if smoke else -1)
                    self.assertEqual(args.warmup_steps, 0.05)
                    self.assertEqual(args.gradient_accumulation_steps, 1 if smoke else 8)
                    self.assertEqual(args.save_strategy, "no")


if __name__ == "__main__":
    unittest.main()
