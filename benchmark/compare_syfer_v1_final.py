#!/usr/bin/env python3
"""Verify completed final runs and report the preregistered release decision; no models."""
import argparse
import json
from pathlib import Path
import evaluate_syfer_v1_final as evaluation
from syfer_v1_final import validate_final as validator

ROOT=evaluation.ROOT
TARGETS=('Patch generation','Tool-call formatting','Small repository reasoning',
         'Test-driven fixing','Multi-step debugging')
BASIC=('Simple coding','Bug fixing')


def only_completed(model):
    paths=[p.parent for p in (evaluation.OUTPUT/model).glob('*/run_status.json')
           if evaluation.read(p).get('status')=='complete']
    evaluation.require(len(paths)==1,f'need exactly one completed {model} run, found {len(paths)}')
    return paths[0]

def load_run(path,model,tasks):
    path=Path(path);read=evaluation.read;require=evaluation.require
    status=read(path/'run_status.json');config=read(path/'run_config.json');summary=read(path/'summary.json')
    require(status.get('status')=='complete' and status.get('completed_tasks')==48,'incomplete evaluation: '+str(path))
    require(config['model']==model and summary['model']==model,'wrong model label')
    require(config['base_model_id']==evaluation.MODEL_ID and config['base_revision']==evaluation.REVISION,'base mismatch')
    require(config['settings']==evaluation.SETTINGS,'settings mismatch')
    require(config['task_sha256']==evaluation.sha(evaluation.HERE/'tasks.json'),'task hash mismatch')
    require(config['validator_sha256']==evaluation.sha(evaluation.HERE/'validate_final.py'),'validator hash mismatch')
    require(config['runner_sha256']==evaluation.sha(Path(evaluation.__file__)),'runner hash mismatch')
    require(config['frozen_manifest_sha256']==evaluation.sha(evaluation.HERE/'frozen_manifest.json'),'manifest mismatch')
    require(config['adapter_sha256']==evaluation.ADAPTER_HASHES.get(model),'wrong adapter identity')
    require(read(path/'tasks_snapshot.json')==tasks,'prompt/task snapshot changed')
    require(len(summary['tasks'])==48 and len({i['id'] for i in summary['tasks']})==48,'incomplete/duplicate summary tasks')
    saved={i['id']:i for i in summary['tasks']};items=[]
    for task in tasks:
        item=read(path/(task['id']+'.result.json'))
        require(item==saved[task['id']] and item['category']==task['category'],'per-task record differs')
        raw_path=path/(task['id']+'.txt')
        require(item['raw_response_sha256']==evaluation.sha(raw_path),'raw response hash mismatch')
        scores=validator.score(task,raw_path.read_text(encoding='utf-8'))
        for key in ('strict','semantic_diagnostic'):
            require(item[key]['passed']==scores[key]['passed'],'saved score differs from independent replay')
        require(item['formatting_only_failure']==scores['formatting_only_failure'],'formatting classification mismatch')
        items.append(item)
    expected=evaluation.summarize(model,items,summary['load_runtime_seconds'],summary['total_runtime_seconds'])
    require(summary==expected,'summary aggregate mismatch')
    require(read(path/'progress.json')==items,'progress mismatch')
    return {'directory':str(path),'config':config,'summary':summary}

def passes(run,key='strict'):
    return {i['id'] for i in run['summary']['tasks'] if i[key]['passed']}

def delta(left,right):
    # left is the newer/tuned candidate.
    a=passes(left);b=passes(right);all_ids={i['id'] for i in left['summary']['tasks']}
    return {'gains':sorted(a-b),'regressions':sorted(b-a),'shared_passes':sorted(a&b),
            'shared_failures':sorted(all_ids-(a|b))}

def selection(runs):
    stock=passes(runs['stock'])
    ranking={}
    for model in ('experiment_b','experiment_d'):
        run=runs[model];summary=run['summary'];success=passes(run)
        basics={i['id'] for i in summary['tasks'] if i['category'] in BASIC}
        ranking[model]=[summary['strict']['passed'],summary['semantic_diagnostic']['passed'],
          sum(summary['strict']['by_category'][category]['passed'] for category in TARGETS),
          -len((stock-success)&basics),-run['config']['adapter_bytes']]
    if ranking['experiment_b']==ranking['experiment_d']:
        winner=None
        explanation='Exact tie after all preregistered criteria. Both are eligible; an explicit documented non-training choice is required.'
    else:
        winner=max(ranking,key=ranking.get)
        explanation='Selected among B/D by the preregistered lexicographic criteria. Stock remains a reference, not a tuned candidate.'
    return {'selected_tuned_checkpoint':winner,'ranking_vectors':ranking,
       'criteria':['official strict passed','semantic diagnostic passed','strict sum across patch/tool/repo/TDD/debug',
                   'fewer strict regressions versus Stock in coding/bug fixing','smaller adapter weights in bytes'],
       'explanation':explanation,'no_further_training':True}

def compare(runs):
    signature=evaluation.runtime_signature(runs['stock']['config'])
    stock_ids={i['id']:i['prompt_input_ids_sha256'] for i in runs['stock']['summary']['tasks']}
    for model,run in runs.items():
        evaluation.require(evaluation.runtime_signature(run['config'])==signature,'different runtime environment: '+model)
        evaluation.require(run['config']['effective_generation_config']==runs['stock']['config']['effective_generation_config'],
                           'generation config differs: '+model)
        evaluation.require({i['id']:i['prompt_input_ids_sha256'] for i in run['summary']['tasks']}==stock_ids,
                           'tokenized prompts differ: '+model)
    result={'official_metric':'strict','diagnostic_label':'NOT THE OFFICIAL RELEASE SCORE',
       'runs':{model:{'directory':run['directory'],'strict':run['summary']['strict'],
              'semantic_diagnostic':run['summary']['semantic_diagnostic'],
              'total_runtime_seconds':run['summary']['total_runtime_seconds'],
              'formatting_only_failures':[i['id'] for i in run['summary']['tasks'] if i['formatting_only_failure']],
              'semantic_failures':[i['id'] for i in run['summary']['tasks'] if not i['semantic_diagnostic']['passed']],
              'token_limit_tasks':[i['id'] for i in run['summary']['tasks'] if i.get('hit_token_limit')],
              'base_revision':run['config']['base_revision'],'adapter_sha256':run['config']['adapter_sha256']}
               for model,run in runs.items()},
       'comparisons':{'B_vs_Stock':delta(runs['experiment_b'],runs['stock']),
                      'D_vs_Stock':delta(runs['experiment_d'],runs['stock']),
                      'D_vs_B':delta(runs['experiment_d'],runs['experiment_b'])},
       'selection':selection(runs),'policy':'Final SYFER v1 development decision; no further training or benchmark-directed tuning.'}
    return result

def markdown(report):
    lines=['# SYFER v1 final comparison','',
      'Official release metric: **STRICT**. Semantic diagnostic: **NOT THE OFFICIAL RELEASE SCORE**.',
      'The diagnostic only removes one complete enclosing Markdown fence and revalidates. It never repairs an answer.','',
      '| Candidate | Strict | Semantic diagnostic | Total seconds |', '| --- | ---: | ---: | ---: |']
    for name,run in report['runs'].items():
        a,b=run['strict'],run['semantic_diagnostic']
        lines.append(f"| {name} | {a['passed']}/48 ({a['percentage']:.2f}%) | {b['passed']}/48 ({b['percentage']:.2f}%) | {run['total_runtime_seconds']:.2f} |")
    for metric in ('strict','semantic_diagnostic'):
        lines+=['',f'## {metric} category scores','', '| Category | Stock | B | D |','| --- | ---: | ---: | ---: |']
        for category in validator.CATEGORIES:
            values=[str(report['runs'][m][metric]['by_category'][category]['passed'])+'/6' for m in evaluation.MODELS]
            lines.append('| '+category+' | '+' | '.join(values)+' |')
    for name,change in report['comparisons'].items():
        lines+=['','## '+name,'']
        for kind,ids in change.items(): lines.append('- '+kind+': '+(', '.join('`'+x+'`' for x in ids) or 'none'))
    for model,run in report['runs'].items():
        lines+=['','## '+model+' failure separation','',
            '- Formatting-only failures: '+(', '.join(run['formatting_only_failures']) or 'none'),
            '- Still failing diagnostic validation: '+(', '.join(run['semantic_failures']) or 'none'),
            '- Reached token limit: '+(', '.join(run['token_limit_tasks']) or 'none')]
    lines+=['','## Checkpoint selection','',json.dumps(report['selection'],indent=2),
      '', 'A diagnostic failure is a failure under the authored tests, not proof that every aspect of the answer is wrong. '
      'The benchmark has six tasks per category and is a small finite sample; close scores are uncertain. '
      'Adapters use the same NF4-loaded base as Stock. No further training is authorized.']
    return '\n'.join(lines)+'\n'

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stock-run',type=Path);parser.add_argument('--b-run',type=Path);parser.add_argument('--d-run',type=Path)
    args=parser.parse_args()
    evaluation.verify_freeze();tasks=evaluation.read(evaluation.HERE/'tasks.json')
    inputs={'stock':args.stock_run,'experiment_b':args.b_run,'experiment_d':args.d_run}
    runs={model:load_run(path or only_completed(model),model,tasks) for model,path in inputs.items()}
    report=compare(runs)
    # Never overwrite a previous release comparison.
    target=evaluation.OUTPUT
    target.mkdir(parents=True,exist_ok=True)
    json_path=target/'final_comparison.json';md_path=target/'final_comparison.md'
    evaluation.require(not json_path.exists() and not md_path.exists(),'final comparison already exists')
    with json_path.open('x') as stream: json.dump(report,stream,indent=2)
    with md_path.open('x') as stream: stream.write(markdown(report))
    print(md_path)
if __name__=='__main__': main()
