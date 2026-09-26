#!/usr/bin/env python3
"""Model-free, full-reference validation for the versioned D1 dataset."""

import collections
import difflib
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT / "benchmark/experiment_d_dev"))
import validate_d_dev as scorer

TRAIN = HERE / "experiment_d_train.jsonl"
VALIDATION = HERE / "experiment_d_validation.jsonl"
COUNTS = {"Patch generation":40,"Tool-call formatting":36,"Small repository reasoning":32,
          "Code explanation":28,"Simple coding":16,"Bug fixing":16,
          "Multi-step debugging":16,"Test-driven fixing":16}
BENCHMARKS = [ROOT / "benchmark/tasks.json",ROOT / "benchmark/final_holdout/tasks.json",
              ROOT / "benchmark/experiment_c_dev/tasks.json",
              ROOT / "benchmark/experiment_d_dev/tasks.json"]
OLD_DATA = list(scorer.EARLIER[3:])


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalized(text):
    return " ".join(re.findall(r"[a-z0-9]+",text.casefold()))


def prior_prompts():
    items = []
    for path in BENCHMARKS:
        for task in json.loads(path.read_text(encoding="utf-8")):
            items.append((str(path.relative_to(ROOT)),task["prompt"],task.get("id",""),task["category"]))
    for path in OLD_DATA:
        with path.open(encoding="utf-8") as stream:
            for line in stream:
                record = json.loads(line)
                items.append((str(path.relative_to(ROOT)),
                              next(msg["content"] for msg in record["messages"] if msg["role"]=="user"),
                              record.get("family",""),record["category"]))
    return items


def inspect():
    errors = []
    records = []
    for split,path in (("train",TRAIN),("validation",VALIDATION)):
        with path.open(encoding="utf-8") as stream:
            for line_no,line in enumerate(stream,1):
                try:
                    record = json.loads(line)
                except json.JSONDecodeError as error:
                    errors.append(f"{split}:{line_no}: malformed JSONL: {error}")
                    continue
                records.append((split,line_no,record))
    category_counts = collections.Counter()
    difficulty_counts = collections.Counter()
    prompts = collections.Counter()
    normalized_prompts = collections.Counter()
    families = collections.defaultdict(set)
    mode_counts = collections.Counter()
    diff_count = json_count = code_count = 0
    patch_features = collections.Counter()
    for split,line_no,record in records:
        label = f"{split}:{line_no}"
        try:
            required = {"messages","category","source","difficulty","family","response_mode",
                        "contract_version","checks"}
            if set(record) != required:
                raise ValueError(f"record keys must be {sorted(required)}")
            messages = record["messages"]
            if [message["role"] for message in messages] != ["system","user","assistant"]:
                raise ValueError("message roles/order must be system,user,assistant")
            if any(not isinstance(message["content"],str) or not message["content"].strip()
                   for message in messages):
                raise ValueError("empty or nonstring message content")
            if record["category"] not in COUNTS or record["response_mode"] != scorer.MODES[record["category"]]:
                raise ValueError("category/response_mode mismatch")
            if record["contract_version"] != "D1" or record["source"] != "experiment_d_authored_v1":
                raise ValueError("contract/source mismatch")
            if record["difficulty"] not in {"easy","medium","hard"}:
                raise ValueError("invalid difficulty")
            if record["checks"]["response_mode"] != record["response_mode"]:
                raise ValueError("checks response_mode mismatch")
            prompt,answer = messages[1]["content"],messages[2]["content"]
            prompts[prompt] += 1
            normalized_prompts[normalized(prompt)] += 1
            families[split].add(record["family"])
            category_counts[record["category"]] += 1
            difficulty_counts[record["difficulty"]] += 1
            mode_counts[record["response_mode"]] += 1
            passed,detail = scorer.validate_response(record["checks"],answer)
            if not passed:
                raise ValueError(f"reference failed scorer: {detail}")
            if record["response_mode"] == "unified_diff":
                diff_count += 1
                if split == "train":
                    hunks = [scorer.HUNK.fullmatch(line) for line in answer.splitlines()
                             if line.startswith("@@ ")]
                    if len(hunks) > 1:
                        patch_features["multiple_hunks"] += 1
                    if any(int(match.group(4) or "1") > int(match.group(2) or "1") for match in hunks):
                        patch_features["insertion"] += 1
                    if any(int(match.group(2) or "1") > int(match.group(4) or "1") for match in hunks):
                        patch_features["deletion"] += 1
                    if record["family"] == "d_patch_whitespace":
                        patch_features["whitespace_preservation"] += 1
                patched = scorer.apply_unified_diff(record["checks"]["source"],answer,
                                                   record["checks"]["path"])
                if patched != record["checks"]["expected_source"]:
                    raise ValueError("patch produces source other than the authored target")
            elif record["response_mode"] == "python_code":
                code_count += 1
            else:
                json_count += 1
                parsed = scorer.parse_json(answer)
                if not scorer.same_type_value(parsed,record["checks"]["expected"]):
                    raise ValueError("JSON target mismatch")
                if record["response_mode"] in {"explanation_json","repository_reasoning_json"}:
                    if parsed["output"] != scorer.run_oracle(record["checks"]):
                        raise ValueError("structured output differs from executable oracle")
                    if set(parsed) != {"output","reason"} or "explanation" in parsed:
                        raise ValueError("D1 output/reason schema mismatch")
        except (KeyError,TypeError,ValueError,IndexError) as error:
            errors.append(f"{label}: {error}")
    exact_duplicates = sum(count-1 for count in prompts.values() if count > 1)
    normalized_duplicates = sum(count-1 for count in normalized_prompts.values() if count > 1)
    if exact_duplicates:
        errors.append(f"{exact_duplicates} exact duplicate prompts")
    if normalized_duplicates:
        errors.append(f"{normalized_duplicates} normalized duplicate prompts")
    overlap = sorted(families["train"] & families["validation"])
    if overlap:
        errors.append(f"train/validation family overlap: {overlap}")
    if len(records) != 200 or sum(split=="train" for split,_,_ in records) != 160:
        errors.append("dataset must have exactly 160 train and 40 validation examples")
    if dict(category_counts) != COUNTS:
        errors.append(f"category counts differ from required balance: {dict(category_counts)}")
    if any(patch_features[name] == 0 for name in
           ("multiple_hunks","insertion","deletion","whitespace_preservation")):
        errors.append(f"patch training coverage missing: {dict(patch_features)}")
    prior = prior_prompts()
    exact = {text for _,text,_,_ in prior}
    normalized_prior = {normalized(text) for _,text,_,_ in prior}
    by_category = collections.defaultdict(list)
    for source,text,family,category in prior:
        by_category[category].append((source,text,family,normalized(text)))
    contamination = {"exact_prompt":0,"normalized_prompt":0,"suspicious_similarity":0}
    suspicious = []
    for split,line_no,record in records:
        prompt = record["messages"][1]["content"]
        if prompt in exact:
            contamination["exact_prompt"] += 1
        if normalized(prompt) in normalized_prior:
            contamination["normalized_prompt"] += 1
        candidate = normalized(prompt)
        for source,other,family,prior_normal in by_category[record["category"]]:
            if record.get("family") == family:
                suspicious.append((split,line_no,source,family,"family name"))
                continue
            if min(len(candidate),len(prior_normal)) / max(len(candidate),len(prior_normal)) < .84:
                continue
            matcher = difflib.SequenceMatcher(None,candidate,prior_normal,autojunk=True)
            if matcher.quick_ratio() < .84:
                continue
            ratio = matcher.ratio()
            if ratio >= .84:
                suspicious.append((split,line_no,source,family,round(ratio,3)))
    contamination["suspicious_similarity"] = len(suspicious)
    if any(contamination.values()):
        errors.append(f"benchmark/earlier-dataset contamination: {contamination}")
    report = {
        "total":len(records),"train":sum(split=="train" for split,_,_ in records),
        "validation":sum(split=="validation" for split,_,_ in records),
        "category_counts":dict(sorted(category_counts.items())),
        "difficulty_counts":dict(sorted(difficulty_counts.items())),
        "response_mode_counts":dict(sorted(mode_counts.items())),
        "family_counts":{"train":len(families["train"]),"validation":len(families["validation"]),
                         "overlap":len(overlap)},
        "exact_duplicate_prompts":exact_duplicates,
        "normalized_duplicate_prompts":normalized_duplicates,
        "contamination":contamination,"suspicious_details":suspicious[:30],
        "validated_references":{"python":code_count,"unified_diff":diff_count,"json":json_count},
        "train_patch_features":dict(sorted(patch_features.items())),
        "sha256":{"train":digest(TRAIN),"validation":digest(VALIDATION)},
        "errors":errors,"validation_error_count":len(errors),
    }
    return report


def main():
    report = inspect()
    (HERE / "experiment_d_stats.json").write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps(report,indent=2,ensure_ascii=False))
    return 0 if not report["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
