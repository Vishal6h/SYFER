# Experiment A: five frozen benchmark failures

Evidence: the user-supplied Stage 6 comparison (11/16 tuned versus 6/16
stock) and the five user-supplied tuned response texts, checked against the
unchanged `benchmark/tasks.json` and `benchmark/run_baseline.py` validator.
The Lightning `results/tuned/<run>/` directory is not in this workspace, so
the response texts are user-supplied rather than verified against files here.
The final `%` printed after the `repo_call_chain` closing brace may be a shell
prompt artifact; the chain is wrong with or without that character.

| Task | Tuned response and exact failure | Cause | Stock comparison | Related Stage 2 coverage |
| --- | --- | --- | --- | --- |
| `simple_dedupe` | Compared each integer only with `result[-1]`. Frozen case `[3,1,3,2,1]` returned `[3,1,3,2,1]`, expected `[3,1,2]`. | Algorithmic logic: adjacent-run compression instead of first-occurrence deduplication. | Stock made the same adjacent-only mistake. | `running_totals` and `vowel_count` cover simple loops, but no first-occurrence deduplication family. |
| `bug_last_index` | Assigned `last_index = i` only on matches, then returned it. Missing-target and empty-list cases raise `UnboundLocalError` because the variable has no initial value. The repeated-target case does return the final index. | Variable initialization/state bug; fix is incomplete across boundary cases. | Stock returned the original first-match logic unchanged. | `strict_threshold` teaches first-match index, not last-match state. |
| `explain_slice` | JSON keys and explanation format are valid, but `output` was `19`; the selected values are 5 and 11, so the required integer is 16. | Arithmetic/trace inconsistency: the explanation identifies the right values but the answer does not add them correctly. | Stock returned 16 and passed, making this the one regression. | `stride_two` slice explanations occur in Stage 2 validation; the original training split has mutation/copy examples but no slice-sum family. |
| `patch_slug` | Hunk header declares `@@ -1,2 +1,3 @@` but the body contains **four** added lines. The frozen parser raises `ValueError: hunk line counts do not match`. The proposed `if not text.strip()` also follows an unconditional `return`, so it is unreachable. | Invalid unified-diff structure, plus dead code in the proposed fix. | Stock also produced invalid hunk counts, though its proposed code differed. | Stage 2 patch families cover small diffs, but not this multi-whitespace behavior. |
| `repo_call_chain` | Returned the correct `file` (`totals.py`) but chain `['sum_amounts']` instead of the full entry-to-target chain `['run','build_report','sum_amounts']`. | Repository call-chain reasoning: omitted caller functions. | Stock omitted the same callers. | Stage 2 already has a `call_chain` training family, so this is a generalization failure rather than missing category coverage. |

The diagnoses above follow the frozen validator's behavior. The Python and
patch responses were checked through its isolated execution/diff routines;
the JSON responses were checked against its exact field/value requirements.
No benchmark prompt, response, validator, or case was changed.

## Experiment B data response

The new examples teach first-occurrence tracking across different data
shapes, initialized state for final-match search, consistent JSON arithmetic,
valid unified-diff hunk lengths with whitespace handling, and complete
multi-file call chains. They use different functions, values, file names, and
code contexts from the frozen tasks. A small rehearsal set retains tool-call,
multi-step debugging, and test-driven behaviors that Experiment A passed.
The combined 190/60 split includes all original Stage 2 examples intact plus
60/20 new targeted examples. Dataset validation executes the code/patch
examples and checks JSON, exact prompt duplicates, benchmark contamination,
and train/validation family separation.

Experiment B starts from the original pinned base. One epoch is chosen because
Experiment A already reached about 0.3117 validation loss after one epoch;
raising rank to 16 while also doubling epochs would compound overfitting and
forgetting risk before measuring whether these targeted cases help. A later
evaluation must confirm whether B actually repairs these failures without
regressing the 11 tasks Experiment A passed.
