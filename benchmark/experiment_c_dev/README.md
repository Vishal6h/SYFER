# Frozen Experiment C development benchmark

This benchmark was created and validated before the Experiment C dataset or
training setup. It has 32 new tasks, four in each of the eight SYFER coding
categories. No model has been queried on these tasks. It is a **development**
benchmark for C, not a new untouched final holdout. The original 16 tasks and
the 32-task `final_holdout` were both inspected before C and are not used to
select C settings.

`validate_c_dev.py` checks every reference answer using the same isolated
Python/diff and exact JSON/tool-call validators as the earlier holdout. It
also executes explanation and virtual-repository snippets in temporary
directories. Virtual repository files are inline in `tasks.json`.

The contamination audit covers both original Stage 2 splits, both combined
Experiment B splits, `benchmark/tasks.json`, and
`benchmark/final_holdout/tasks.json`. Exact prompts, normalized prompts,
complete expected-output vectors, family names, and suspiciously similar
same-category prompts all returned zero matches. Forty individual expected
values overlap earlier material; these are common small results such as
booleans and zeros, not complete task vectors.

Frozen SHA-256 values:

| File | SHA-256 |
| --- | --- |
| `benchmark/experiment_c_dev/tasks.json` | `d428a4186944358b420c754a70e70027e6bc0251d8320ad058db4e3609eb04b4` |
| `benchmark/experiment_c_dev/validate_c_dev.py` | `39fa89524df13d27005d607f57ac0504c20e0a6fbbf0acc2f6c65b0ea230801f` |

Do not edit the tasks or validator after this freeze. Future evaluation must
send only each task's `prompt` to a model; references and cases remain local
to the scorer. No model evaluation is part of the C preparation stage.
