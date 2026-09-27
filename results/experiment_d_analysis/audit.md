# Experiment D development audit

All 128 saved raw responses were replayed with the frozen D-dev validator. The replay reproduces every pass/fail decision, validator detail and error type: **zero mismatches**. All four run snapshots match the same 32 frozen tasks; each run has 32 raw texts, 32 result JSON files and a complete status. Recorded scores remain unchanged.

| Category | Stock | B | C | D |
| --- | ---: | ---: | ---: | ---: |
| Simple coding | 0/4 | 3/4 | 0/4 | 4/4 |
| Bug fixing | 0/4 | 3/4 | 0/4 | 4/4 |
| Code explanation | 0/4 | 0/4 | 0/4 | 0/4 |
| Patch generation | 0/4 | 0/4 | 0/4 | 0/4 |
| Multi-step debugging | 0/4 | 1/4 | 0/4 | 2/4 |
| Tool-call formatting | 0/4 | 3/4 | 0/4 | 2/4 |
| Test-driven fixing | 0/4 | 1/4 | 0/4 | 2/4 |
| Small repository reasoning | 0/4 | 2/4 | 0/4 | 2/4 |
| **Total** | **0/32** | **13/32** | **0/32** | **16/32** |

## Why the scores differ

The frozen prompts explicitly request bare Python, JSON or unified diffs without Markdown fences. The scorer rejects fences by design. Stock and C produced byte-identical raw text on 26/32 tasks. Their saved `ValueError` entries are validator rejections, not model-loading failures.

| Model | Any fence | One complete enclosing fence | Pass if only that fence is removed |
| --- | ---: | ---: | ---: |
| Stock | 31/32 | 28/32 | 14 |
| B | 1/32 | 0/32 | 0 |
| C | 29/32 | 26/32 | 15 |
| D | 3/32 | 2/32 | 0 |

Removing **only** one complete outer fence as an offline diagnostic makes 14 Stock and 15 C responses pass the same validator. This is not a score change: both prompts and D1 contract forbid fences. It demonstrates that the 0/32 floor mostly measures raw-artifact compliance. Other answers remain wrong after unwrapping: for example, both models predict the closure result as `[0,1,2]` instead of `[2,2,2]`, and both use `min()` rather than multiplication in the weighted-product patch. No response shows convincing 512-token cutoff; generated token counts were not recorded.

B and D generally emit bare artifacts, explaining their much higher strict-contract scores. D gains four tasks over B: one bare-code/instruction gain (`ddev_alternate_letters`) and three correct logic fixes (`ddev_first_colon`, `ddev_debug_coordinates`, `ddev_tdd_rotation`). D regresses on `ddev_tool_catalog_exact`: it omits the explicitly required `version:null` key that B supplies. The net +3 is real under the frozen scorer, but D does **not** improve its intended target categories over B: patches 0/4 in both, explanations 0/4 in both, repository reasoning 2/4 in both, and tool calls fall from 3/4 to 2/4. Thus D's 16/32 combines stronger bare-code/logic behavior with contract compliance; the 16-task gap over Stock/C is mainly presentation sensitivity, not evidence of 16 new semantic capabilities.

## Identical evaluation path

All four `run_config.json` files record the same task and validator hashes, runner SHA256, pinned `Qwen/Qwen2.5-Coder-3B-Instruct` revision `89fe5444e8baf5736e70f528f1edcc79e6616ef6`, package versions, seed 42, temperature setting 0 and 512-token limit. Task snapshots are identical to frozen `tasks.json`. The runner builds the same single-user chat message for every model, loads the same revision's tokenizer/chat template, resets the seed for every task, generates greedily (`do_sample=False`, `max_new_tokens=512`), and decodes only the generated token suffix with `skip_special_tokens=True`. No model-specific prompt, system message, stop rule or response parser exists. Stock uses the base alone; B/C/D attach different adapters. The saved files do not include a runtime tokenizer trace or generated token counts, so those cannot be independently re-created without querying a model.

## D versus B, task by task

- **D gains over B (4):** `ddev_alternate_letters`, `ddev_first_colon`, `ddev_debug_coordinates`, `ddev_tdd_rotation`
- **D regressions from B (1):** `ddev_tool_catalog_exact`
- **Shared passes (12):** `ddev_encode_runs`, `ddev_adjacent_gap`, `ddev_spreadsheet_label`, `ddev_power_of_two`, `ddev_cycle_index`, `ddev_triangle_rule`, `ddev_debug_grades`, `ddev_tool_job_batch`, `ddev_tool_emit_metric`, `ddev_tdd_monotonic`, `ddev_repo_reexport_math`, `ddev_repo_config_precedence`
- **Shared failures (15):** `ddev_closure_binding`, `ddev_live_dict_view`, `ddev_set_add_result`, `ddev_try_else`, `ddev_patch_line_endings`, `ddev_patch_terminal_newline`, `ddev_patch_weighted_products`, `ddev_patch_position_selector`, `ddev_debug_path_segments`, `ddev_debug_digit_product`, `ddev_tool_archive_policy`, `ddev_tdd_suffix_sum`, `ddev_tdd_outer_quotes`, `ddev_repo_callback_composition`, `ddev_repo_exception_propagation`

## Every Stock/C failure

Primary causes below describe the strict recorded failure. Where a response also has a fence, the note records any additional semantic/schema defect. The JSON report links each raw file and records both the original replay and fence-only diagnostic.

| Task | Stock primary cause | C primary cause | Rejection/diagnostic detail |
| --- | --- | --- | --- |
| `ddev_encode_runs` | additional prose / formatting mismatch | additional prose / formatting mismatch | Only a complete outer Markdown fence blocks an otherwise passing bare artifact. |
| `ddev_adjacent_gap` | additional prose / formatting mismatch | additional prose / formatting mismatch | Only a complete outer Markdown fence blocks an otherwise passing bare artifact. |
| `ddev_spreadsheet_label` | genuinely incorrect answer | genuinely incorrect answer | Off-by-one column conversion: 26 becomes AA, not Z; 52 becomes BA, not AZ. |
| `ddev_alternate_letters` | additional prose / formatting mismatch | additional prose / formatting mismatch | Only a complete outer Markdown fence blocks an otherwise passing bare artifact. |
| `ddev_power_of_two` | additional prose / formatting mismatch | additional prose / formatting mismatch | Only a complete outer Markdown fence blocks an otherwise passing bare artifact. |
| `ddev_cycle_index` | additional prose / formatting mismatch | additional prose / formatting mismatch | Only a complete outer Markdown fence blocks an otherwise passing bare artifact. |
| `ddev_first_colon` | genuinely incorrect answer | additional prose / formatting mismatch | Stock: Stock returns a one-element list when no colon occurs; the prompt requires [text, '']. C: Only a complete outer Markdown fence blocks an otherwise passing bare artifact. |
| `ddev_triangle_rule` | additional prose / formatting mismatch | additional prose / formatting mismatch | Only a complete outer Markdown fence blocks an otherwise passing bare artifact. |
| `ddev_closure_binding` | genuinely incorrect answer | genuinely incorrect answer | Predicts [0,1,2]; late-bound closures actually produce [2,2,2]. |
| `ddev_live_dict_view` | correct semantics but wrong required schema | correct semantics but wrong required schema | Output 2 is right, but reason has an extra tag_ prefix instead of the prompt's literal tag. |
| `ddev_set_add_result` | genuinely incorrect answer | genuinely incorrect answer | Predicts [2,0] rather than [2,1]; also adds tag_ to the reason. |
| `ddev_try_else` | additional prose / formatting mismatch | additional prose / formatting mismatch | Only a complete outer Markdown fence blocks an otherwise passing bare artifact. |
| `ddev_patch_line_endings` | invalid unified diff | invalid unified diff | Stock: Unprefixed blank/context lines make the hunk invalid; the proposed edit also changes unrelated prefix or misses CRLF handling. C: Unprefixed blank context invalidates the diff; the proposed lone-CR replacement also loses CRLF correctness. |
| `ddev_patch_terminal_newline` | invalid unified diff | invalid unified diff | An unprefixed blank context line invalidates the hunk; the edit changes identity and uses rstrip(), removing more than one LF. |
| `ddev_patch_weighted_products` | invalid unified diff | invalid unified diff | Stock: Hunk/body formatting is invalid; replacing pairwise multiplication with min() is also semantically wrong. C: Unprefixed blank context invalidates the diff; both functions are changed to min() instead of products. |
| `ddev_patch_position_selector` | invalid unified diff | invalid unified diff | Stock: A stray Markdown fence/prose invalidates the raw diff; it edits count_values while leaving the selector bug unfixed. C: A stray closing fence and explanatory prose invalidate the diff; the selector bug is left unfixed. |
| `ddev_debug_coordinates` | additional prose / formatting mismatch | additional prose / formatting mismatch | Only a complete outer Markdown fence blocks an otherwise passing bare artifact. |
| `ddev_debug_path_segments` | genuinely incorrect answer | genuinely incorrect answer | Keeps empty path segments and discards literal '..', so both helper and depth fail cases. |
| `ddev_debug_grades` | additional prose / formatting mismatch | additional prose / formatting mismatch | Only a complete outer Markdown fence blocks an otherwise passing bare artifact. |
| `ddev_debug_digit_product` | genuinely incorrect answer | genuinely incorrect answer | Calls reduce without defining or importing it; the isolated execution raises NameError. |
| `ddev_tool_catalog_exact` | tool-call contract mismatch | tool-call contract mismatch | Uses the right tool/package but omits the explicitly required version:null argument. |
| `ddev_tool_job_batch` | additional prose / formatting mismatch | additional prose / formatting mismatch | Only a complete outer Markdown fence blocks an otherwise passing bare artifact. |
| `ddev_tool_emit_metric` | additional prose / formatting mismatch | additional prose / formatting mismatch | Only a complete outer Markdown fence blocks an otherwise passing bare artifact. |
| `ddev_tool_archive_policy` | tool-call contract mismatch | tool-call contract mismatch | Invents target.logs and a placeholder bucket instead of exact target.key and bucket='logs'. |
| `ddev_tdd_monotonic` | additional prose / formatting mismatch | additional prose / formatting mismatch | Only a complete outer Markdown fence blocks an otherwise passing bare artifact. |
| `ddev_tdd_suffix_sum` | genuinely incorrect answer | genuinely incorrect answer | Produces prose plus code for a running prefix sum, not the largest suffix sum; the all-negative case also fails. |
| `ddev_tdd_rotation` | genuinely incorrect answer | genuinely incorrect answer | Treats anagrams as rotations: 'acbd' is incorrectly accepted for 'abcd'. |
| `ddev_tdd_outer_quotes` | additional prose / formatting mismatch | additional prose / formatting mismatch | Only a complete outer Markdown fence blocks an otherwise passing bare artifact. |
| `ddev_repo_reexport_math` | correct semantics but wrong required schema | correct semantics but wrong required schema | Output 14 is right, but reason has an extra tag_ prefix. |
| `ddev_repo_callback_composition` | repository-reasoning schema mismatch | repository-reasoning schema mismatch | Print value and reason are given as an array plus prose rather than one {output,reason} JSON object. |
| `ddev_repo_exception_propagation` | repository-reasoning schema mismatch | repository-reasoning schema mismatch | Returns the reason tag as an output array and omits the required {output,reason} object; actual output is ['finished']. |
| `ddev_repo_config_precedence` | additional prose / formatting mismatch | additional prose / formatting mismatch | Only a complete outer Markdown fence blocks an otherwise passing bare artifact. |

## Validator and runner finding

The benchmark's 32 authored references pass the same frozen validator. Every saved PASS/FAIL, detail and error type is reproduced; the inspected patches with invalid blank/context lines, bad hunk counts, stray fences or wrong edits are not valid alternative diffs. JSON parsing compares semantic objects, but the prompts explicitly require one bare object and literal keys/tags. No observed answer establishes a validator or evaluator scoring defect. The runner's `error` field also contains validator `ValueError`/`JSONDecodeError` exceptions, which can be mistaken for generation failures; this is a reporting limitation, not a score change.

**Recommendation A — the strict D-dev result is valid enough to proceed to a fresh untouched final holdout**, without choosing a final checkpoint yet. Pre-register the exact raw-output metric before seeing that holdout. If semantic capability apart from Markdown packaging is of interest, define a separate versioned fence-normalized diagnostic metric; never overwrite these D-dev scores. The D-dev set has already informed analysis and must not be treated as an untouched final test.
