#!/usr/bin/env python3
"""One final, frozen, model-symmetric evaluation. --check never loads a model."""
import argparse
import datetime as dt
import hashlib
import importlib.metadata
import json
import os
import time
import traceback
import uuid
from pathlib import Path
from syfer_v1_final import validate_final as validator

ROOT=Path(__file__).resolve().parents[1]
HERE=ROOT/'benchmark/syfer_v1_final'
OUTPUT=ROOT/'results/syfer_v1_final'
MODELS=('stock','experiment_b','experiment_d')
MODEL_ID='Qwen/Qwen2.5-Coder-3B-Instruct'
REVISION='89fe5444e8baf5736e70f528f1edcc79e6616ef6'
SETTINGS={'temperature':0,'do_sample':False,'max_new_tokens':512,'seed':42,'num_beams':1,
          'repetition_penalty':1.0,'use_cache':True}
B_RUN='training/output/experiment_b/experiment-20260926T111408Z-4838f847'
D_RUN='training/output/experiment_d/experiment-20260926T190151Z-2a492ce7'
# Provenance: adapter hashes recorded in the copied historical D-dev run_config.json files.
# They lock the two existing release candidates, not a preferred winner.
ADAPTER_HASHES={
 'experiment_b':{'adapter_model.safetensors':'41406a1fff7f4377b5fb554e46ab72133add35a53458b351b1f1401d4fd552e1',
                 'adapter_config.json':'a90d0eea29be640d778cabdb407473cdd1b4b1766ccf0269dea830328bfeecf7'},
 'experiment_d':{'adapter_model.safetensors':'638078fbff02f49db338f84d68c4b2dad6df01fda87a26ed2c2e9b259fa7553a',
                 'adapter_config.json':'72e18adf5776dad6f69eedaf8046be577e443126dd6a8ebbc6b358f5201dd4c9'}}


def require(condition,message):
    if not condition: raise ValueError(message)

def read(path): return json.loads(Path(path).read_text(encoding='utf-8'))
def sha(path): return validator.sha256(path)
def digest_json(value): return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def save(path,value):
    # Atomic progress/status updates; the enclosing run itself is always new.
    path=Path(path);temporary=path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    temporary.replace(path)

def verify_freeze():
    manifest=read(HERE/'frozen_manifest.json')
    require(manifest['task_count']==48,'wrong frozen task count')
    for name,expected in manifest['sha256'].items():
        require(sha(ROOT/name)==expected,'frozen file changed: '+name)
    return manifest

def select_adapter(name,d_run=None):
    require(name in MODELS,'unknown candidate')
    if name!='experiment_d': require(d_run is None,'--experiment-d-run is only for D')
    if name=='stock': return None
    if name=='experiment_d':
        require(d_run is not None,'--experiment-d-run is required')
        run=(ROOT/d_run).resolve()
        require(run==(ROOT/D_RUN).resolve(),'D must be the preregistered completed candidate run')
    else: run=ROOT/B_RUN
    status=read(run/'run_status.json');manifest=read(run/'manifest.json');config=read(run/'config.json')
    expected_experiment='B' if name=='experiment_b' else 'D'
    require(status.get('status')=='complete','training run is not complete')
    require(manifest.get('mode')=='train' and manifest.get('experiment')==expected_experiment,
            'wrong training experiment or smoke adapter')
    require(manifest.get('model_id')==MODEL_ID and manifest.get('model_revision')==REVISION,
            'training manifest base differs')
    require(config.get('model_id')==MODEL_ID and config.get('model_revision')==REVISION,
            'training config base differs')
    adapter=run/'adapter'
    for filename,expected in ADAPTER_HASHES[name].items():
        require(sha(adapter/filename)==expected,'release candidate hash mismatch: '+filename)
    ac=read(adapter/'adapter_config.json')
    require(ac.get('peft_type')=='LORA' and ac.get('r')==16 and ac.get('lora_alpha')==32
            and ac.get('lora_dropout')==0.05,'unexpected adapter settings')
    require(ac.get('base_model_name_or_path') in (None,MODEL_ID),'adapter base mismatch')
    return adapter

def check(name,d_run=None):
    frozen=verify_freeze()
    tasks=read(HERE/'tasks.json')
    require(len(tasks)==48 and len({t['id'] for t in tasks})==48,'invalid task inventory')
    require({c:sum(t['category']==c for t in tasks) for c in validator.CATEGORIES}==dict.fromkeys(validator.CATEGORIES,6),'category mismatch')
    adapter=select_adapter(name,d_run)
    require(OUTPUT.resolve()==ROOT/'results/syfer_v1_final','output root mismatch')
    return tasks,adapter,frozen

def runtime_signature(config):
    """Comparison requires identical actual generation environment, not just CLI flags."""
    keys=('base_model_id','base_revision','settings','task_sha256','validator_sha256','runner_sha256',
          'packages','tokenizer_class','chat_template_sha256','tokenizer_vocab_sha256',
          'tokenizer_special_tokens','eos_token_id','pad_token_id','dtype','quantization',
          'gpu_name','compute_capability','prompt_protocol','response_extraction')
    return {key:config[key] for key in keys}

def enforce_environment(config):
    # Freeze first actual environment; all subsequent candidates must match it.
    target=OUTPUT/'evaluation_environment.json'
    signature=runtime_signature(config)
    try:
        with target.open('x',encoding='utf-8') as stream:
            json.dump(signature,stream,indent=2)
    except FileExistsError:
        require(read(target)==signature,'evaluation environment differs from first candidate; stop, do not query')

def summarize(name,items,load_seconds,total_seconds):
    def metric(key):
        passed=sum(item[key]['passed'] for item in items)
        return {'passed':passed,'total':48,'percentage':round(passed/48*100,4),
                'by_category':{category:{'passed':sum(item[key]['passed'] for item in items if item['category']==category),'total':6}
                               for category in validator.CATEGORIES}}
    return {'model':name,'task_count':48,'strict':metric('strict'),
            'semantic_diagnostic':metric('semantic_diagnostic'),
            'semantic_diagnostic_label':'NOT THE OFFICIAL RELEASE SCORE',
            'load_runtime_seconds':load_seconds,'task_runtime_seconds':sum(i['runtime_seconds'] for i in items),
            'total_runtime_seconds':total_seconds,'tasks':items}

def reserve(name):
    root=OUTPUT/name;root.mkdir(parents=True,exist_ok=True)
    # An exclusive reservation prevents accidental reruns and selective retries.
    # A pre-generation infrastructure failure can only be retried through explicit,
    # documented operator review. Never delete this marker after seeing responses.
    run_id=dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8]
    with (root/'evaluation_once.json').open('x') as stream:
        json.dump({'run_id':run_id,'policy':'one evaluation; no tuning or selective retries'},stream)
    run=root/run_id;run.mkdir(exist_ok=False)
    return run

def generate(model,tokenizer,prompt,torch,set_seed):
    # The same function is called for Stock, B and D. One user turn, no system message.
    set_seed(SETTINGS['seed'])
    inputs=tokenizer.apply_chat_template([{'role':'user','content':prompt}],tokenize=True,
        add_generation_prompt=True,return_dict=True,return_tensors='pt').to('cuda:0')
    length=inputs['input_ids'].shape[-1]
    with torch.inference_mode():
        result=model.generate(**inputs,do_sample=False,num_beams=1,max_new_tokens=512,
            repetition_penalty=1.0,use_cache=True,return_dict_in_generate=False,
            eos_token_id=tokenizer.eos_token_id,pad_token_id=tokenizer.eos_token_id)
    tokens=result[0][length:]
    raw=tokenizer.decode(tokens,skip_special_tokens=True)
    return raw,{'prompt_tokens':length,'generated_tokens':len(tokens),
                'last_token_id':int(tokens[-1]) if len(tokens) else None,
                'hit_token_limit':len(tokens)==512,
                'prompt_input_ids_sha256':digest_json(inputs['input_ids'][0].tolist())}

def run(name,tasks,adapter,frozen):
    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM,AutoTokenizer,BitsAndBytesConfig,GenerationConfig,set_seed
    require(torch.cuda.is_available(),'CUDA required; run on Kaggle, never local CPU evaluation')
    torch.cuda.set_device(0)
    dtype=torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
    run_dir=reserve(name);items=[];started=time.monotonic();load_seconds=0
    config={'model':name,'base_model_id':MODEL_ID,'base_revision':REVISION,'settings':SETTINGS,
      'task_sha256':sha(HERE/'tasks.json'),'validator_sha256':sha(HERE/'validate_final.py'),
      'runner_sha256':sha(Path(__file__)),'frozen_manifest_sha256':sha(HERE/'frozen_manifest.json'),
      'adapter':str(adapter.relative_to(ROOT)) if adapter else None,
      'adapter_sha256':ADAPTER_HASHES[name] if adapter else None,
      'adapter_bytes':(adapter/'adapter_model.safetensors').stat().st_size if adapter else 0,
      'packages':{package:importlib.metadata.version(package) for package in
                  ('torch','transformers','peft','accelerate','bitsandbytes','tokenizers','huggingface-hub')},
      'dtype':str(dtype),'gpu_name':torch.cuda.get_device_name(0),
      'compute_capability':list(torch.cuda.get_device_capability(0)),
      'quantization':{'load_in_4bit':True,'type':'nf4','double_quant':True},
      'prompt_protocol':'one user message; pinned tokenizer.apply_chat_template; add_generation_prompt=True',
      'response_extraction':'decode generated suffix only; skip_special_tokens=True; no stripping/repair',
      'started_utc':dt.datetime.now(dt.timezone.utc).isoformat()}
    save(run_dir/'tasks_snapshot.json',tasks);save(run_dir/'run_config.json',config)
    save(run_dir/'progress.json',items)
    save(run_dir/'run_status.json',{'status':'loading','completed_tasks':0})
    try:
        cache=ROOT/'training/cache'
        set_seed(42)
        tokenizer=AutoTokenizer.from_pretrained(MODEL_ID,revision=REVISION,cache_dir=cache,trust_remote_code=False)
        require(bool(tokenizer.chat_template),'pinned tokenizer has no chat template')
        config.update(tokenizer_class=type(tokenizer).__name__,
            chat_template_sha256=digest_json(tokenizer.chat_template),
            tokenizer_vocab_sha256=digest_json(tokenizer.get_vocab()),
            tokenizer_special_tokens={key:str(value) for key,value in tokenizer.special_tokens_map.items()},
            eos_token_id=tokenizer.eos_token_id,pad_token_id=tokenizer.eos_token_id)
        enforce_environment(config)
        save(run_dir/'run_config.json',config)
        quant=BitsAndBytesConfig(load_in_4bit=True,bnb_4bit_quant_type='nf4',
            bnb_4bit_use_double_quant=True,bnb_4bit_compute_dtype=dtype)
        base=AutoModelForCausalLM.from_pretrained(MODEL_ID,revision=REVISION,cache_dir=cache,
            trust_remote_code=False,quantization_config=quant,dtype=dtype,device_map={'':0})
        model=PeftModel.from_pretrained(base,adapter,is_trainable=False) if adapter else base
        # Discard model-supplied sampling defaults; identical greedy configuration.
        model.generation_config=GenerationConfig(do_sample=False,num_beams=1,max_new_tokens=512,
            repetition_penalty=1.0,use_cache=True,eos_token_id=tokenizer.eos_token_id,
            pad_token_id=tokenizer.eos_token_id,bos_token_id=tokenizer.bos_token_id)
        model.eval();torch.cuda.synchronize();load_seconds=time.monotonic()-started
        config['load_runtime_seconds']=load_seconds
        config['effective_generation_config']=model.generation_config.to_dict()
        save(run_dir/'run_config.json',config)
        for task in tasks:
            tick=time.monotonic()
            raw,token_info=generate(model,tokenizer,task['prompt'],torch,set_seed)
            torch.cuda.synchronize();generation_seconds=time.monotonic()-tick
            (run_dir/(task['id']+'.txt')).write_text(raw,encoding='utf-8')
            scores=validator.score(task,raw)
            item={'id':task['id'],'category':task['category'],**scores,**token_info,
                  'generation_runtime_seconds':generation_seconds,
                  'runtime_seconds':time.monotonic()-tick,'raw_response_sha256':sha(run_dir/(task['id']+'.txt'))}
            save(run_dir/(task['id']+'.result.json'),item);items.append(item)
            save(run_dir/'progress.json',items)
            save(run_dir/'run_status.json',{'status':'in_progress','completed_tasks':len(items)})
        summary=summarize(name,items,load_seconds,time.monotonic()-started)
        save(run_dir/'summary.json',summary)
        save(run_dir/'run_status.json',{'status':'complete','completed_tasks':48})
    except BaseException as error:
        save(run_dir/'run_status.json',{'status':'failed_or_interrupted','completed_tasks':len(items),
             'error_type':type(error).__name__,'error':str(error),'traceback':traceback.format_exc(),
             'total_runtime_seconds':time.monotonic()-started})
        raise
    print(json.dumps({'run_directory':str(run_dir),'strict':summary['strict'],
                      'semantic_diagnostic':summary['semantic_diagnostic']},indent=2))
    return 0

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model',required=True,choices=MODELS)
    parser.add_argument('--experiment-d-run',type=Path)
    parser.add_argument('--check',action='store_true')
    args=parser.parse_args()
    try: tasks,adapter,frozen=check(args.model,args.experiment_d_run)
    except (OSError,ValueError,KeyError) as error: parser.exit(2,f'Preflight failed: {error}\n')
    if args.check:
        print(f'PASS: {args.model}, 48 frozen tasks; candidate={adapter}; NO MODEL LOADED OR QUERIED')
        return 0
    return run(args.model,tasks,adapter,frozen)
if __name__=='__main__': raise SystemExit(main())
