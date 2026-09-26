# SYFER final holdout — frozen before model evaluation

This 32-task holdout was authored after Experiments A and B finished. It has
four tasks in each of the eight benchmark categories. Neither experiment was
trained on these prompts, and no model response to them has been generated or
inspected in Stage 9. The earlier 16-task benchmark is a development set for
Experiment B and is not an untouched final holdout.

Each task contains its prompt, objective cases or exact JSON/tool expectation,
and a reference answer. The runner sends **only the prompt** to a model.
`validate_holdout.py` checks every reference answer against the same scoring
function future runs will use. Python solutions execute in isolated temporary
directories; patch tasks must be applicable unified diffs with valid hunk
counts and pass executable cases. JSON tasks require exact keys, types, and
values. Mock tool calls require exact minified JSON. Explanation and virtual
repository outputs are additionally checked by executing their authored code
in temporary directories. Virtual repository files are embedded in
`tasks.json`; there are no separate fixture files.

The contamination audit reads all four Stage 2/Experiment B JSONL splits and
the original `benchmark/tasks.json`. It checks exact prompts, normalized
prompts, complete expected-output vectors, task-family names, known development
functions, and high text/token similarity within categories. All six checks
returned zero matches when frozen. Forty **individual** expected values also
occur in earlier material; these are common values such as booleans, zero,
empty lists, or small integers. Their complete task output vectors and prompts
do not match. This distinction is recorded in the validator report.

Frozen SHA-256 values:

| File | SHA-256 |
| --- | --- |
| `benchmark/final_holdout/tasks.json` | `862cf0dc1a3d11cdff1f1555dce85fe26fdef9fd93548eb34d7b7c5bb75187a9` |
| `benchmark/final_holdout/validate_holdout.py` | `f36aec792f6e3c0cb7d81765908d7bc5f8cfd279799cadb36628a9dbf3e4bec1` |
| Separate fixture/repository files | None; inline fixtures are covered by the tasks hash. |

Run static validation without querying a model:

```sh
python3 -B benchmark/final_holdout/validate_holdout.py
python3 -B -m unittest discover -s benchmark/final_holdout -p 'test_*.py' -v
python3 -B benchmark/evaluate_final_holdout.py --model stock --check
```

The future runner uses the pinned
`Qwen/Qwen2.5-Coder-3B-Instruct` revision
`89fe5444e8baf5736e70f528f1edcc79e6616ef6` for **all three** arms,
loaded in 4-bit NF4 for the same Hugging Face chat-template inference path.
`stock` means that pinned base without an adapter; it does not invoke the
earlier Ollama baseline. A and B attach their respective saved adapters.
All arms use temperature 0, greedy decoding, at most 512 new tokens, and seed
42. Their future results go to separate unique run directories under
`results/final_holdout/stock/`, `experiment_a/`, and `experiment_b/`.

The Experiment A adapter must be present at
`training/output/experiment-20260926T093433Z-6630ef2a/adapter/` and the
Experiment B adapter at
`training/output/experiment_b/experiment-20260926T111408Z-4838f847/adapter/`
before their `--check` modes can pass on Kaggle. The checks do not load a
model. Preserve the holdout files and hashes; do not edit cases or validators
after seeing model results.
