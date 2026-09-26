"""Standard-library checks for chat-template return shapes and loss masking."""

import unittest

from train_qlora import format_example, normalize_token_ids


class FakeTokenizer:
    def apply_chat_template(self, messages, **kwargs):
        ids = [10, 11] if len(messages) == 2 else [10, 11, 12, 13]
        return {"input_ids": ids, "attention_mask": [1] * len(ids)}


class ChatFormatTests(unittest.TestCase):
    def test_mapping_and_single_batch_contain_integer_ids(self):
        for encoding in ([10, 11], {"input_ids": [10, 11]}, {"input_ids": [[10, 11]]}):
            ids = normalize_token_ids(encoding)
            self.assertEqual(ids, [10, 11])
            self.assertTrue(all(type(token_id) is int for token_id in ids))

    def test_rejects_invalid_ids_and_multiple_batches(self):
        for encoding in ({"input_ids": [10, "11"]}, {"input_ids": [10, True]},
                         {"input_ids": [[10], [11]]}, {"attention_mask": [1]}, []):
            with self.subTest(encoding=encoding), self.assertRaises(ValueError):
                normalize_token_ids(encoding)

    def test_mapping_preserves_mask_and_length_validation(self):
        messages = [{"role": role, "content": role} for role in ("system", "user", "assistant")]
        item = format_example(FakeTokenizer(), messages, max_length=4)
        self.assertEqual(item["input_ids"], [10, 11, 12, 13])
        self.assertEqual(item["labels"], [-100, -100, 12, 13])
        self.assertEqual(item["attention_mask"], [1, 1, 1, 1])
        with self.assertRaisesRegex(ValueError, "above limit"):
            format_example(FakeTokenizer(), messages, max_length=3)


if __name__ == "__main__":
    unittest.main()
