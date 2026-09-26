# Experiment B dataset extension

The original Stage 2 `syfer_train.jsonl` and `syfer_validation.jsonl` are unchanged. `build_experiment_b.py` appends 80 locally authored examples to new combined files: 60 to `experiment_b_train.jsonl` and 20 to `experiment_b_validation.jsonl`. The combined totals are 190 train and 60 validation. New rows have source `targeted_experiment_b_v1`, so they can be audited separately. Whole example families are assigned to one split only.

The additions concentrate on stable distinctness, last-match state, exact JSON explanation output, whitespace-sensitive unified diffs, and multi-file call chains. Eight examples each rehearse mock tool calls, multi-step debugging, and test-driven fixes that worked in Experiment A. The examples use new functions, file names, inputs, and outputs; they do not copy benchmark tasks. The generator is deterministic and uses only local code and Python's standard library.

`validate_experiment_b.py` checks every combined record with the original Stage 2 record validator, including executing code cases, applying diffs, checking JSON and tool-call shapes, and tracing virtual repository answers. It also checks original-record preservation, exact prompt duplicates, family overlap, benchmark contamination, category distribution, and split hashes. The generated `experiment_b_stats.json` records the results. Rebuild and validate with:

```sh
python3 -B dataset/build_experiment_b.py
python3 -B dataset/validate_experiment_b.py
```

Do not regenerate the B files after training begins: `config_experiment_b.json` pins their current SHA-256 hashes. Any change requires a deliberate new dataset/config version and a fresh validation pass. The frozen 16-task benchmark remains evaluation-only.
