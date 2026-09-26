"""No-model checks for the frozen-baseline comparison arithmetic."""

import copy
import json
from contextlib import nullcontext
import unittest

import run_tuned


class TunedComparisonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.stock = json.loads((run_tuned.BASELINE_RUN / "summary.json").read_text(encoding="utf-8"))

    def test_unchanged_scores_are_zero_gain(self):
        results = copy.deepcopy(self.stock["tasks"])
        result = run_tuned.compare(results, self.stock)
        self.assertEqual(result["tuned_passed"], 6)
        self.assertEqual(result["absolute_task_gain"], 0)
        self.assertEqual(result["percentage_point_gain"], 0)
        self.assertEqual(result["relative_improvement_percent"], 0)

    def test_improvement_and_regression_are_both_reported(self):
        results = copy.deepcopy(self.stock["tasks"])
        by_id = {item["id"]: item for item in results}
        by_id["bug_count_words"]["passed"] = True
        by_id["tool_find_symbol"]["passed"] = False
        result = run_tuned.compare(results, self.stock)
        self.assertEqual(result["tuned_passed"], 6)
        self.assertEqual(result["improved_tasks"], ["bug_count_words"])
        self.assertEqual(result["regressed_tasks"], ["tool_find_symbol"])
        self.assertEqual(result["by_category"]["Bug fixing"]["task_gain"], 1)
        self.assertEqual(result["by_category"]["Tool-call formatting"]["task_gain"], -1)
        markdown = run_tuned.comparison_markdown(result, 1.0)
        self.assertIn("| Tool-call formatting | 2/2 | 1/2 | -1 |", markdown)

    def test_generation_preserves_prompt_and_greedy_limit(self):
        observed = {}

        class Encoding(dict):
            def to(self, device):
                self.assert_device = device
                return self

        class Tokenizer:
            eos_token_id = 0

            def apply_chat_template(self, messages, **kwargs):
                observed["messages"] = messages
                observed["template_kwargs"] = kwargs
                return Encoding(input_ids=type("Tokens", (), {"shape": (1, 2)})())

            def decode(self, ids, **kwargs):
                observed["decoded_ids"] = ids
                return "answer"

        class Model:
            def generate(self, **kwargs):
                observed["generation_kwargs"] = kwargs
                return [[1, 2, 3]]

        fake_torch = type("Torch", (), {"inference_mode": staticmethod(nullcontext)})()
        raw = run_tuned.generate_raw(Model(), Tokenizer(), "Exact frozen prompt", fake_torch,
                                     lambda seed: observed.setdefault("seed", seed))
        self.assertEqual(raw, "answer")
        self.assertEqual(observed["messages"], [{"role": "user", "content": "Exact frozen prompt"}])
        self.assertEqual(observed["seed"], 42)
        self.assertEqual(observed["generation_kwargs"]["max_new_tokens"], 512)
        self.assertFalse(observed["generation_kwargs"]["do_sample"])
        self.assertEqual(observed["decoded_ids"], [3])


if __name__ == "__main__":
    unittest.main()
