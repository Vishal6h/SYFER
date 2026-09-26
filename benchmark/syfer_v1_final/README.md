# SYFER v1 — final model-development benchmark

**THIS IS THE FINAL MODEL-DEVELOPMENT BENCHMARK FOR SYFER v1.**

**NO MODEL WAS QUERIED DURING BENCHMARK CONSTRUCTION.**

There are 48 authored tasks: six each in Simple coding, Bug fixing, Code
explanation, Patch generation, Multi-step debugging, Tool-call formatting,
Test-driven fixing, and Small repository reasoning. Tasks and fixtures are fully
inline in `tasks.json`. All 48 reference answers pass deterministic validation;
the 12 explanation/repository outputs are also computed by executing the trusted
fixtures. References are test oracles, not model outputs.

This benchmark is the one fresh release decision set for Stock, B, and D. Previous
benchmarks are historical/development evidence. No model may be trained or tuned
against this benchmark after exposure. No additional experiment is authorized.
Do not change the frozen files, selectively rerun failures, or use this benchmark
to revise datasets. The source authoring script refuses to rebuild after freeze.

## Contracts and scores

The response modes follow `docs/TRAINING_OUTPUT_CONTRACT.md` (D1). Each prompt
spells out its response mode and restrictions. There are no hidden reason tags.

- **Official STRICT**: correct semantics plus the stated contract. Code is bare
  function definitions; JSON is bare with explicit exact keys/types; patches are
  raw diffs. Forbidden fences and prose fail. Ordinary implementation comments
  inside Python are acceptable. The builtin whitelist and no-import policy are
  stated in raw-code prompts. Patch fixtures contain only self-contained functions.
- **Semantic diagnostic — NOT THE OFFICIAL RELEASE SCORE**: first uses strict
  scoring. On failure, it may remove exactly one complete enclosing Markdown
  fence (matching backtick/tilde delimiters, optional info string) and revalidate
  the unchanged body. Surrounding prose, multiple/nested fences, missing keys,
  invalid JSON, wrong arguments, bad logic, and malformed diff counts are never
  repaired. A successful diagnostic rescue is labelled formatting-only.
- JSON is parsed semantically in both metrics: whitespace/key order do not matter;
  extra keys, duplicate keys, wrong types (including bool vs integer), NaN and
  Infinity fail. Code-explanation and repo answers have exactly `output` and
  `reason`; every literal reason is supplied in the prompt.
- Diff validation checks single-file headers, old/new hunk positions/counts,
  exact context/deletions, actual patched behavior, and unchanged helper source.
  Replacement, insertion, deletion and multiple-hunk cases are present. CRLF
  transport and one extra terminal blank line are harmless and accepted. Actual
  Python content whitespace is never globally stripped; it can change strings or
  indentation. No multi-file diff tasks are included: this parser deliberately
  supports one file per patch. Repository tasks still use multiple inline files.
- Debugging validates both helper outputs and final pipeline behavior. TDD/coding
  execute deterministic cases, including edge cases and nonmutation checks.

The sandbox runs answers in isolated temporary directories with restricted
builtins/AST, CPU/address-space limits and a timeout. Normal `iter`, `next`,
`divmod`, etc. are available. It is a controlled test harness, **not an OS-grade
sandbox for deliberately hostile arbitrary code**. Trusted authored repository
oracles may use standard-library modules. No model is connected to shell/file
editing tools; tool tasks are parsed mock JSON only.

## Novelty / contamination

`check_contamination.py` checks all four earlier task files and all eight
Stage2/B/C/D train/validation splits (852 records, including repeated Stage2
records in B). `contamination_report.json` records source hashes and nearest
lexical neighbors. Checks cover exact/normalized prompts, normalized full
reference answers, complete expected-output vectors, family IDs, declared
function names, fixture file identifiers, same-category lexical similarity, and
large normalized AST identity. `novelty_review.md` documents the 48-family manual
review. There are no blocking matches or obvious near-copies in that review.
Common Python constructs and canonical schemas recur intentionally. Heuristics
cannot prove the absence of all semantic overlap, and six tasks per category
provide limited statistical precision.

## Freeze and model-free validation

`frozen_manifest.json` hashes tasks, validator, evaluator, comparison script,
tests, authorship/audit/support scripts, review, README, the D1 contract, and prior
contamination inputs. All fixtures are inline. Its “no model evaluated” statement
records the **time of freeze**; future evaluation results do not rewrite it.

Run from the SYFER project root:

```bash
python3 -B benchmark/syfer_v1_final/validate_final.py
python3 -B benchmark/syfer_v1_final/check_contamination.py
python3 -B -m unittest discover -s benchmark/syfer_v1_final -p 'test_*.py' -v
python3 -B benchmark/evaluate_syfer_v1_final.py --model stock --check
```

The two adapter checks need the actual completed training run directories; no
local substitute adapter is fabricated. Tests use clearly synthetic records only
in temporary directories, never the real results roots. No GPU/model package
imports, tokenizer downloads or generation occur in `--check`.

## One identical evaluation path

Stock is the Hugging Face base, **not Ollama**. All three candidates load
`Qwen/Qwen2.5-Coder-3B-Instruct` at
`89fe5444e8baf5736e70f528f1edcc79e6616ef6` with the same tokenizer/chat template,
NF4/double-quantized base loading, and CUDA device 0. BF16 is used if supported,
otherwise FP16. This is temporary inference loading, not adapter merging or an
export/quantization stage. Only adapter presence/identity differs.

Every task uses one unchanged user message, no system message, the chat template
with `add_generation_prompt=True`, seed 42, greedy generation (`do_sample=False`,
one beam; temperature 0 denotes this deterministic policy), and 512 new tokens.
Only the generated suffix is decoded with special tokens skipped; no fences or
prose are stripped from saved raw responses. Model-supplied sampling defaults are
replaced with one common generation configuration. Prompt token hashes, template
hash, vocabulary hash, package versions, dtype/GPU, eos/pad IDs and the effective
generation config are recorded. The first runtime environment is locked, and the
comparison rejects incompatible environments or different tokenized prompts.
Do all three evaluations in the same Kaggle image/session and GPU type.

B and D are locked to the user-nominated run IDs and the adapter/config SHA256s
recorded in the copied historical D-dev run configs. Provenance is in
`candidate_provenance.json`. D requires `--experiment-d-run`; C/A are not allowed.

Each candidate reserves a unique run directory **before loading/generation**.
An exclusive `evaluation_once.json` prevents an accidental second run. A runtime
error/interruption marks the run invalid rather than scoring an infrastructure
failure as a model failure. Do not delete the reservation after seeing answers.
If infrastructure fails before any response, retain the status/error evidence and
obtain an explicit, documented recovery plan before attempting a fresh run.
Never selectively retry failed tasks.

Future outputs:

```
results/syfer_v1_final/
  evaluation_environment.json
  stock/<run-id>/
  experiment_b/<run-id>/
  experiment_d/<run-id>/
```

Each run contains `summary.json`, `run_config.json`, `tasks_snapshot.json`,
`progress.json`, `run_status.json`, and 48 `.txt`/48 `.result.json` pairs. The
summary records strict and diagnostic totals, percentages, category scores,
per-task results, load/task/total runtime. Interrupted runs have no completed
summary and cannot enter the final comparison.

## Commit from the local workspace

Stage only this new benchmark and its two top-level scripts. Do not accidentally
stage previous result archives, datasets, adapters, or untracked audit folders.

```bash
cd ~/SYFER
git add benchmark/syfer_v1_final benchmark/evaluate_syfer_v1_final.py benchmark/compare_syfer_v1_final.py
git diff --cached --stat
git commit -m "Freeze final SYFER v1 benchmark and one-shot evaluation tooling"
git push origin main
```

## Kaggle: pull, restore, check

Use a terminal (or a notebook `%%bash` cell). Attach the **extracted complete** B
and D training runs as Kaggle inputs, or retain them in the working checkout.
Each must include `run_status.json`, `manifest.json`, `config.json`, and `adapter/`.
The restore helper searches `/kaggle/input` by the exact run names, validates the
recorded weight hashes, and copies to the expected paths without overwriting.
It never downloads a replacement or invents metadata. If only an archive is
attached, extract it to a directory first; its path cannot be guessed here.

```bash
set -e
cd /kaggle/working/SYFER
git pull --ff-only origin main
python3 -B benchmark/syfer_v1_final/restore_candidates.py --input-root /kaggle/input
python3 -B benchmark/syfer_v1_final/validate_final.py
python3 -B benchmark/syfer_v1_final/check_contamination.py
python3 -B -m unittest discover -s benchmark/syfer_v1_final -p 'test_*.py' -v
python3 -B benchmark/evaluate_syfer_v1_final.py --model stock --check
python3 -B benchmark/evaluate_syfer_v1_final.py --model experiment_b --check
python3 -B benchmark/evaluate_syfer_v1_final.py --model experiment_d --experiment-d-run training/output/experiment_d/experiment-20260926T190151Z-2a492ce7 --check
```

These checks do not query a model. Keep the existing working CUDA/Transformers/
PEFT/bitsandbytes stack unchanged across all three runs. Internet is needed to
retrieve the already-pinned base if it is not cached. Persist the complete results
outside the ephemeral Kaggle working session.

## Kaggle: evaluate exactly once, only after all checks pass

These commands are prepared for the user; none was executed during construction.

```bash
set -e
cd /kaggle/working/SYFER
python3 -B benchmark/evaluate_syfer_v1_final.py --model stock
python3 -B benchmark/evaluate_syfer_v1_final.py --model experiment_b
python3 -B benchmark/evaluate_syfer_v1_final.py --model experiment_d --experiment-d-run training/output/experiment_d/experiment-20260926T190151Z-2a492ce7
python3 -B benchmark/compare_syfer_v1_final.py
```

The comparison script discovers exactly one completed run per candidate, replays
all saved responses with the frozen validator, checks hashes/settings/tokenized
prompts, and refuses incomplete/incompatible/tampered inputs or an existing final
report. Explicit inputs are also supported:

```bash
python3 -B benchmark/compare_syfer_v1_final.py --stock-run results/syfer_v1_final/stock/<run-id> --b-run results/syfer_v1_final/experiment_b/<run-id> --d-run results/syfer_v1_final/experiment_d/<run-id>
```

It produces `results/syfer_v1_final/final_comparison.md` and `.json`: both metrics,
category tables, B/Stock, D/Stock, D/B gains/regressions/shared passes/failures,
formatting-only rescues and remaining diagnostic failures. It does not load a
model or initiate training.

## Selection policy, fixed before exposure

Choose **between the tuned B and D checkpoints**; Stock is the reference.
Lexicographic criteria:

1. Higher official strict passed count.
2. Higher semantic-diagnostic passed count.
3. Higher combined strict count across patches, tools, repo reasoning, TDD and
   debugging (equal category weights, maximum 30). All five individual category
   counts are also reported; no post-hoc weighting is allowed.
4. Fewer strict regressions versus Stock in simple coding and bug fixing.
5. Smaller adapter weight-file size (both candidates have the same rank).

If every criterion ties exactly, report both as tied instead of inventing a
performance winner; a documented non-training choice is needed. A selected tuned
checkpoint becomes SYFER v1. No winner exists until all three real results are
complete. No new training, Experiment E, export, or quantization is authorized.
