#!/usr/bin/env python3
"""One-time authorship freeze. Refuses an existing manifest; never queries a model."""
import datetime as dt
import json
from pathlib import Path
import validate_final as validator
import check_contamination

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]

def freeze():
    target=HERE/'frozen_manifest.json'
    if target.exists():raise SystemExit('Already frozen; modifying this benchmark is forbidden.')
    references=validator.validate_references()
    if references['errors'] or references['references_passed']!=48:raise SystemExit(references)
    contamination=check_contamination.audit()
    if contamination['blocking_matches']:raise SystemExit('Contamination review failed')
    recorded=json.loads((HERE/'contamination_report.json').read_text())
    if recorded!=contamination:raise SystemExit('Contamination report is stale; regenerate before freeze')
    tasks=json.loads((HERE/'tasks.json').read_text())
    validation={'references':references,'oracle_count':sum(t['response_mode'] in ('explanation_json','repository_reasoning_json') for t in tasks),
                'executable_case_count':sum(len(t.get('cases',[])) for t in tasks),
                'model_queries':0,'scope':'Reference validation and trusted fixture execution only'}
    (HERE/'validation_report.json').write_text(json.dumps(validation,indent=2)+'\n')
    files=sorted(path for path in HERE.iterdir() if path.is_file() and path.name!='frozen_manifest.json')
    files += [ROOT/'benchmark/evaluate_syfer_v1_final.py',ROOT/'benchmark/compare_syfer_v1_final.py',ROOT/'docs/TRAINING_OUTPUT_CONTRACT.md']
    files += [ROOT/name for name in check_contamination.SOURCES]
    manifest={'benchmark':'SYFER v1 final','created_utc':dt.datetime.now(dt.timezone.utc).isoformat(),
      'task_count':48,'category_distribution':references['category_counts'],'contract_version':'D1 / final-v1 explicit task contracts',
      'sha256':{str(path.relative_to(ROOT)):validator.sha256(path) for path in files},
      'fixtures':'All task source/repository fixtures are inline in tasks.json; no separate fixture files.',
      'contamination_status':{'blocking_matches':0,'prior_records_checked':contamination['prior_records'],
        'manual_family_review':'benchmark/syfer_v1_final/novelty_review.md','limitations':contamination['limitations']},
      'creation_notes':['No candidate model queried during authorship, validation, tests or freeze.',
        'References are independently authored deterministic oracles, not generated model responses.',
        'This is the final model-development benchmark for SYFER v1; no training after exposure.',
        'Official strict score and fence-only diagnostic are distinct; no retroactive changes.',
        'No winner selected; policy preregistered in README and comparison script.'],
      'model_evaluations_at_freeze':0,'no_model_has_been_evaluated_yet':True}
    with target.open('x') as stream:json.dump(manifest,stream,indent=2);stream.write('\n')
    print(json.dumps({'frozen':str(target),'task_sha256':manifest['sha256']['benchmark/syfer_v1_final/tasks.json'],
                      'validator_sha256':manifest['sha256']['benchmark/syfer_v1_final/validate_final.py'],
                      'runner_sha256':manifest['sha256']['benchmark/evaluate_syfer_v1_final.py']},indent=2))
if __name__=='__main__':freeze()
