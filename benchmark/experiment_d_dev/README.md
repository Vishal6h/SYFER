# Experiment D development benchmark (D1)

This is a new, versioned development series. Its 32 authored tasks contain four
tasks in each of the eight SYFER categories. The prompts state the required
response shape, including every JSON key and literal reason tag. The validator
compares parsed JSON values and types, applies raw unified diffs with hunk-count
checks, and executes code in an isolated temporary directory with a restricted
set of ordinary Python builtins. It never invokes a model or a real tool.

Frozen on 2026-09-26 before Experiment D dataset construction or model queries:

| File | SHA256 |
| --- | --- |
| `tasks.json` | `c2e858e1b67dd6d8d529e7f80db9cb6a9eb6715a80066e53c686544f188ad788` |
| `validate_d_dev.py` | `4e0a7d268861f7df898406116e52ec80037d48b73a3b4691939ae539c3558792` |
| `build_tasks.py` (authorship provenance) | `bb5f5f99e64c8cd5efee22ce190968291916501bd94e5e18573c9f475107b633` |

Run `python3 -B benchmark/experiment_d_dev/validate_d_dev.py` to check all
reference answers and scan prior Stage 2/B/C datasets and earlier benchmarks
for exact, normalized and suspiciously similar prompts. Run
`python3 -B benchmark/experiment_d_dev/test_d_dev.py` for parser and sandbox
regressions. Both commands are local and model-free. Keep these frozen files
unchanged after evaluation; fixes require a new benchmark version and score
series. Do not compare scores on this series to historical C-dev scores as if
they shared the same tasks.
