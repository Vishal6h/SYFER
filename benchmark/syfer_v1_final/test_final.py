"""Model-free tests. Synthetic evaluation records live only in temporary directories."""
import ast
import contextlib
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent))
from syfer_v1_final import validate_final as v
from syfer_v1_final import check_contamination as contamination
import evaluate_syfer_v1_final as runner
import compare_syfer_v1_final as comparison

TASKS=json.loads((HERE/'tasks.json').read_text())
BY_ID={t['id']:t for t in TASKS}

class ValidatorTests(unittest.TestCase):
    def test_all_references_and_oracles(self):
        report=v.validate_references()
        self.assertEqual(report['references_passed'],48)
        self.assertEqual(report['errors'],[])
    def test_all_wrapped_references_diagnostic_only(self):
        for task in TASKS:
            with self.subTest(task=task['id']):
                raw='```\n'+task['reference'].rstrip('\n')+'\n```'
                scores=v.score(task,raw)
                self.assertFalse(scores['strict']['passed'])
                self.assertTrue(scores['semantic_diagnostic']['passed'],scores)
                self.assertTrue(scores['formatting_only_failure'])
    def test_json_semantics_and_exact_types(self):
        task=BY_ID['v1_nonlocal_counter_state']
        obj=task['expected']
        raw=json.dumps(dict(reversed(list(obj.items()))),indent=3)
        self.assertTrue(v.strict(task,raw)['passed'])
        self.assertFalse(v.strict(task,json.dumps(dict(obj,extra=1)))['passed'])
        self.assertFalse(v.equal(True,1));self.assertFalse(v.equal(1.0,1))
    def test_json_duplicate_keys_and_non_json_numbers(self):
        for raw in ('{"x":1,"x":1}','NaN','Infinity','-Infinity'):
            with self.assertRaises(ValueError):v.parse_json(raw)
    def test_diagnostic_does_not_repair(self):
        task=BY_ID['v1_nonlocal_counter_state'];ref=task['reference']
        for raw in ('Here it is:\n```json\n'+ref+'\n```','```json\n'+ref,
                    '```json\n'+ref+'\n```\nmore prose','```json\n{broken}\n```',
                    '```\n```json\n'+ref+'\n```\n```', '```json\n{"output":0}\n```'):
            with self.subTest(raw=raw):self.assertFalse(v.score(task,raw)['semantic_diagnostic']['passed'])
    def test_alternative_complete_fence_delimiters(self):
        task=BY_ID['v1_nonlocal_counter_state']
        for delimiter,label in (('~~~','json'),('````','JSON'),('```','python3')):
            scores=v.score(task,delimiter+label+'\n'+task['reference']+'\n'+delimiter)
            self.assertFalse(scores['strict']['passed'])
            self.assertTrue(scores['semantic_diagnostic']['passed'])
    def test_tool_wrong_args_types_keys(self):
        task=BY_ID['v1_symbol_scope_query']
        for mutation in ('tool','type','extra'):
            obj=copy.deepcopy(task['expected'])
            if mutation=='tool':obj['tool']='text_query'
            if mutation=='type':obj['arguments']['limit']='7'
            if mutation=='extra':obj['arguments']['scope']['more']=True
            self.assertFalse(v.strict(task,json.dumps(obj))['passed'])
    def test_safe_iter_and_divmod(self):
        cases=[{'function':'sample','args':[[2,5]],'expected':[2,1,1]}]
        raw='def sample(values):\n    it=iter(values)\n    first=next(it)\n    q,r=divmod(next(it),4)\n    return [first,q,r]\n'
        self.assertTrue(v.validate_python(raw,cases)[0])
    def test_forbidden_code_and_mutation(self):
        for raw in ('import os\ndef x(): return 1','def x(): return open("x")',
                    'def x(): return (1).__class__','print(1)','def x():\n    global q\n    return 1'):
            with self.assertRaises(ValueError):v.check_code(raw)
        raw='def f(values):\n    values.append(3)\n    return 2\n'
        self.assertFalse(v.validate_python(raw,[{'function':'f','args':[[1]],'expected':2,'unchanged_args':True}])[0])
    def test_code_execution_timeout(self):
        result=v.strict({'response_mode':'python_code','cases':[{'function':'f','args':[],'expected':0}]},
                        'def f():\n    while True: pass\n')
        self.assertFalse(result['passed'])
    def test_patch_counts_and_files(self):
        task=BY_ID['v1_zigzag_integer_encoding'];raw=task['reference']
        self.assertFalse(v.strict(task,raw.replace('@@ -1,','@@ -99,',1))['passed'])
        self.assertFalse(v.strict(task,raw.replace('--- a/','--- wrong/',1))['passed'])
        self.assertFalse(v.strict(task,raw.replace('+    return 2*n if n>=0 else -2*n-1','+    return 2*abs(n)'))['passed'])
        self.assertFalse(v.strict(task,'--- a/'+task['path']+'\n+++ b/'+task['path']+'\n')['passed'])
    def test_patch_transport_and_content_whitespace(self):
        task=BY_ID['v1_common_margin_removal']
        self.assertTrue(v.strict(task,task['reference'].replace('\n','\r\n'))['passed'])
        self.assertTrue(v.strict(task,task['reference']+'\n')['passed'])
        self.assertFalse(v.strict(task,task['reference'].replace('-    return [line.strip()', '-    return [line.strip() '))['passed'])
    def test_patch_insert_delete_and_multiple_hunks(self):
        for family in ('switch_type_guard','rook_conflict_scan','byte_field_roundtrip'):
            task=BY_ID['v1_'+family]
            self.assertTrue(v.strict(task,task['reference'])['passed'])
        self.assertGreaterEqual(BY_ID['v1_byte_field_roundtrip']['reference'].count('@@ -'),2)
        self.assertEqual(v.apply_unified_diff('a\nb\n','--- a/x\n+++ b/x\n@@ -1,0 +2 @@\n+c\n','x'),'a\nc\nb\n')
        self.assertEqual(v.apply_unified_diff('a\nb\n','--- a/x\n+++ b/x\n@@ -2 +1,0 @@\n-b\n','x'),'a\n')
    def test_patch_no_final_newline_marker(self):
        self.assertEqual(v.apply_unified_diff('a','--- a/x\n+++ b/x\n@@ -1 +1 @@\n-a\n\\ No newline at end of file\n+b\n\\ No newline at end of file\n','x'),'b')
    def test_preserved_helper_enforced(self):
        task=copy.deepcopy(BY_ID['v1_zigzag_integer_encoding'])
        import difflib
        patched=v.apply_unified_diff(task['source'],task['reference'],task['path']).replace('return value','return value+0')
        raw=''.join(difflib.unified_diff(task['source'].splitlines(True),patched.splitlines(True),fromfile='a/'+task['path'],tofile='b/'+task['path']))
        self.assertFalse(v.strict(task,raw)['passed'])
    def test_original_broken_fixtures_rejected(self):
        for task in TASKS:
            if task['response_mode']=='unified_diff':
                self.assertFalse(v.validate_python(task['source'],task['cases'])[0],task['id'])
            elif '\nCurrent code:\n' in task['prompt']:
                broken=task['prompt'].split('\nCurrent code:\n',1)[1]
                self.assertFalse(v.strict(task,broken)['passed'],task['id'])
    def test_contamination_and_family_inventory(self):
        report=contamination.audit()
        self.assertEqual(report['blocking_matches'],0,report)
        self.assertEqual(report['final_tasks'],48)
    def test_syntax_and_freeze(self):
        for path in list(HERE.glob('*.py'))+[Path(runner.__file__),Path(comparison.__file__)]:
            ast.parse(path.read_text(),filename=str(path))
        if (HERE/'frozen_manifest.json').exists():runner.verify_freeze()

class RunnerTests(unittest.TestCase):
    def test_completed_candidate_and_hash_lock(self):
        with tempfile.TemporaryDirectory(prefix='syfer-candidate-mock-') as tmp,patch.object(runner,'ROOT',Path(tmp)):
            run=Path(tmp)/runner.D_RUN
            (run/'adapter').mkdir(parents=True)
            runner.save(run/'run_status.json',{'status':'complete'})
            manifest={'experiment':'D','mode':'train','model_id':runner.MODEL_ID,'model_revision':runner.REVISION}
            runner.save(run/'manifest.json',manifest);runner.save(run/'config.json',manifest)
            runner.save(run/'adapter/adapter_config.json',{'peft_type':'LORA','r':16,'lora_alpha':32,
              'lora_dropout':0.05,'base_model_name_or_path':runner.MODEL_ID})
            (run/'adapter/adapter_model.safetensors').write_bytes(b'SYNTHETIC TEST ONLY, NOT A MODEL')
            hashes={name:runner.sha(run/'adapter'/name) for name in ('adapter_model.safetensors','adapter_config.json')}
            with patch.dict(runner.ADAPTER_HASHES,{'experiment_d':hashes}):
                self.assertEqual(runner.select_adapter('experiment_d',Path(runner.D_RUN)),run/'adapter')
                (run/'adapter/adapter_model.safetensors').write_bytes(b'changed')
                with self.assertRaises(ValueError):runner.select_adapter('experiment_d',Path(runner.D_RUN))
    def test_d_flag_required_and_other_models_reject_it(self):
        with self.assertRaises(ValueError):runner.select_adapter('experiment_d')
        with self.assertRaises(ValueError):runner.select_adapter('stock',Path(runner.D_RUN))
        with self.assertRaises(ValueError):runner.select_adapter('experiment_b',Path(runner.D_RUN))
        self.assertIsNone(runner.select_adapter('stock'))
    def test_only_known_candidates(self):
        with self.assertRaises(ValueError):runner.select_adapter('experiment_c')
        with self.assertRaises(ValueError):runner.select_adapter('experiment_d',Path('training/output/experiment_d/other'))
    def test_stock_check_without_ml_packages(self):
        if not (HERE/'frozen_manifest.json').exists():self.skipTest('pre-freeze')
        with patch.dict(sys.modules,{'torch':None,'transformers':None,'peft':None}):
            tasks,adapter,_=runner.check('stock')
        self.assertEqual(len(tasks),48);self.assertIsNone(adapter)
    def test_reservation_prevents_rerun(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(runner,'OUTPUT',Path(tmp)):
            first=runner.reserve('stock');self.assertTrue(first.is_dir())
            with self.assertRaises(FileExistsError):runner.reserve('stock')
    def test_generation_same_path_no_response_repair(self):
        class Tokens(list):
            def tolist(self):return list(self)
        class Matrix(list):
            shape=(1,3)
        class Inputs(dict):
            def to(self,device):self.device=device;return self
        class Tokenizer:
            eos_token_id=99
            def apply_chat_template(self,messages,**kwargs):
                self.messages=messages;self.kwargs=kwargs
                return Inputs(input_ids=Matrix([Tokens([4,5,6])]))
            def decode(self,tokens,**kwargs):
                self.decoded=list(tokens);return '```python\ndef f(): return 1\n```'
        class Model:
            def generate(self,**kwargs):self.kwargs=kwargs;return [Tokens([4,5,6,8,99])]
        class Torch:
            inference_mode=staticmethod(contextlib.nullcontext)
        tokenizer=Tokenizer();model=Model();seeds=[]
        raw,info=runner.generate(model,tokenizer,'unchanged prompt',Torch,seeds.append)
        self.assertTrue(raw.startswith('```'));self.assertEqual(seeds,[42])
        self.assertEqual(tokenizer.messages,[{'role':'user','content':'unchanged prompt'}])
        self.assertEqual(tokenizer.decoded,[8,99]);self.assertEqual(info['generated_tokens'],2)
        self.assertEqual(model.kwargs['max_new_tokens'],512);self.assertFalse(model.kwargs['do_sample'])
        self.assertEqual(model.kwargs['eos_token_id'],99)

class ComparisonTests(unittest.TestCase):
    def synthetic(self,model):
        items=[]
        for index,task in enumerate(TASKS):
            # Only mock references, never model-generated answers or real output directories.
            passed=index<({'stock':10,'experiment_b':12,'experiment_d':15}[model])
            raw=task['reference'] if passed else 'incorrect synthetic response'
            scores=v.score(task,raw)
            items.append({'id':task['id'],'category':task['category'],**scores,'runtime_seconds':0.1,
                          'prompt_input_ids_sha256':runner.digest_json(task['prompt']),'hit_token_limit':False})
        summary=runner.summarize(model,items,1,6)
        config={key:'same mock value' for key in (
          'base_model_id','base_revision','settings','task_sha256','validator_sha256','runner_sha256',
          'packages','tokenizer_class','chat_template_sha256','tokenizer_vocab_sha256','tokenizer_special_tokens',
          'eos_token_id','pad_token_id','dtype','quantization','gpu_name','compute_capability','prompt_protocol','response_extraction')}
        config.update(adapter_bytes=100,adapter_sha256=runner.ADAPTER_HASHES.get(model),effective_generation_config={'mock':True})
        return {'directory':'synthetic-only','summary':summary,'config':config}
    def test_comparison_and_selection(self):
        runs={model:self.synthetic(model) for model in runner.MODELS}
        report=comparison.compare(runs)
        self.assertEqual(report['selection']['selected_tuned_checkpoint'],'experiment_d')
        self.assertEqual(len(report['comparisons']['D_vs_B']['gains']),3)
        self.assertIn('NOT THE OFFICIAL RELEASE SCORE',comparison.markdown(report))
        runs['experiment_d']['config']['dtype']='different'
        with self.assertRaises(ValueError):comparison.compare(runs)
    def test_tie_selection_uses_diagnostic_then_targets(self):
        runs={model:self.synthetic(model) for model in runner.MODELS}
        runs['experiment_b']['summary']=copy.deepcopy(runs['experiment_d']['summary'])
        self.assertIsNone(comparison.selection(runs)['selected_tuned_checkpoint'])
        runs['experiment_b']['summary']['semantic_diagnostic']['passed']+=1
        self.assertEqual(comparison.selection(runs)['selected_tuned_checkpoint'],'experiment_b')
    def test_completed_fixture_replay_and_tamper_rejection(self):
        if not (HERE/'frozen_manifest.json').exists():self.skipTest('pre-freeze')
        run=self.synthetic('stock');config=run['config'];summary=run['summary']
        config.update(model='stock',base_model_id=runner.MODEL_ID,base_revision=runner.REVISION,settings=runner.SETTINGS,
          task_sha256=runner.sha(HERE/'tasks.json'),validator_sha256=runner.sha(HERE/'validate_final.py'),
          runner_sha256=runner.sha(Path(runner.__file__)),frozen_manifest_sha256=runner.sha(HERE/'frozen_manifest.json'))
        with tempfile.TemporaryDirectory(prefix='syfer-mock-final-') as tmp:
            root=Path(tmp)
            for index,(task,item) in enumerate(zip(TASKS,summary['tasks'])):
                raw=task['reference'] if index<10 else 'incorrect synthetic response'
                raw_path=root/(task['id']+'.txt');raw_path.write_text(raw)
                item['raw_response_sha256']=runner.sha(raw_path)
                runner.save(root/(task['id']+'.result.json'),item)
            runner.save(root/'summary.json',summary);runner.save(root/'run_config.json',config)
            runner.save(root/'tasks_snapshot.json',TASKS);runner.save(root/'progress.json',summary['tasks'])
            runner.save(root/'run_status.json',{'status':'complete','completed_tasks':48})
            verified=comparison.load_run(root,'stock',TASKS)
            self.assertEqual(verified['summary']['strict']['passed'],10)
            (root/(TASKS[0]['id']+'.txt')).write_text('tampered')
            with self.assertRaises(ValueError):comparison.load_run(root,'stock',TASKS)
    def test_incomplete_run_is_not_scored(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            runner.save(root/'run_status.json',{'status':'failed_or_interrupted','completed_tasks':47})
            runner.save(root/'run_config.json',{});runner.save(root/'summary.json',{})
            with self.assertRaises(ValueError):comparison.load_run(root,'stock',TASKS)

if __name__=='__main__':unittest.main()
