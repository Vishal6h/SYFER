#!/usr/bin/env python3
"""Copy already-existing, extracted Kaggle candidate runs; never download models."""
import argparse
import shutil
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import evaluate_syfer_v1_final as evaluation


def restore(input_root):
    evaluation.verify_freeze()
    for model,relative in (('experiment_b',evaluation.B_RUN),('experiment_d',evaluation.D_RUN)):
        target=evaluation.ROOT/relative
        if target.exists():
            evaluation.select_adapter(model,Path(relative) if model=='experiment_d' else None)
            print('Verified existing '+str(target));continue
        sources=[p for p in Path(input_root).rglob(target.name) if p.is_dir() and (p/'adapter').is_dir()]
        evaluation.require(len(sources)==1,
            f'Attach exactly one EXTRACTED complete {target.name} under {input_root}; found {len(sources)}. No archive paths or artifacts are invented.')
        source=sources[0]
        evaluation.require(evaluation.read(source/'run_status.json').get('status')=='complete','source training run incomplete')
        manifest=evaluation.read(source/'manifest.json');config=evaluation.read(source/'config.json')
        for document in (manifest,config):
            evaluation.require(document.get('model_id')==evaluation.MODEL_ID and document.get('model_revision')==evaluation.REVISION,'source base differs')
        evaluation.require(manifest.get('mode')=='train' and manifest.get('experiment')==model[-1].upper(),'wrong experiment')
        for name,expected in evaluation.ADAPTER_HASHES[model].items():
            evaluation.require(evaluation.sha(source/'adapter'/name)==expected,'source adapter hash differs')
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copytree(source,target)  # dirs_exist_ok defaults False: no overwrites.
        evaluation.select_adapter(model,Path(relative) if model=='experiment_d' else None)
        print('Restored and verified '+str(target))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input-root',type=Path,default=Path('/kaggle/input'))
    restore(parser.parse_args().input_root)
