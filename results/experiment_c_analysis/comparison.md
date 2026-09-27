# Stock vs Experiment B vs Experiment C: C-development error analysis

This is a 32-task **development** benchmark, not an untouched final holdout for a future model. This report reads the three completed runs; it does not change their scores or select a final SYFER checkpoint.

All three runs have 32 raw responses and 32 matching per-task result files. Re-scoring every raw response with the frozen validator reproduced all 96 pass/fail decisions. They share the same task, validator, runner, base-revision and generation-setting hashes; generation used temperature 0, 512 new tokens and seed 42.

| Model | Score | Task runtime | Run |
| --- | ---: | ---: | --- |
| Stock | 10/32 (31.25%) | 237.24 s | `20260926T164239Z-c34b32bd` |
| B | 8/32 (25.0%) | 280.775 s | `20260926T164725Z-485d87c2` |
| C | 10/32 (31.25%) | 429.699 s | `20260926T165628Z-dcad18d5` |

## Category scores

| Category | Stock | B | C | C vs Stock | C vs B |
| --- | ---: | ---: | ---: | ---: | ---: |
| Bug fixing | 3/4 | 2/4 | 3/4 | +0 | +1 |
| Code explanation | 0/4 | 0/4 | 0/4 | +0 | +0 |
| Multi-step debugging | 1/4 | 1/4 | 1/4 | +0 | +0 |
| Patch generation | 0/4 | 0/4 | 0/4 | +0 | +0 |
| Simple coding | 3/4 | 3/4 | 3/4 | +0 | +0 |
| Small repository reasoning | 0/4 | 0/4 | 0/4 | +0 | +0 |
| Test-driven fixing | 3/4 | 2/4 | 3/4 | +0 | +1 |
| Tool-call formatting | 0/4 | 0/4 | 0/4 | +0 | +0 |

## Task-level outcomes

P = validator pass; F = validator failure. Raw response links and their SHA-256 hashes are in the JSON report.

| Task | Category | Stock | B | C |
| --- | --- | :---: | :---: | :---: |
| `cdev_interleave` | Simple coding | P | P | P |
| `cdev_hamming` | Simple coding | P | P | P |
| `cdev_border_sum` | Simple coding | F | F | F |
| `cdev_seat_position` | Simple coding | P | P | P |
| `cdev_prime_square` | Bug fixing | P | P | P |
| `cdev_stable_partition` | Bug fixing | P | P | P |
| `cdev_gcd_one` | Bug fixing | P | F | P |
| `cdev_percent_decode` | Bug fixing | F | F | F |
| `cdev_generator_exhaustion` | Code explanation | F | F | F |
| `cdev_mutable_default` | Code explanation | F | F | F |
| `cdev_loop_else` | Code explanation | F | F | F |
| `cdev_comprehension_scope` | Code explanation | F | F | F |
| `cdev_patch_escape` | Patch generation | F | F | F |
| `cdev_patch_priority` | Patch generation | F | F | F |
| `cdev_patch_none` | Patch generation | F | F | F |
| `cdev_patch_mask` | Patch generation | F | F | F |
| `cdev_debug_word_score` | Multi-step debugging | F | F | F |
| `cdev_debug_grid_neighbors` | Multi-step debugging | P | F | P |
| `cdev_debug_ranges` | Multi-step debugging | F | F | F |
| `cdev_debug_money` | Multi-step debugging | F | P | F |
| `cdev_tool_edit_plan` | Tool-call formatting | F | F | F |
| `cdev_tool_test_plan` | Tool-call formatting | F | F | F |
| `cdev_tool_review` | Tool-call formatting | F | F | F |
| `cdev_tool_two_steps` | Tool-call formatting | F | F | F |
| `cdev_tdd_subsequence` | Test-driven fixing | F | F | F |
| `cdev_tdd_ordinal` | Test-driven fixing | P | P | P |
| `cdev_tdd_anagram` | Test-driven fixing | P | P | P |
| `cdev_tdd_ipv4` | Test-driven fixing | P | F | P |
| `cdev_repo_overlay` | Small repository reasoning | F | F | F |
| `cdev_repo_callback` | Small repository reasoning | F | F | F |
| `cdev_repo_import_cache` | Small repository reasoning | F | F | F |
| `cdev_repo_lazy_import` | Small repository reasoning | F | F | F |

## Changes and overlap

**Stock passed, C failed:** None.
**Stock failed, C passed:** None.
**B passed, C failed:** `cdev_debug_money`.
**B failed, C passed:** `cdev_gcd_one`, `cdev_debug_grid_neighbors`, `cdev_tdd_ipv4`.

Stock and C passed the **same ten tasks**: 10 unchanged passes and 22 unchanged failures. Stock/C unchanged passes: `cdev_interleave`, `cdev_hamming`, `cdev_seat_position`, `cdev_prime_square`, `cdev_stable_partition`, `cdev_gcd_one`, `cdev_debug_grid_neighbors`, `cdev_tdd_ordinal`, `cdev_tdd_anagram`, `cdev_tdd_ipv4`. Stock/C unchanged failures: `cdev_border_sum`, `cdev_percent_decode`, `cdev_generator_exhaustion`, `cdev_mutable_default`, `cdev_loop_else`, `cdev_comprehension_scope`, `cdev_patch_escape`, `cdev_patch_priority`, `cdev_patch_none`, `cdev_patch_mask`, `cdev_debug_word_score`, `cdev_debug_ranges`, `cdev_debug_money`, `cdev_tool_edit_plan`, `cdev_tool_test_plan`, `cdev_tool_review`, `cdev_tool_two_steps`, `cdev_tdd_subsequence`, `cdev_repo_overlay`, `cdev_repo_callback`, `cdev_repo_import_cache`, `cdev_repo_lazy_import`. B and C share 7 passes and 21 failures. B/C unchanged passes: `cdev_interleave`, `cdev_hamming`, `cdev_seat_position`, `cdev_prime_square`, `cdev_stable_partition`, `cdev_tdd_ordinal`, `cdev_tdd_anagram`. B/C unchanged failures: `cdev_border_sum`, `cdev_percent_decode`, `cdev_generator_exhaustion`, `cdev_mutable_default`, `cdev_loop_else`, `cdev_comprehension_scope`, `cdev_patch_escape`, `cdev_patch_priority`, `cdev_patch_none`, `cdev_patch_mask`, `cdev_debug_word_score`, `cdev_debug_ranges`, `cdev_tool_edit_plan`, `cdev_tool_test_plan`, `cdev_tool_review`, `cdev_tool_two_steps`, `cdev_tdd_subsequence`, `cdev_repo_overlay`, `cdev_repo_callback`, `cdev_repo_import_cache`, `cdev_repo_lazy_import`. All three share these 7 passes: `cdev_interleave`, `cdev_hamming`, `cdev_seat_position`, `cdev_prime_square`, `cdev_stable_partition`, `cdev_tdd_ordinal`, `cdev_tdd_anagram`.

All three share these 21 failures: `cdev_border_sum`, `cdev_percent_decode`, `cdev_generator_exhaustion`, `cdev_mutable_default`, `cdev_loop_else`, `cdev_comprehension_scope`, `cdev_patch_escape`, `cdev_patch_priority`, `cdev_patch_none`, `cdev_patch_mask`, `cdev_debug_word_score`, `cdev_debug_ranges`, `cdev_tool_edit_plan`, `cdev_tool_test_plan`, `cdev_tool_review`, `cdev_tool_two_steps`, `cdev_tdd_subsequence`, `cdev_repo_overlay`, `cdev_repo_callback`, `cdev_repo_import_cache`, `cdev_repo_lazy_import`.

Stock and C raw responses are byte-for-byte identical on 20/32 tasks, including all four patch tasks. The other 12 raw responses differ without changing Stock-to-C pass/fail status.

## Every Experiment C failure

The primary cause labels follow the requested taxonomy. Each explanation distinguishes the validator's immediate rejection from additional errors visible in the raw answer. The frozen code scorer extracts only the first fenced block; JSON and tool-call scorers compare the raw response without removing fences. A blank context line in a unified diff must begin with one space.

- **`cdev_border_sum` — algorithmic reasoning error.** The first Python case failure is case 2: the one-row grid should sum to 15, but the code sums the same row as both top and bottom and returns 30. [Raw response](../experiment_c_dev/experiment_c/20260926T165628Z-dcad18d5/cdev_border_sum.txt). Validator detail: `[{"case":2,"expected":15,"actual":30}]`.
- **`cdev_percent_decode` — bug-fixing logic error.** Case 2 expects /% from %2f%25, but the function leaves lowercase %2f unchanged and returns %2f%. It repeats the broken case-sensitive replacement. [Raw response](../experiment_c_dev/experiment_c/20260926T165628Z-dcad18d5/cdev_percent_decode.txt). Validator detail: `[{"case":2,"expected":"/%","actual":"%2f%"}]`.
- **`cdev_generator_exhaustion` — malformed JSON/schema.** Raw output begins with a JSON Markdown fence, so json.loads rejects it at character 0. Inside the fence the output is [14,0] instead of [13,0], and reason is prose rather than generator_is_exhausted. [Raw response](../experiment_c_dev/experiment_c/20260926T165628Z-dcad18d5/cdev_generator_exhaustion.txt). Validator detail: `"Expecting value: line 1 column 1 (char 0)"`.
- **`cdev_mutable_default` — malformed JSON/schema.** The Markdown fence causes JSONDecodeError at character 0. The inner output [1,2] is correct, but reason is prose rather than the required default_list_persists tag. [Raw response](../experiment_c_dev/experiment_c/20260926T165628Z-dcad18d5/cdev_mutable_default.txt). Validator detail: `"Expecting value: line 1 column 1 (char 0)"`.
- **`cdev_loop_else` — malformed JSON/schema.** The Markdown fence causes JSONDecodeError at character 0. The inner output is also 0 instead of 1: no break occurs, so the for-else appends none. [Raw response](../experiment_c_dev/experiment_c/20260926T165628Z-dcad18d5/cdev_loop_else.txt). Validator detail: `"Expecting value: line 1 column 1 (char 0)"`.
- **`cdev_comprehension_scope` — malformed JSON/schema.** The Markdown fence causes JSONDecodeError at character 0. The inner output [9,3] is correct, but reason is prose rather than comprehension_has_own_scope. [Raw response](../experiment_c_dev/experiment_c/20260926T165628Z-dcad18d5/cdev_comprehension_scope.txt). Validator detail: `"Expecting value: line 1 column 1 (char 0)"`.
- **`cdev_patch_escape` — invalid unified diff.** The empty context line has no leading space, so the diff parser raises invalid diff line before applying it. The patch also changes unrelated label(), escapes less-than before ampersand, and adds a greater-than escape. [Raw response](../experiment_c_dev/experiment_c/20260926T165628Z-dcad18d5/cdev_patch_escape.txt). Validator detail: `"invalid diff line"`.
- **`cdev_patch_priority` — invalid unified diff.** The empty context line has no leading space, so the parser raises invalid diff line. The patch changes unrelated count_jobs() and leaves reverse=True, so priority order remains wrong. [Raw response](../experiment_c_dev/experiment_c/20260926T165628Z-dcad18d5/cdev_patch_priority.txt). Validator detail: `"invalid diff line"`.
- **`cdev_patch_none` — invalid unified diff.** The empty context line lacks the required leading space; the hunk header also does not describe the shown lines. The patch changes unrelated item_count() and leaves the truthiness filter, which still drops 0, False, and empty strings. [Raw response](../experiment_c_dev/experiment_c/20260926T165628Z-dcad18d5/cdev_patch_none.txt). Validator detail: `"invalid diff line"`.
- **`cdev_patch_mask` — invalid unified diff.** The empty context line lacks its leading space, so the parser raises invalid diff line. The mask_card() change looks compatible with supplied cases, but unrelated display_label() is changed. [Raw response](../experiment_c_dev/experiment_c/20260926T165628Z-dcad18d5/cdev_patch_mask.txt). Validator detail: `"invalid diff line"`.
- **`cdev_debug_word_score` — bug-fixing logic error.** Cases 1-3 raise NameError because the frozen sandbox excludes ord. Even with ord available, the code sums ASCII code points instead of alphabet positions (cab would score 294, not 6). [Raw response](../experiment_c_dev/experiment_c/20260926T165628Z-dcad18d5/cdev_debug_word_score.txt). Validator detail: `[{"case":1,"error":"NameError: name 'ord' is not defined"},{"case":2,"error":"NameError: name 'ord' is not defined"},{"case":3,"error":"NameError: name 'ord' is not defined"}]`.
- **`cdev_debug_ranges` — bug-fixing logic error.** Cases 1 and 3 return a list of tuples instead of the required list of lists; JSON rendering makes the displayed values look equal, but Python equality fails. Case 2 returns 9 instead of 7 because covered_length keeps the old inclusive +1 for half-open ranges. [Raw response](../experiment_c_dev/experiment_c/20260926T165628Z-dcad18d5/cdev_debug_ranges.txt). Validator detail: `[{"case":1,"expected":[[1,7],[9,10]],"actual":[[1,7],[9,10]]},{"case":2,"expected":7,"actual":9},{"case":3,"expected":[[0,5]],"actual":[[0,5]]}]`.
- **`cdev_debug_money` — incomplete answer.** code_only extracts only the first fenced Python block, containing parse_money. total_cents is in a second fenced block and is absent from the executed scope, giving KeyError on cases 3 and 4. [Raw response](../experiment_c_dev/experiment_c/20260926T165628Z-dcad18d5/cdev_debug_money.txt). Validator detail: `[{"case":3,"error":"KeyError: 'total_cents'"},{"case":4,"error":"KeyError: 'total_cents'"}]`.
- **`cdev_tool_edit_plan` — tool-selection/tool-argument error.** The validator requires the exact minified tool/arguments object. The response is fenced, pretty-printed, nests plan.file_edit instead of tool=plan_file_edit, and adds an unrequested text field. [Raw response](../experiment_c_dev/experiment_c/20260926T165628Z-dcad18d5/cdev_tool_edit_plan.txt). Validator detail: `"mock call differs"`.
- **`cdev_tool_test_plan` — tool-selection/tool-argument error.** The response is fenced and pretty-printed, omits the required tool key, and puts plan_test_run in arguments.suite instead of using tool=plan_test_run and suite=unit. [Raw response](../experiment_c_dev/experiment_c/20260926T165628Z-dcad18d5/cdev_tool_test_plan.txt). Validator detail: `"mock call differs"`.
- **`cdev_tool_review` — tool-selection/tool-argument error.** The response is fenced and pretty-printed, uses request_review as a top-level key instead of tool, and inserts an extra scope.object level. [Raw response](../experiment_c_dev/experiment_c/20260926T165628Z-dcad18d5/cdev_tool_review.txt). Validator detail: `"mock call differs"`.
- **`cdev_tool_two_steps` — malformed JSON/schema.** The response is YAML in a Markdown fence, not the required minified JSON tool/arguments object; it also uses file and unit_suite rather than the required path and unit values. [Raw response](../experiment_c_dev/experiment_c/20260926T165628Z-dcad18d5/cdev_tool_two_steps.txt). Validator detail: `"mock call differs"`.
- **`cdev_tdd_subsequence` — validator edge-case mismatch.** The extracted Python uses iter(long), a correct standard-Python subsequence idiom for these five cases. The frozen sandbox omits iter from allowed builtins, so every case raises NameError before the logic is assessed. [Raw response](../experiment_c_dev/experiment_c/20260926T165628Z-dcad18d5/cdev_tdd_subsequence.txt). Validator detail: `[{"case":1,"error":"NameError: name 'iter' is not defined"},{"case":2,"error":"NameError: name 'iter' is not defined"},{"case":3,"error":"NameError: name 'iter' is not defined"},{"case":4,"error":"NameError: name 'iter' is not defined"},{"case":5,"error":"NameError: name 'iter' is not defined"}]`.
- **`cdev_repo_overlay` — malformed JSON/schema.** The Markdown fence causes JSONDecodeError at character 0. The inner output 30 is right, but reason is prose instead of the exact later_overlay_wins tag. [Raw response](../experiment_c_dev/experiment_c/20260926T165628Z-dcad18d5/cdev_repo_overlay.txt). Validator detail: `"Expecting value: line 1 column 1 (char 0)"`.
- **`cdev_repo_callback` — malformed JSON/schema.** The Markdown fence causes JSONDecodeError at character 0. The inner output GO! is right, but reason is prose instead of the exact injected_callback tag. [Raw response](../experiment_c_dev/experiment_c/20260926T165628Z-dcad18d5/cdev_repo_callback.txt). Validator detail: `"Expecting value: line 1 column 1 (char 0)"`.
- **`cdev_repo_import_cache` — repository reasoning error.** The raw Markdown fence first causes JSONDecodeError. Even without it, output=2 is wrong: importing tracker twice runs its top-level increment once, so output must be 1. [Raw response](../experiment_c_dev/experiment_c/20260926T165628Z-dcad18d5/cdev_repo_import_cache.txt). Validator detail: `"Expecting value: line 1 column 1 (char 0)"`.
- **`cdev_repo_lazy_import` — instruction-following/output-format error.** The inner JSON has the correct output 12 and exact import_inside_function reason tag. The raw Markdown fence alone causes JSONDecodeError at character 0. [Raw response](../experiment_c_dev/experiment_c/20260926T165628Z-dcad18d5/cdev_repo_lazy_import.txt). Validator detail: `"Expecting value: line 1 column 1 (char 0)"`.

Cause counts across C's 22 failures: algorithmic reasoning error 1, bug-fixing logic error 3, incomplete answer 1, instruction-following/output-format error 1, invalid unified diff 4, malformed JSON/schema 7, repository reasoning error 1, tool-selection/tool-argument error 3, validator edge-case mismatch 1.

## What the target-area results mean

- **Patches:** Stock, B and C each scored 0/4. C's four patches contain unprefixed blank context lines; none reaches code execution. Three also visibly alter unrelated functions or leave the requested defect in place. All four C raw patches exactly match Stock's.
- **Tool calls:** all three scored 0/4. C emitted fenced pretty JSON with wrong top-level structure on three tasks and YAML on the fourth. The mock protocol requires one exact minified JSON object with tool and arguments; no real tools were invoked.
- **Repository reasoning:** all three scored 0/4. C computes the result value correctly on overlay, callback and lazy import, but the raw JSON format or exact reason tag fails. C incorrectly predicts 2 rather than 1 for the cached import task. B's overlay and callback answers were bare JSON but still used prose instead of the required reason tag; C returned to fenced JSON.

A temporary diagnostic changed only the allowed builtins in an in-memory copy of the harness: adding iter makes C's subsequence answer pass all five cases; adding ord still leaves word_score wrong (294 instead of 6 on cab). Neither frozen validator nor saved run was changed.

## Basic-capability preservation

- Simple coding remains 3/4 for Stock, B and C; border_sum still double-counts a single-row grid.
- Bug fixing is 3/4 for Stock and C versus 2/4 for B. C recovers gcd_one but still misses lowercase percent escapes.
- Test-driven fixing is 3/4 for Stock and C versus 2/4 for B. C recovers ipv4. On subsequence, C's algorithm is valid standard Python, but the frozen sandbox does not expose iter.
- Multi-step debugging is 1/4 for each, but the passed task changes: B passes debug_money; Stock and C pass debug_grid_neighbors. C's two separately fenced functions cause only the first to be executed on debug_money.

## Technical path

**C — Rework dataset/validators before any new training.** The intended target areas show no measured improvement, and C ties Stock on the exact same ten tasks. The C training examples for explanation and repository reasoning use an output/explanation schema, while the development tasks require output/reason with exact tags. The frozen Python harness also excludes valid builtins such as iter and ord; this changes how some failures should be interpreted. Audit the dataset-to-task format alignment and version any future validator changes while preserving these recorded scores. This is evidence for a next training decision, **not** a final SYFER checkpoint decision.
