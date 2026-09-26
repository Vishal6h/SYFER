"""CPU-only checks for Experiment B evaluation and its A comparison."""

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import run_experiment_b as runner
import run_tuned


class ExperimentBEvaluationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tasks = json.loads(runner.TASKS.read_text(encoding="utf-8"))
        cls.stock = json.loads((runner.BASELINE_RUN / "summary.json").read_text(encoding="utf-8"))
        cls.a_passes = runner.stage6_passes(cls.tasks, cls.stock)

    def test_stage6_provenance_reconstructs_a_without_raw_artifacts(self):
        self.assertEqual(len(self.a_passes), 11)
        self.assertEqual({task["id"] for task in self.tasks} - self.a_passes,
                         runner.EXPECTED_A_FAILURES)

    def test_comparison_reports_improvements_regressions_and_caveat(self):
        results = [{"id": task["id"], "category": task["category"],
                    "passed": task["id"] in self.a_passes} for task in self.tasks]
        by_id = {item["id"]: item for item in results}
        by_id["simple_dedupe"]["passed"] = True
        by_id["tool_find_symbol"]["passed"] = False
        comparison = runner.compare_with_a(results, self.stock, self.a_passes)
        self.assertEqual(comparison["experiment_b_passed"], 11)
        self.assertEqual(comparison["improved_vs_a"], ["simple_dedupe"])
        self.assertEqual(comparison["regressed_vs_a"], ["tool_find_symbol"])
        self.assertEqual(comparison["by_category"]["Simple coding"]["change_from_a"], 1)
        self.assertEqual(comparison["by_category"]["Tool-call formatting"]["change_from_a"], -1)
        markdown = runner.comparison_markdown(comparison, 3.5)
        self.assertIn("Stock: 6/16 (37.5%). Experiment A: 11/16 (68.8%).", markdown)
        self.assertIn("DEVELOPMENT benchmark", markdown)
        self.assertIn("not an untouched final holdout", markdown)

    def test_check_mode_does_not_load_model(self):
        with patch.object(runner, "preflight", return_value=(self.tasks, self.stock,
                                                             self.a_passes, Path("adapter_model.safetensors"))), \
                patch("sys.argv", ["run_experiment_b.py", "--check"]):
            self.assertEqual(runner.main(), 0)

    def test_preflight_accepts_pinned_fixture_without_model(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = runner.ROOT
            for relative in ("benchmark/tasks.json", "benchmark/run_baseline.py",
                             "results/stage6_experiment_a_record.json",
                             "dataset/syfer_train.jsonl", "dataset/syfer_validation.jsonl",
                             "dataset/experiment_b_train.jsonl", "dataset/experiment_b_validation.jsonl",
                             "training/config_experiment_b.json"):
                destination = root / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source / relative, destination)
            baseline_run = root / runner.BASELINE_RUN.relative_to(source)
            baseline_run.mkdir(parents=True)
            for name in ("summary.json", "run_config.json"):
                shutil.copyfile(runner.BASELINE_RUN / name, baseline_run / name)
            adapter_run = root / runner.ADAPTER_RUN.relative_to(source)
            adapter = adapter_run / "adapter"
            adapter.mkdir(parents=True)
            (adapter / "adapter_model.safetensors").write_bytes(b"test-only weights placeholder")
            (adapter / "adapter_config.json").write_text(json.dumps({
                "peft_type": "LORA", "r": 16, "lora_alpha": 32, "lora_dropout": 0.05,
                "base_model_name_or_path": runner.MODEL_ID}))
            planned = json.loads(runner.CONFIG.read_text(encoding="utf-8"))
            (adapter_run / "config.json").write_text(json.dumps(planned))
            (adapter_run / "manifest.json").write_text(json.dumps({
                "model_id": runner.MODEL_ID, "model_revision": runner.REVISION,
                "train_sha256": planned["train_sha256"],
                "validation_sha256": planned["validation_sha256"],
                "experiment": "B", "mode": "train"}))
            (adapter_run / "loss_history.json").write_text("{}")
            (adapter_run / "experiment_metrics.json").write_text(json.dumps({
                "completed_normally": True, "optimizer_steps": 12}))
            (adapter_run / "run_status.json").write_text(json.dumps({
                "status": "complete", "optimizer_steps": 12}))
            constants = {"ROOT": root, "TASKS": root / "benchmark/tasks.json",
                         "BASELINE_RUN": baseline_run, "ADAPTER_RUN": adapter_run,
                         "STAGE6_RECORD": root / "results/stage6_experiment_a_record.json",
                         "OUTPUT_ROOT": root / "results/experiment_b",
                         "CONFIG": root / "training/config_experiment_b.json"}
            with patch.multiple(runner, **constants):
                tasks, stock, a_passes, weights = runner.preflight()
            self.assertEqual(len(tasks), 16)
            self.assertEqual(stock["passed"], 6)
            self.assertEqual(len(a_passes), 11)
            self.assertEqual(weights, adapter / "adapter_model.safetensors")

    def test_generation_path_is_the_unchanged_a_runner(self):
        self.assertIs(runner.experiment_a.generate_raw, run_tuned.generate_raw)
        self.assertEqual(runner.EXPECTED_OPTIONS,
                         {"temperature": 0, "num_predict": 512, "seed": 42})

    def test_check_rejects_changed_frozen_hash_revision_and_result_path(self):
        for name, value, message in (("TASKS_SHA256", "wrong", "frozen task"),
                                     ("REVISION", "wrong", "pinned base"),
                                     ("OUTPUT_ROOT", run_tuned.OUTPUT_ROOT, "not separate")):
            with self.subTest(name=name), patch.object(runner, name, value):
                with self.assertRaisesRegex(ValueError, message):
                    runner.preflight()


if __name__ == "__main__":
    unittest.main()
