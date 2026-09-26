# SYFER Stage 2 dataset

This is a locally authored supervised fine-tuning dataset for the coding weaknesses measured in Stage 1. It contains 170 examples: 130 training and 40 validation. No external data or model outputs were used as target answers. The Stage 1 benchmark remains a separate holdout.

## Files and commands

- `build_dataset.py` contains the curated task families and deterministically writes both JSONL splits.
- `syfer_train.jsonl` and `syfer_validation.jsonl` contain one inspectable example per line.
- `validate_dataset.py` validates every record and writes `stats.json`.
- `stats.json` reports counts and validation errors.

From the SYFER root:

```sh
python3 -B dataset/build_dataset.py
python3 -B dataset/validate_dataset.py
```

The builder is deterministic: the same source writes the same JSONL bytes. Run the validator after any edit. It exits nonzero if a record is malformed or fails a check.

## Record format

```json
{
  "messages": [
    {"role": "system", "content": "..."},
    {"role": "user", "content": "..."},
    {"role": "assistant", "content": "..."}
  ],
  "category": "Bug fixing",
  "source": "locally_curated_synthetic_v1",
  "difficulty": "medium",
  "family": "strict_threshold",
  "checks": {"kind": "python", "cases": []}
}
```

Only `messages` are intended as model input and target text in a later stage. The other fields are provenance and quality checks. The displayed `checks` object is schematic; real Python examples contain at least two concrete cases. Assistant targets contain only the requested code, diff, or JSON.

## Curation choices

The baseline failed on repeat handling, whitespace, boundary comparisons, mutation versus copying, arithmetic means, full call chains, and unified diff hunk counts. The dataset teaches those concepts through different functions and values. Bug fixing, patch generation, and multi-step debugging have 30 examples each; the remaining categories have 15–20 each. Patch targets are generated as exact full-file unified diffs. Multi-step tasks require both functions to work. Test-driven tasks show tests in the prompt before the broken implementation. Mock tool calls share the `{ "tool": ..., "arguments": ... }` envelope and never invoke tools.

Each of 34 task families has five variants. All five variants of a family stay in one split; the final family in each category is reserved for validation. This gives every category five validation examples and keeps renamed siblings out of the opposite split. The validation set is separate from Stage 1's benchmark and is for future training checks only.

The validator checks JSONL syntax, exact required fields, role order, nonempty messages, valid categories and difficulty labels, exact duplicate prompts/examples, family overlap, and exact Stage 1 prompt/response reuse. It also checks benchmark function names, patch paths, tool symbols, and exact test input/output pairs. Python targets run against recorded cases in temporary directories with a timeout and limited built-ins. Diff targets must have valid headers and hunk counts, match the old file, produce the curated new file, and pass Python cases. Explanation outputs are compared with executing the shown snippet. Repository call chains are traced from the virtual files. Tool JSON must parse, match the required envelope, and be minified exactly.

## Limits

This is a small first dataset. Variants within a family share an algorithm and should not be treated as independent evidence of broad coverage. Explanations are checked for the printed value and a nonempty rationale, but their wording is not semantically graded. The Python runner uses process isolation to catch ordinary mistakes and hangs; it is not a hardened sandbox for hostile code. Stage 3 should review representative examples and the family distribution before any training setup.
