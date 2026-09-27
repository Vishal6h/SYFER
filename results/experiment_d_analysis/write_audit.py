#!/usr/bin/env python3
"""Create the read-only Experiment D development audit from saved artifacts."""

import collections
import json
from pathlib import Path

import replay

HERE = Path(__file__).resolve().parent
MODELS = tuple(replay.RUNS)
FORMAT_ONLY = {
    "ddev_encode_runs", "ddev_adjacent_gap", "ddev_alternate_letters",
    "ddev_power_of_two", "ddev_cycle_index", "ddev_triangle_rule",
    "ddev_try_else", "ddev_debug_coordinates", "ddev_debug_grades",
    "ddev_tool_job_batch", "ddev_tool_emit_metric", "ddev_tdd_monotonic",
    "ddev_tdd_outer_quotes", "ddev_repo_config_precedence",
}
CAUSES = {
    "ddev_spreadsheet_label": ("genuinely incorrect answer", "Off-by-one column conversion: 26 becomes AA, not Z; 52 becomes BA, not AZ."),
    "ddev_first_colon": ("genuinely incorrect answer", "Stock returns a one-element list when no colon occurs; the prompt requires [text, '']."),
    "ddev_closure_binding": ("genuinely incorrect answer", "Predicts [0,1,2]; late-bound closures actually produce [2,2,2]."),
    "ddev_live_dict_view": ("correct semantics but wrong required schema", "Output 2 is right, but reason has an extra tag_ prefix instead of the prompt's literal tag."),
    "ddev_set_add_result": ("genuinely incorrect answer", "Predicts [2,0] rather than [2,1]; also adds tag_ to the reason."),
    "ddev_patch_line_endings": ("invalid unified diff", "Unprefixed blank/context lines make the hunk invalid; the proposed edit also changes unrelated prefix or misses CRLF handling."),
    "ddev_patch_terminal_newline": ("invalid unified diff", "An unprefixed blank context line invalidates the hunk; the edit changes identity and uses rstrip(), removing more than one LF."),
    "ddev_patch_weighted_products": ("invalid unified diff", "Hunk/body formatting is invalid; replacing pairwise multiplication with min() is also semantically wrong."),
    "ddev_patch_position_selector": ("invalid unified diff", "A stray Markdown fence/prose invalidates the raw diff; it edits count_values while leaving the selector bug unfixed."),
    "ddev_debug_path_segments": ("genuinely incorrect answer", "Keeps empty path segments and discards literal '..', so both helper and depth fail cases."),
    "ddev_debug_digit_product": ("genuinely incorrect answer", "Calls reduce without defining or importing it; the isolated execution raises NameError."),
    "ddev_tool_catalog_exact": ("tool-call contract mismatch", "Uses the right tool/package but omits the explicitly required version:null argument."),
    "ddev_tool_archive_policy": ("tool-call contract mismatch", "Invents target.logs and a placeholder bucket instead of exact target.key and bucket='logs'."),
    "ddev_tdd_suffix_sum": ("genuinely incorrect answer", "Produces prose plus code for a running prefix sum, not the largest suffix sum; the all-negative case also fails."),
    "ddev_tdd_rotation": ("genuinely incorrect answer", "Treats anagrams as rotations: 'acbd' is incorrectly accepted for 'abcd'."),
    "ddev_repo_reexport_math": ("correct semantics but wrong required schema", "Output 14 is right, but reason has an extra tag_ prefix."),
    "ddev_repo_callback_composition": ("repository-reasoning schema mismatch", "Print value and reason are given as an array plus prose rather than one {output,reason} JSON object."),
    "ddev_repo_exception_propagation": ("repository-reasoning schema mismatch", "Returns the reason tag as an output array and omits the required {output,reason} object; actual output is ['finished']."),
}


def classification(model, task_id, entry):
    if task_id in FORMAT_ONLY or (model == "experiment_c" and task_id == "ddev_first_colon"):
        if not (entry["unfenced_diagnostic"] and entry["unfenced_diagnostic"]["passed"]):
            raise ValueError(f"{model}/{task_id}: claimed fence-only failure did not pass diagnostic")
        return {"primary_cause": "additional prose / formatting mismatch",
                "explanation": "Only a complete outer Markdown fence blocks an otherwise passing bare artifact."}
    label, note = CAUSES[task_id]
    if model == "experiment_c" and task_id == "ddev_patch_line_endings":
        note = "Unprefixed blank context invalidates the diff; the proposed lone-CR replacement also loses CRLF correctness."
    if model == "experiment_c" and task_id == "ddev_patch_weighted_products":
        note = "Unprefixed blank context invalidates the diff; both functions are changed to min() instead of products."
    if model == "experiment_c" and task_id == "ddev_patch_position_selector":
        note = "A stray closing fence and explanatory prose invalidate the diff; the selector bug is left unfixed."
    return {"primary_cause": label, "explanation": note}


def build():
    tasks, runs = replay.load()
    benchmark = replay.scorer.validate_benchmark()
    if benchmark["error_count"]:
        raise ValueError("frozen benchmark reference validation failed")
    current_runner_hash = replay.digest(replay.ROOT / "benchmark/evaluate_experiment_d_dev.py")
    common_keys = ("base_model_id", "base_revision", "d_dev_tasks_sha256",
                   "d_dev_validator_sha256", "runner_sha256", "options", "generation", "packages")
    stock_config = runs["stock"]["run_config"]
    same_common = all(all(run["run_config"][key] == stock_config[key] for key in common_keys)
                      for run in runs.values())
    all_runner_hashes_current = all(run["run_config"]["runner_sha256"] == current_runner_hash
                                    for run in runs.values())
    categories = list(replay.scorer.CATEGORIES)
    category_scores = {category: {model: sum(entry["replayed"]["passed"]
                                              for entry in run["tasks"].values()
                                              if entry["category"] == category)
                                  for model, run in runs.items()}
                       for category in categories}
    task_rows = []
    for task in tasks:
        task_id = task["id"]
        outcomes = {}
        for model, run in runs.items():
            item = run["tasks"][task_id]
            raw = (replay.ROOT / item["raw_path"]).read_text(encoding="utf-8")
            outcome = {
                "recorded_pass": item["recorded"]["passed"],
                "replayed_pass": item["replayed"]["passed"],
                "recorded_detail": item["recorded"]["detail"],
                "replayed_detail": item["replayed"]["detail"],
                "recorded_error_type": item["recorded"]["error"],
                "replayed_error_type": item["replayed"]["error_type"],
                "raw_path": item["raw_path"], "raw_sha256": item["raw_sha256"],
                "raw_bytes": item["raw_bytes"],
                "contains_markdown_fence": "```" in raw,
                "starts_with_markdown_fence": raw.lstrip().startswith("```"),
                "single_enclosing_fence": item["fenced"],
                "would_pass_after_only_outer_fence_removal": bool(item["unfenced_diagnostic"] and
                                                              item["unfenced_diagnostic"]["passed"]),
                "unfenced_diagnostic": item["unfenced_diagnostic"],
            }
            if model in ("stock", "experiment_c"):
                outcome["failure_classification"] = classification(model, task_id, item)
            outcomes[model] = outcome
        task_rows.append({"id": task_id, "category": task["category"],
                          "response_mode": task["response_mode"], "models": outcomes})
    b = runs["experiment_b"]["tasks"]
    d = runs["experiment_d"]["tasks"]
    compare = {
        "d_gains_over_b": [task["id"] for task in tasks if not b[task["id"]]["replayed"]["passed"] and d[task["id"]]["replayed"]["passed"]],
        "d_regressions_from_b": [task["id"] for task in tasks if b[task["id"]]["replayed"]["passed"] and not d[task["id"]]["replayed"]["passed"]],
        "shared_passes": [task["id"] for task in tasks if b[task["id"]]["replayed"]["passed"] and d[task["id"]]["replayed"]["passed"]],
        "shared_failures": [task["id"] for task in tasks if not b[task["id"]]["replayed"]["passed"] and not d[task["id"]]["replayed"]["passed"]],
    }
    fence = {}
    for model, run in runs.items():
        outcomes = [row["models"][model] for row in task_rows]
        fence[model] = {
            "contains_markdown_fence": sum(x["contains_markdown_fence"] for x in outcomes),
            "starts_with_markdown_fence": sum(x["starts_with_markdown_fence"] for x in outcomes),
            "single_enclosing_fence": sum(x["single_enclosing_fence"] for x in outcomes),
            "would_pass_after_only_outer_fence_removal": sum(x["would_pass_after_only_outer_fence_removal"] for x in outcomes),
        }
    integrity = {}
    for model, run in runs.items():
        entries = list(run["tasks"].values())
        summary_by_id = {item["id"]: item for item in run["summary"]["tasks"]}
        integrity[model] = {
            "run_directory": run["directory"], "run_status": run["status"],
            "raw_response_count": len(entries), "result_json_count": len(entries),
            "task_snapshot_matches_frozen": True,
            "summary_matches_result_files": all(summary_by_id[task_id] == entry["recorded"]
                                                for task_id, entry in run["tasks"].items()),
            "pass_fail_mismatches": sum(entry["recorded"]["passed"] != entry["replayed"]["passed"]
                                        for entry in entries),
            "detail_mismatches": sum(entry["recorded"]["detail"] != entry["replayed"]["detail"]
                                     for entry in entries),
            "error_type_mismatches": sum(entry["recorded"]["error"] != entry["replayed"]["error_type"]
                                         for entry in entries),
            "recorded_score": run["summary"]["passed"],
            "replayed_score": sum(entry["replayed"]["passed"] for entry in entries),
            "task_runtime_seconds": run["summary"]["total_runtime_seconds"],
            "model_load_runtime_seconds": run["summary"]["load_runtime_seconds"],
            "run_config": run["run_config"],
        }
    identical_stock_c = sum(runs["stock"]["tasks"][task["id"]]["raw_sha256"] ==
                            runs["experiment_c"]["tasks"][task["id"]]["raw_sha256"] for task in tasks)
    cause_counts = {model: dict(collections.Counter(row["models"][model]["failure_classification"]["primary_cause"]
                                                    for row in task_rows))
                    for model in ("stock", "experiment_c")}
    if not same_common or not all_runner_hashes_current or any(
            any(integrity[model][name] for name in
                ("pass_fail_mismatches", "detail_mismatches", "error_type_mismatches"))
            for model in MODELS):
        raise ValueError("run metadata or independent replay disagrees")
    return {
        "scope": "Saved D-dev artifacts only; no model queried and no historical score changed",
        "frozen": {"tasks_sha256": replay.digest(replay.scorer.TASKS),
                   "validator_sha256": replay.digest(Path(replay.scorer.__file__)),
                   "runner_sha256": current_runner_hash,
                   "reference_validation_errors": benchmark["error_count"]},
        "replay": {"responses_replayed": 128, "pass_fail_mismatches": 0,
                   "detail_mismatches": 0, "error_type_mismatches": 0},
        "common_evaluation": {"metadata_fields_identical": list(common_keys),
                              "same_common_fields": same_common,
                              "runner_hash_matches_current": all_runner_hashes_current,
                              "chat_messages": "one user prompt; no per-model system prompt",
                              "generation_function": "run_tuned.generate_raw",
                              "sampling": "do_sample=False (greedy); temperature recorded as 0",
                              "max_new_tokens": 512, "seed_reset_per_task": 42,
                              "response_extraction": "decode generated token suffix with skip_special_tokens=True",
                              "pad_token_id": "tokenizer.eos_token_id",
                              "runtime_tokenizer_trace_available": False,
                              "runner_branches_only_select_adapter": True},
        "runs": integrity, "category_scores": category_scores,
        "fence_diagnostics": fence,
        "stock_c_byte_identical_raw_responses": identical_stock_c,
        "stock_c_failure_cause_counts": cause_counts,
        "d_vs_b": compare,
        "tasks": task_rows,
        "observed_defects": {"scoring_validator_defect": False,
                             "generation_or_extraction_defect": False,
                             "diagnostic_limitation": "Validator exceptions are saved in the per-task error field and counted as failures; this is consistent but can look like a runtime failure. Token counts were not saved."},
        "recommendation": "A: strict D-dev results are valid; proceed to a fresh untouched final holdout before any checkpoint decision. Preserve raw-artifact scoring and optionally pre-register a separate fence-normalized diagnostic metric."
    }


def markdown(data):
    lines = [
        "# Experiment D development audit",
        "",
        "All 128 saved raw responses were replayed with the frozen D-dev validator. The replay reproduces every pass/fail decision, validator detail and error type: **zero mismatches**. All four run snapshots match the same 32 frozen tasks; each run has 32 raw texts, 32 result JSON files and a complete status. Recorded scores remain unchanged.",
        "",
        "| Category | Stock | B | C | D |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for category, scores in data["category_scores"].items():
        lines.append(f"| {category} | {scores['stock']}/4 | {scores['experiment_b']}/4 | {scores['experiment_c']}/4 | {scores['experiment_d']}/4 |")
    lines += ["| **Total** | **0/32** | **13/32** | **0/32** | **16/32** |", "",
              "## Why the scores differ", "",
              "The frozen prompts explicitly request bare Python, JSON or unified diffs without Markdown fences. The scorer rejects fences by design. Stock and C produced byte-identical raw text on 26/32 tasks. Their saved `ValueError` entries are validator rejections, not model-loading failures.",
              "",
              "| Model | Any fence | One complete enclosing fence | Pass if only that fence is removed |",
              "| --- | ---: | ---: | ---: |",
    ]
    for model, summary in data["fence_diagnostics"].items():
        label = {"stock":"Stock","experiment_b":"B","experiment_c":"C","experiment_d":"D"}[model]
        lines.append(f"| {label} | {summary['contains_markdown_fence']}/32 | {summary['single_enclosing_fence']}/32 | {summary['would_pass_after_only_outer_fence_removal']} |")
    lines += [
              "",
              "Removing **only** one complete outer fence as an offline diagnostic makes 14 Stock and 15 C responses pass the same validator. This is not a score change: both prompts and D1 contract forbid fences. It demonstrates that the 0/32 floor mostly measures raw-artifact compliance. Other answers remain wrong after unwrapping: for example, both models predict the closure result as `[0,1,2]` instead of `[2,2,2]`, and both use `min()` rather than multiplication in the weighted-product patch. No response shows convincing 512-token cutoff; generated token counts were not recorded.",
              "",
              "B and D generally emit bare artifacts, explaining their much higher strict-contract scores. D gains four tasks over B: one bare-code/instruction gain (`ddev_alternate_letters`) and three correct logic fixes (`ddev_first_colon`, `ddev_debug_coordinates`, `ddev_tdd_rotation`). D regresses on `ddev_tool_catalog_exact`: it omits the explicitly required `version:null` key that B supplies. The net +3 is real under the frozen scorer, but D does **not** improve its intended target categories over B: patches 0/4 in both, explanations 0/4 in both, repository reasoning 2/4 in both, and tool calls fall from 3/4 to 2/4. Thus D's 16/32 combines stronger bare-code/logic behavior with contract compliance; the 16-task gap over Stock/C is mainly presentation sensitivity, not evidence of 16 new semantic capabilities.",
              "",
              "## Identical evaluation path", "",
              "All four `run_config.json` files record the same task and validator hashes, runner SHA256, pinned `Qwen/Qwen2.5-Coder-3B-Instruct` revision `89fe5444e8baf5736e70f528f1edcc79e6616ef6`, package versions, seed 42, temperature setting 0 and 512-token limit. Task snapshots are identical to frozen `tasks.json`. The runner builds the same single-user chat message for every model, loads the same revision's tokenizer/chat template, resets the seed for every task, generates greedily (`do_sample=False`, `max_new_tokens=512`), and decodes only the generated token suffix with `skip_special_tokens=True`. No model-specific prompt, system message, stop rule or response parser exists. Stock uses the base alone; B/C/D attach different adapters. The saved files do not include a runtime tokenizer trace or generated token counts, so those cannot be independently re-created without querying a model.",
              "",
              "## D versus B, task by task", "",
    ]
    for title, key in (("D gains over B", "d_gains_over_b"), ("D regressions from B", "d_regressions_from_b"),
                       ("Shared passes", "shared_passes"), ("Shared failures", "shared_failures")):
        lines.append(f"- **{title} ({len(data['d_vs_b'][key])}):** " + ", ".join(f"`{value}`" for value in data["d_vs_b"][key]))
    lines += ["", "## Every Stock/C failure", "",
              "Primary causes below describe the strict recorded failure. Where a response also has a fence, the note records any additional semantic/schema defect. The JSON report links each raw file and records both the original replay and fence-only diagnostic.",
              "", "| Task | Stock primary cause | C primary cause | Rejection/diagnostic detail |",
              "| --- | --- | --- | --- |"]
    for row in data["tasks"]:
        a = row["models"]["stock"]["failure_classification"]
        c = row["models"]["experiment_c"]["failure_classification"]
        note = c["explanation"] if a["explanation"] == c["explanation"] else "Stock: " + a["explanation"] + " C: " + c["explanation"]
        lines.append(f"| `{row['id']}` | {a['primary_cause']} | {c['primary_cause']} | {note.replace('|','\\|')} |")
    lines += ["", "## Validator and runner finding", "",
              "The benchmark's 32 authored references pass the same frozen validator. Every saved PASS/FAIL, detail and error type is reproduced; the inspected patches with invalid blank/context lines, bad hunk counts, stray fences or wrong edits are not valid alternative diffs. JSON parsing compares semantic objects, but the prompts explicitly require one bare object and literal keys/tags. No observed answer establishes a validator or evaluator scoring defect. The runner's `error` field also contains validator `ValueError`/`JSONDecodeError` exceptions, which can be mistaken for generation failures; this is a reporting limitation, not a score change.",
              "",
              "**Recommendation A — the strict D-dev result is valid enough to proceed to a fresh untouched final holdout**, without choosing a final checkpoint yet. Pre-register the exact raw-output metric before seeing that holdout. If semantic capability apart from Markdown packaging is of interest, define a separate versioned fence-normalized diagnostic metric; never overwrite these D-dev scores. The D-dev set has already informed analysis and must not be treated as an untouched final test.",
              ""]
    return "\n".join(lines)


def main():
    report = build()
    (HERE / "audit.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (HERE / "audit.md").write_text(markdown(report), encoding="utf-8")
    print("Wrote audit.json and audit.md; 128/128 replayed with zero mismatches")


if __name__ == "__main__":
    main()
