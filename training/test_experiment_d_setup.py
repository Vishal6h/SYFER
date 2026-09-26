"""CPU/static safeguards for the separate Experiment D preparation."""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import preflight_experiment_d as preflight
import train_experiment_d
from train_qlora import MODEL_ID, MODEL_REVISION, make_training_arguments, sha256

sys.path.insert(0,str(preflight.ROOT / "dataset"))
import validate_experiment_d as dataset_validator  # noqa: E402

sys.path.insert(0,str(preflight.ROOT / "benchmark"))
import evaluate_experiment_d_dev as evaluator  # noqa: E402
from experiment_d_dev import validate_d_dev as scorer  # noqa: E402


class ExperimentDSetupTests(unittest.TestCase):
    def test_static_preflight_fresh_base_and_hashes(self):
        report = preflight.check(local=True)
        self.assertEqual(report["errors"],[])
        self.assertTrue(report["static_checks_passed"])
        config = json.loads(preflight.CONFIG.read_text(encoding="utf-8"))
        self.assertEqual(config["model_id"],MODEL_ID)
        self.assertEqual(config["model_revision"],MODEL_REVISION)
        self.assertEqual(config["output_root"],"training/output/experiment_d")
        self.assertEqual(config["training"],preflight.EXPECTED_TRAINING)
        self.assertEqual(config["lora"],preflight.EXPECTED_LORA)
        self.assertEqual(sha256(preflight.TRAIN),config["train_sha256"])
        self.assertEqual(sha256(preflight.VALIDATION),config["validation_sha256"])

    def test_dataset_references_and_family_separation(self):
        stats = dataset_validator.inspect()
        self.assertEqual(stats["validation_error_count"],0)
        self.assertEqual((stats["total"],stats["train"],stats["validation"]),(200,160,40))
        self.assertEqual(stats["family_counts"]["overlap"],0)
        self.assertEqual(stats["validated_references"],{"python":64,"unified_diff":40,"json":96})

    def test_training_arguments_preserve_plan_without_model(self):
        config = json.loads(preflight.CONFIG.read_text(encoding="utf-8"))
        args = make_training_arguments(config,Path("unused"),False,False,
                                       lambda **values: SimpleNamespace(**values))
        self.assertEqual(args.max_steps,-1)
        self.assertEqual(args.num_train_epochs,1)
        self.assertEqual(args.gradient_accumulation_steps,8)
        self.assertEqual(args.learning_rate,0.000075)
        self.assertEqual(args.warmup_steps,0.05)
        self.assertEqual(args.eval_strategy,"epoch")

    def test_malformed_tool_json_and_hunk_counts_are_rejected(self):
        records = [json.loads(line) for line in preflight.TRAIN.read_text(encoding="utf-8").splitlines()]
        tool = next(item for item in records if item["response_mode"] == "tool_call_json")
        with self.assertRaises(ValueError):
            scorer.validate_response(tool["checks"],'{"tool":"x","tool":"x","arguments":{}}')
        patch = next(item for item in records if item["response_mode"] == "unified_diff")
        answer = patch["messages"][2]["content"]
        self.assertTrue(scorer.validate_response(patch["checks"],answer)[0])
        broken = answer.replace("@@", "@", 1)
        with self.assertRaises(ValueError):
            scorer.validate_response(patch["checks"],broken)

    def test_train_flag_cannot_bypass_host_preflight(self):
        with patch.object(sys,"argv",["train_experiment_d.py","--train"]), \
             patch.object(train_experiment_d,"check",return_value={"errors":["CUDA unavailable"]}), \
             patch.object(train_experiment_d.core,"train") as train:
            with self.assertRaises(SystemExit):
                train_experiment_d.main()
            train.assert_not_called()

    def test_evaluator_check_and_d_run_requirement(self):
        tasks,adapter,weights = evaluator.check("stock")
        self.assertEqual(len(tasks),32)
        self.assertIsNone(adapter)
        self.assertIsNone(weights)
        with self.assertRaisesRegex(ValueError,"experiment-d-run is required"):
            evaluator.select_adapter("experiment_d",None,None)
        with self.assertRaisesRegex(ValueError,"run flags are only"):
            evaluator.select_adapter("stock",None,Path("x"))

    def test_completed_d_adapter_metadata_check_without_model(self):
        pinned = json.loads(preflight.CONFIG.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory(prefix="syfer-d-check-") as temporary:
            output = Path(temporary)
            run = output / "experiment-test"
            adapter = run / "adapter"
            adapter.mkdir(parents=True)
            (adapter / "adapter_model.safetensors").write_bytes(b"static-test-placeholder")
            (adapter / "adapter_config.json").write_text(json.dumps({
                "peft_type":"LORA","r":16,"lora_alpha":32,"lora_dropout":0.05,
                "base_model_name_or_path":MODEL_ID}),encoding="utf-8")
            (run / "config.json").write_text(json.dumps(pinned),encoding="utf-8")
            (run / "run_status.json").write_text(json.dumps({"status":"complete"}),encoding="utf-8")
            (run / "manifest.json").write_text(json.dumps({
                "experiment":"D","mode":"train","model_id":MODEL_ID,
                "model_revision":MODEL_REVISION,"train_sha256":pinned["train_sha256"],
                "validation_sha256":pinned["validation_sha256"]}),encoding="utf-8")
            with patch.object(evaluator,"D_OUTPUT",output):
                tasks,selected,weights = evaluator.check("experiment_d",d_run=run)
                self.assertEqual(len(tasks),32)
                self.assertEqual(selected,adapter)
                self.assertEqual(weights,adapter / "adapter_model.safetensors")
                (run / "run_status.json").write_text(json.dumps({"status":"interrupted"}),encoding="utf-8")
                with self.assertRaisesRegex(ValueError,"incomplete"):
                    evaluator.select_adapter("experiment_d",None,run)


if __name__ == "__main__":
    unittest.main()
