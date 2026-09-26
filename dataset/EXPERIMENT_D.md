# Experiment D dataset (D1)

This deterministic, locally authored dataset contains 200 new supervised
examples from 100 task families. Eighty families (160 examples) train the
adapter; 20 disjoint families (40 examples) validate it. The separate frozen
D-development benchmark was written and hashed **before** these examples.
Neither its prompts nor its reference answers were used as training content.

| Category | Total |
| --- | ---: |
| Patch generation | 40 |
| Tool-call formatting | 36 |
| Small repository reasoning | 32 |
| Code explanation | 28 |
| Simple coding | 16 |
| Bug fixing | 16 |
| Multi-step debugging | 16 |
| Test-driven fixing | 16 |

Each JSONL row has `messages` (system/user/assistant), `category`, `source`,
`difficulty`, `family`, `response_mode`, `contract_version`, and `checks`.
The assistant target obeys [the D1 contract](../docs/TRAINING_OUTPUT_CONTRACT.md):
raw Python or unified diff, or one exact-schema JSON value. Explanation and
repository examples consistently use `output`/`reason` and a prompt-stated
literal reason tag. Tool examples use `tool`/`arguments` with typed nested
schemas and no real tool invocation.

Regenerate with `python3 -B dataset/build_experiment_d.py` and validate with
`python3 -B dataset/validate_experiment_d.py`. The validator checks every
reference target against the versioned D scorer, runs code in isolated
temporary directories, applies every diff, parses every JSON target, runs
trusted explanation/repository oracles, checks family separation and scans
all earlier benchmarks/datasets for prompt contamination. The generated
`experiment_d_stats.json` records counts, errors and SHA256 hashes.

Frozen JSONL SHA256 values:

- `experiment_d_train.jsonl`: `9a9a213ea36de6fb2c191845bf510119b5f954ec159cb6cbd12c42fe9903d953`
- `experiment_d_validation.jsonl`: `c38c0009a7974f7f6a71660cc7485f56addd0608c19e64e94f008c9aa25daf61`

The 40 validation examples come from different families, but this is still a
small authored dataset. The validation loss is an optimization signal, not a
substitute for the separately versioned 32-task D-development evaluation.
