"""No-model checks that Experiment B stays separate from Experiment A."""

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import preflight_experiment_b as preflight
from preflight_experiment_b import CONFIG, OUTPUT, TRAIN, VALIDATION, check
from train_qlora import OUTPUT_ROOT, make_training_arguments, report_paths


class ExperimentBSetupTests(unittest.TestCase):
    def test_static_preflight_and_separate_output(self):
        report = check(local=True)
        self.assertEqual(report["errors"], [])
        self.assertTrue(report["static_checks_passed"])
        self.assertEqual(report["stage6_evidence_source"], "provenance_record")
        self.assertNotEqual(OUTPUT, OUTPUT_ROOT)

    def test_stage6_provenance_fallback_when_original_run_is_absent(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            record = root / preflight.STAGE6_RECORD_PATH
            record.parent.mkdir(parents=True)
            record.write_text((preflight.ROOT / preflight.STAGE6_RECORD_PATH).read_text())
            with patch.object(preflight, "ROOT", root):
                source, path = preflight.stage6_evidence()
            self.assertEqual((source, path), ("provenance_record", record))

    def test_original_stage6_run_takes_precedence_over_record(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            record = root / preflight.STAGE6_RECORD_PATH
            record.parent.mkdir(parents=True)
            record.write_text((preflight.ROOT / preflight.STAGE6_RECORD_PATH).read_text())
            run = root / preflight.STAGE6_RUN_PATH
            run.mkdir(parents=True)
            frozen = json.loads((preflight.ROOT / "benchmark/tasks.json").read_text())
            tasks = [{"id": item["id"], "passed": item["id"] not in preflight.EXPECTED_FAILURES}
                     for item in frozen]
            (run / "summary.json").write_text(json.dumps({"task_count": 16, "passed": 11,
                                                          "tasks": tasks}))
            (run / "run_status.json").write_text(json.dumps({"status": "complete"}))
            (run / "run_config.json").write_text(json.dumps({
                "tasks_sha256": preflight.EXPECTED_HASHES["benchmark/tasks.json"],
                "baseline_runner_sha256": preflight.EXPECTED_HASHES["benchmark/run_baseline.py"]}))
            with patch.object(preflight, "ROOT", root):
                self.assertEqual(preflight.stage6_evidence(), ("run_directory", run))
                (run / "run_status.json").write_text(json.dumps({"status": "in_progress"}))
                with self.assertRaisesRegex(ValueError, "original Stage 6 run"):
                    preflight.stage6_evidence()  # Do not hide an invalid run behind the record.

    def test_provenance_rejects_changed_score_or_artifact_claim(self):
        original = json.loads((preflight.ROOT / preflight.STAGE6_RECORD_PATH).read_text())
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "record.json"
            for key, value in (("baseline", {"passed": 7, "total": 16}),
                               ("experiment_a", {"passed": 10, "total": 16}),
                               ("run_id", "different-run"),
                               ("remaining_failed_tasks", ["simple_dedupe"]),
                               ("raw_lightning_artifacts_preserved_in_git", True)):
                changed = dict(original)
                changed[key] = value
                path.write_text(json.dumps(changed))
                with self.assertRaisesRegex(ValueError, "provenance record"):
                    preflight.validate_stage6_record(path)

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
