# Proposed D-development validator v2 — specification only

This document proposes a **new, versioned** evaluator for future Experiment D
tasks. No D tasks, response validator, dataset, scores or model run are created
here. `benchmark/experiment_c_dev/`, `benchmark/final_holdout/`, the original
benchmark, and all saved Stock/B/C results stay frozen. Once new D tasks and
fixtures are authored, they must be frozen with their validator SHA-256 values
before any D model query. Do not apply v2 to rewrite C-development scores.

Contract source: `docs/TRAINING_OUTPUT_CONTRACT.md` (`D1`). Proposed version
identifier: `syfer-d-dev-validator-v2`. Each task declares `response_mode`,
exact schema and types, allowed tool registry entry if relevant, and any
preservation invariant. A future result records both task and validator hashes.

## Scoring proposals

1. **Raw Python:** Parse the entire response and require only top-level
   function definitions for `python_code`. Reject prose, fences, multiple
   disjoint code blocks and trailing non-code. Execute in a temporary process
   with a published allowlist that includes harmless `iter`, `next`, `ord` and
   `chr`, but excludes file, process and network access. Compare nested return
   types recursively when the task specifies them. If tuples and lists are
   semantically interchangeable for a task, declare that explicitly.
2. **Exact JSON, explanation and repository JSON:** Parse exactly one complete
   JSON value with duplicate-key detection. Reject fences, prose, unknown
   keys, wrong types and wrong values. Ignore object key order. For
   `explanation_json` and `repository_reasoning_json`, require the task-stated
   `reason` tag; a prose explanation is not equivalent to a tag. Execute
   trusted snippets/virtual repositories in isolated temporary directories.
3. **Tool-call JSON:** Parse an object with exactly `tool` (string) and
   `arguments` (object), then enforce the selected mock tool's nested schema.
   Reject duplicate/extra keys, wrong array order, invented tool names,
   missing required keys and wrong nullability. Accept irrelevant JSON
   whitespace and object-key order; train on compact serialization without
   scoring byte-level quirks. No real tool connection exists.
4. **Unified diff:** Parse raw diff text without whole-string `.strip()`.
   Require one specified file, exact headers, valid hunk positions/counts,
   correct context/deletion prefixes (including a single space on blank
   context), and exact context/deletion matches. Preserve trailing spaces and
   final-newline state; support or explicitly exclude the standard
   `\\ No newline at end of file` marker. Execute the patched source in an
   isolated process. Check both requested behavior and declared untouched
   code regions, not just a few helper examples.

## Acceptance cases for an eventual implementation

| Case | Expected v2 result | Why |
| --- | --- | --- |
| A correct subsequence function using `iter` passes the stated cases. | Pass | The C-development sandbox rejected this valid standard-Python idiom. |
| The C `word_score` answer with `ord` enabled still returns 294 for `cab` rather than 6. | Fail | Wider builtins must not hide algorithmic errors. |
| A code answer wrapped in prose/fences or split across two fences. | Fail with explicit format reason | The old parser silently extracted the first block. |
| A result `[True]` for an expected `[1]` when exact nested JSON types are declared. | Fail | Python's `True == 1` must not bypass declared types. |
| A minified tool object with correct values but `arguments` before `tool`. | Pass | JSON object key order is not meaningful and prompts did not require an order. |
| A tool object with an extra key, duplicated key, wrong nested type, or YAML syntax. | Fail | Exact schema and JSON format remain strict. |
| A standard unified diff whose final context line is blank and prefixed by one space. | Pass and preserve source | The old parser's `.strip()` rejects this valid diff. |
| A valid diff adding a line with two trailing spaces. | Pass and preserve both spaces | The old parser silently removed them. |
| A diff containing an unprefixed blank context line. | Fail | This is the genuine defect in C's four saved patch outputs. |
| A patch that correctly fixes escaping but changes an unrelated helper's integer return to string. | Fail preservation check | The C-development functional cases alone accepted such a change. |
| Bare JSON with correct output but prose instead of a prompt-stated literal reason tag. | Fail | The exact tag is an explicitly stated task requirement. |

Prior audit diagnostics confirmed the first two Python cases, reordered tool
key rejection, diff trailing-blank rejection, trailing-space corruption, and
the unrelated-helper false pass **against the existing scorer**. These cases
are specifications for future tests, not changes to that scorer.

## Evaluation protocol

Author new D-development tasks independently of all training data, including
their reference answers and validators. Run contamination checks against
Stage 2, B, C, the original 16 tasks, final_holdout, and C-development tasks.
Freeze files and hashes before generating D training examples or evaluating a
model. Evaluate Stock and candidate models under v2 on the **same** D tasks;
report both format and semantic failures. Treat C-development and the older
32-task holdout as inspected development evidence, not untouched final tests.
