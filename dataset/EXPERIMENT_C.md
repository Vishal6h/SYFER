# Experiment C supervised dataset

This is a separate, authored dataset for Experiment C. It does not change
Stage 2 or Experiment B records. `build_experiment_c.py` deterministically
recreates the checked-in JSONL files; `validate_experiment_c.py` checks every
record and writes `experiment_c_stats.json`.

Each line has three `messages` (system, user, assistant), `category`, `source`,
`difficulty`, `family`, and `checks`. The `checks` field is local validation
metadata: executable Python cases, an exact patch target and cases, or an
expected JSON object and isolated snippet/repository oracle. Only `messages`
are passed to the training tokenizer.

| Category | Train | Validation | Total |
| --- | ---: | ---: | ---: |
| Patch generation | 28 | 4 | 32 |
| Tool-call formatting | 20 | 4 | 24 |
| Small repository reasoning | 20 | 4 | 24 |
| Simple coding | 4 | 4 | 8 |
| Bug fixing | 4 | 4 | 8 |
| Code explanation | 4 | 4 | 8 |
| Multi-step debugging | 4 | 4 | 8 |
| Test-driven fixing | 4 | 4 | 8 |
| **Total** | **88** | **32** | **120** |

The 30 authored task families each have four readable variants. Eight entire
families are reserved for validation; no family appears in both splits. This
design gives deterministic coverage but variants within a family are related,
so 120 records are not 120 independent concepts. The training examples were
built after the C development benchmark was frozen. That benchmark's prompts,
expected answers, fixtures, and validators are never inserted into this data.

The validator runs Python solutions and virtual repositories in temporary
directories, applies and executes patches, checks exact JSON values and types,
and checks each executable explanation. It compares prompts with the original
16-task benchmark, the older 32-task holdout, the new C development benchmark,
and the earlier Stage 2/B datasets. The current validation result is 120/120
valid, zero exact duplicate prompts, zero family split overlaps, zero prior
dataset prompt matches, and zero exact, normalized, full-answer-vector, or
suspicious-similarity benchmark matches. Similarity checks are heuristic and
do not prove absence of every semantic overlap.

Run `python3 -B dataset/validate_experiment_c.py` before any cloud training.
Do not use the old 32-task holdout to select C hyperparameters or edit the C
dataset after seeing C development model responses.
