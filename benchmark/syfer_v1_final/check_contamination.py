#!/usr/bin/env python3
"""Deterministic lexical screen plus explicit human family review; no model calls."""
import argparse
import ast
import collections
import difflib
import hashlib
import json
import re
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
SOURCES=['benchmark/tasks.json','benchmark/final_holdout/tasks.json',
         'benchmark/experiment_c_dev/tasks.json','benchmark/experiment_d_dev/tasks.json']+[
    f'dataset/{name}_{split}.jsonl' for name in ('syfer','experiment_b','experiment_c','experiment_d')
    for split in ('train','validation')]

def normalize(text):
    return re.sub(r'\s+',' ',text).strip().casefold()

def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False)

def vector(row):
    checks=row.get('checks',row.get('validation',{}))
    cases=row.get('cases',checks.get('cases',[]))
    if cases: return canonical([case.get('expected') for case in cases])
    expected=row.get('expected',row.get('expected_fields',checks.get('expected',checks.get('expected_fields'))))
    if expected is not None: return canonical(expected)
    return None

def skeleton(text):
    """Large identical ASTs after renaming are a review signal, not proof of copying."""
    try: tree=ast.parse(text)
    except SyntaxError: return None
    if sum(1 for _ in ast.walk(tree))<30: return None
    class Normalize(ast.NodeTransformer):
        def visit_Name(self,node):
            node.id='NAME';return node
        def visit_arg(self,node):
            node.arg='ARG';return node
        def visit_FunctionDef(self,node):
            self.generic_visit(node);node.name='FUNCTION';return node
        def visit_Constant(self,node):
            node.value=type(node.value).__name__;return node
    return ast.dump(Normalize().visit(tree),include_attributes=False)

def entry(row,source,index):
    messages=row.get('messages',[])
    prompt=row.get('prompt','\n'.join(m['content'] for m in messages if m['role']=='user'))
    reference=row.get('reference','\n'.join(m['content'] for m in messages if m['role']=='assistant'))
    text=prompt+'\n'+reference
    return {'source':source,'id':row.get('id',row.get('family',str(index))),
            'family':row.get('family',row.get('id','')),'prompt':prompt,'reference':reference,
            'vector':vector(row),'functions':set(re.findall(r'\bdef\s+(\w+)\s*\(',text)),
            'fixtures':set(re.findall(r'\b[\w/]+\.py\b',text)),
            'category':row.get('category'),
            'ast_skeleton':skeleton(reference),
            'words':set(re.findall(r'[a-z][a-z_]{2,}',prompt.lower()))}

def content(prompt):
    # Drop recurring response-contract boilerplate from lexical similarity.
    return normalize(re.split(r'Return only raw Python|Return one bare JSON|Return exactly one bare JSON',prompt)[0])

def audit():
    tasks=json.loads((HERE/'tasks.json').read_text())
    prior=[];hashes={}
    for source in SOURCES:
        path=ROOT/source
        hashes[source]=hashlib.sha256(path.read_bytes()).hexdigest()
        rows=[json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.suffix=='.jsonl' else json.loads(path.read_text())
        if isinstance(rows,dict): rows=rows['tasks']
        prior.extend(entry(row,source,i) for i,row in enumerate(rows))
    exact=[]; normalized=[]; refs=[]; vectors=[]; families=[]; functions=[]; fixtures=[]; suspicious=[]; nearest=[]; ast_matches=[]
    for i,row in enumerate(tasks):
        current=entry(row,'final',i)
        best=(0,None)
        for old in prior:
            pair={'task':row['id'],'source':old['source'],'prior_id':old['id']}
            if current['prompt']==old['prompt']: exact.append(pair)
            if normalize(current['prompt'])==normalize(old['prompt']): normalized.append(pair)
            if old['reference'] and normalize(current['reference'])==normalize(old['reference']): refs.append(pair)
            if current['vector'] is not None and current['vector']==old['vector']: vectors.append(pair)
            if current['family']==old['family']: families.append(pair)
            if current['ast_skeleton'] and current['ast_skeleton']==old['ast_skeleton']: ast_matches.append(pair)
            common=current['functions']&old['functions']
            # Dunder protocol names are language syntax, not task identifiers.
            common={x for x in common if not x.startswith('__')}
            if common: functions.append(dict(pair,names=sorted(common)))
            shared=current['fixtures']&old['fixtures']
            if shared: fixtures.append(dict(pair,names=sorted(shared)))
            if current['category']==old['category']:
                # Sequence ratio plus shared meaningful word set; not semantic proof.
                a,b=content(current['prompt']),content(old['prompt'])
                overlap=len(current['words']&old['words'])/max(1,len(current['words']|old['words']))
                ratio=difflib.SequenceMatcher(None,a,b,autojunk=False).ratio()
                value=max(ratio,overlap)
                if value>best[0]: best=(value,dict(pair,sequence_ratio=round(ratio,4),word_jaccard=round(overlap,4)))
                if ratio>=0.70 or overlap>=0.70: suspicious.append(dict(pair,sequence_ratio=round(ratio,4),word_jaccard=round(overlap,4)))
        nearest.append(dict(best[1],similarity=round(best[0],4)))
    report={'prior_records':len(prior),'final_tasks':len(tasks),'source_sha256':hashes,
      'exact_prompt_matches':exact,'normalized_prompt_matches':normalized,'normalized_reference_matches':refs,
      'exact_expected_output_vectors':vectors,'family_name_collisions':families,
      'function_name_collisions':functions,'fixture_identifier_collisions':fixtures,
      'suspicious_similarity':suspicious,'nearest_same_category':nearest,
      'renamed_large_ast_matches':ast_matches,
      'limitations':'Lexical screens cannot prove algorithmic independence. Generic language constructs and canonical contracts necessarily recur. See novelty_review.md for manual family review; no model outputs used.'}
    report['blocking_matches']=sum(map(len,(exact,normalized,refs,vectors,families,functions,fixtures,suspicious,ast_matches)))
    return report

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write',action='store_true',help='write report only before freeze')
    args=parser.parse_args();report=audit()
    if args.write:
        if (HERE/'frozen_manifest.json').exists(): parser.error('frozen: report cannot be rewritten')
        (HERE/'contamination_report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ('nearest_same_category','source_sha256')},indent=2))
    return bool(report['blocking_matches'])
if __name__=='__main__': raise SystemExit(main())
