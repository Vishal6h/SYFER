# Experiment D design proposal — no dataset or training run

This is a plan based on the C-development postmortem, not authorization to
generate examples, change frozen evaluators, or train. The C-development set
and older 32-task holdout have both been inspected and are development
evidence. A genuinely new D evaluation set must be authored and frozen before
any D model query. The proposed versioned validator contract is in
`benchmark/experiment_d_dev/VALIDATOR_V2_PROPOSAL.md`.

## Choice

Choose **C: a mixed rehearsal + structured-output curriculum**, initialized
from the **original pinned Qwen2.5-Coder-3B-Instruct base**, not the C adapter.
The curriculum is the data/training strategy; fresh-from-base is its starting
checkpoint. C tied Stock on exactly the same ten C-development tasks, had
20/32 byte-identical raw responses, and scored 0/4 in every intended target
category. Continuing C would carry forward behavior without demonstrated
target gains. B also underperformed Stock on this development set. These
observations do not establish a final checkpoint ranking.

## Proposed new dataset

Target **200 new authored examples**, 160 training and 40 family-disjoint
validation, with at least 70 distinct task families and no routine renaming
of one solution four times. Do not copy or closely transform any prompt,
fixture, expected answer or validator from the original 16 tasks, older
32-task holdout, C-development set, or earlier datasets. Run exact,
normalized and semantic-family contamination audits before freezing.

| Category | New examples | Training | Validation | Purpose |
| --- | ---: | ---: | ---: | --- |
| Patch generation | 44 | 36 | 8 | Valid raw diffs, blank context, exact hunk counts, multi-hunk edits, whitespace and preservation. |
| Tool-call formatting | 40 | 32 | 8 | Exact mock root schema, nested arguments, optional/null fields, arrays, selection and ordered plans. |
| Small repository reasoning | 36 | 28 | 8 | Import/cache behavior, callbacks, exception flow, configuration and multi-file data flow with exact reason tags. |
| Code explanation | 28 | 22 | 6 | Bare JSON, typed output, literal reason tag, accurate Python execution tracing. |
| Multi-step debugging | 20 | 16 | 4 | Fix all requested functions in one raw-code answer; preserve earlier behavior. |
| Bug fixing | 12 | 10 | 2 | Rehearse minimal logic fixes and edge cases. |
| Test-driven fixing | 12 | 10 | 2 | Rehearse reading cases, return types and complete implementations. |
| Simple coding | 8 | 6 | 2 | Rehearse core algorithms and boundary conditions. |
| **Total** | **200** | **160** | **40** | **148 structured-target; 52 basic/debugging rehearsal.** |

Every new assistant target must follow `docs/TRAINING_OUTPUT_CONTRACT.md` D1.
In particular, explanation and repository targets use `output`/`reason` with
prompt-stated literal tags, never silently swap in C's legacy
`output`/`explanation` examples. Tool targets are minified JSON with exact
typed arguments. Patch targets are generated or reviewed against a
whitespace-preserving diff parser and executed after application. Raw-code
targets contain all requested functions in a single response. Validate every
example with an independent reference oracle, and inspect samples manually.
Do not include C-development examples in the training or validation split.

Use one deterministic **single-pass** schedule over the 160 training examples:
place roughly the first quarter of optimizer steps on diverse structured
format examples, then stratify the remaining steps across all categories so
the 52 basic/debugging rehearsal examples are interleaved with structured
ones. Every example is seen once in the initial experiment. Evaluate by mode
after the format warm-up and at the end, with the family-disjoint 40-example
validation set. This tests formatting gains while watching for basic-code
regressions; it is a proposal, not a run.

## Initial QLoRA proposal

Use the same pinned original base revision as earlier experiments, 4-bit NF4
with double quantization, all-linear LoRA rank 16 / alpha 32 / dropout 0.05,
batch size 1, accumulation 8, gradient checkpointing, seed 42, and one epoch.
Start at learning rate **7.5e-5**: modestly above C's 5e-5 but below B's
1e-4, as a controlled hypothesis rather than a claim that learning rate
caused C's failure. Keep max sequence length 768 if a real-tokenizer dry run
shows every example fits; otherwise document and test a 1024-token variant
before training. Never silently truncate assistant targets. Save adapter-only
checkpoints and per-mode validation, runtime, GPU memory, hashes and config.
Do not raise rank or epochs until validation behavior provides evidence.

## Gates before any future training

1. Finalize and test a versioned D validator. Prove it handles valid Python
   idioms and unified-diff whitespace while still rejecting C's malformed
   patch/tool outputs. Publish exact output schemas and tool registry.
2. Author and freeze new D-development tasks and validator, then audit
   contamination against all prior data/benchmarks. Preserve historical C
   scores without retroactive adjustment.
3. Author the D dataset only after that freeze. Validate every output, family
   split, code/diff/JSON contract and exact dataset hashes.
4. Run CPU/static tests and a real-tokenizer dry run. Confirm suitable CUDA
   hardware, package versions and expected sequence lengths before any
   separately authorized GPU training.

No D dataset, D benchmark tasks, model adapter, or training output has been
created by this postmortem.
