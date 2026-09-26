"""Check adapter inference plumbing without loading torch or model weights."""

from contextlib import nullcontext
import unittest

from verify_smoke_adapter import generate_completion


class FakeTensor:
    ndim = 2
    shape = (1, 2)


class FakeEncoding(dict):
    def to(self, device):
        if device != "cpu":
            raise AssertionError("test must stay on CPU")
        return self

    def __getattr__(self, name):
        raise AttributeError  # Matches BatchEncoding's empty-message missing attribute.


class FakeTokenizer:
    eos_token_id = 0

    def apply_chat_template(self, messages, **kwargs):
        assert kwargs["return_dict"] is True
        assert kwargs["return_tensors"] == "pt"
        return FakeEncoding(input_ids=FakeTensor(), attention_mask=FakeTensor())

    def decode(self, token_ids, **kwargs):
        return "two" if token_ids == [7] else ""


class FakeModel:
    def generate(self, **kwargs):
        assert isinstance(kwargs["input_ids"], FakeTensor)
        assert isinstance(kwargs["attention_mask"], FakeTensor)
        assert kwargs["max_new_tokens"] == 24
        return [[1, 2, 7]]


class AdapterInferenceTests(unittest.TestCase):
    def test_encoding_is_passed_by_keyword_and_prompt_length_is_tensor_length(self):
        self.assertEqual(generate_completion(FakeModel(), FakeTokenizer(), nullcontext, "cpu"), "two")

    def test_batch_encoding_has_no_shape_and_raises_empty_attribute_error(self):
        with self.assertRaises(AttributeError) as caught:
            _ = FakeEncoding(input_ids=FakeTensor()).shape
        self.assertEqual(str(caught.exception), "")


if __name__ == "__main__":
    unittest.main()
