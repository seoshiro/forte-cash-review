"""Register/run one cache-only TRAIN diagnostic. Only aggregate metrics stdout."""
from pathlib import Path
import sys,json,time,argparse,datetime
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from xclip_candidate.experimental import sha
from cashreview.supervision import atomic_json
OUT=ROOT/'.private/xclip-hardneg-control'
FILES=['config/xclip-hardneg-protocol.json','xclip_candidate/hard_negative.py','scripts/xclip_hardneg.py',
    'xclip_candidate/evaluate.py','qvt_candidate/evaluate.py','cashreview/research_split.py',
    '.private/xclip-control/registration.json','.private/xclip-control/feature-registration.json','.private/xclip-control/safe-summary.json']


def sources():
    from scripts.xclip_experiment import rows,verify
    record=json.loads((ROOT/'.private/xclip-control/registration.json').read_text());verify(record)
    selected=rows();inventory=json.loads((ROOT/'.private/xclip-control/feature-registration.json').read_text())['artifact_sha256']
    if set(inventory)!={r['sha256']+'.npz' for r in selected}:raise ValueError('Exact original TRAIN cache coverage required')
    if any(sha(ROOT/'.private/xclip-control/features'/name)!=digest for name,digest in inventory.items()):raise ValueError('Original cache changed')
    return selected,inventory


def verify_registered(registration):
    if any(sha(ROOT/n)!=digest for n,digest in registration['code_sha256'].items()):raise ValueError('Registered diagnostic code changed')
    selected,inventory=sources()
    if inventory!=registration['cache_sha256'] or [r['sha256'] for r in selected]!=registration['source_sha256']:raise ValueError('Registered diagnostic inputs changed')
    return selected


def main(action):
    OUT.mkdir(exist_ok=True)
    if action=='register':
        if (OUT/'registration.json').exists():raise RuntimeError('No registration overwrite')
        selected,inventory=sources()
        with (OUT/'registration.json').open('x') as stream:json.dump({'protocol_id':'XCLIP-HARDNEG-01',
            'registered_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'code_sha256':{n:sha(ROOT/n) for n in FILES},
            'cache_sha256':inventory,'source_sha256':[r['sha256'] for r in selected]},stream,indent=2)
        print(json.dumps({'registered':True,'registration_sha256':sha(OUT/'registration.json'),'new_inference_started':False}));return
    with (OUT/'attempt.json').open('x') as stream:json.dump({'started':True},stream)
    start=time.monotonic();cfg=json.loads((ROOT/'config/xclip-hardneg-protocol.json').read_text());registration=json.loads((OUT/'registration.json').read_text())
    def check():
        if time.monotonic()-start>cfg['budget']['wall_sec']:raise TimeoutError('Cache diagnostic budget exceeded')
    try:
        import numpy as np
        from xclip_candidate.hard_negative import evaluate
        selected=verify_registered(registration);check()
        items=[]
        for row in selected:
            with np.load(ROOT/'.private/xclip-control/features'/(row['sha256']+'.npz'),allow_pickle=False) as data:item={'ordered':np.array(data['ordered']),'times':np.array(data['times'])}
            item.update({k:row[k] for k in ['group','target','label_sec','sha256']});items.append(item)
        check();aggregate,private=evaluate(items,cfg);check();verify_registered(registration);check()
        baseline=aggregate['baseline']['confusion_matrix_tn_fp_fn_tp'];flat=[baseline[0][0],baseline[0][1],baseline[1][0],baseline[1][1]]
        if flat!=cfg['baseline_expected_tn_fp_fn_tp']:raise ValueError('Saved baseline not reproduced')
        test=aggregate['hard_negative'];gate=cfg['useful_binary_gate'];cm=test['confusion_matrix_tn_fp_fn_tp']
        useful=cm[1][1]>=gate['tp_min'] and cm[0][1]<=gate['fp_max'] and test['f1']>=gate['f1_min']
        atomic_json(OUT/'private-oof-results.json',private)
        summary={'status':'completed','split':'train','protocol_id':cfg['protocol_id'],'results':aggregate,'train_unique_contents':len(items),
            'train_auto_groups':len({i['group'] for i in items}),'useful_binary_gate_passed':bool(useful),'baseline_reproduced':True,
            'elapsed_sec':time.monotonic()-start,'new_gpu_inference':False,'real_video_opened':False,'tune_run':False,'holdout_media_inference':False,
            'type_or_rule_validated':False,'release_eligible':False,'original_baseline_and_deployment_pack_changed':False,'limits':cfg['limits']}
        check();atomic_json(OUT/'safe-summary.json',summary,deadline=start+cfg['budget']['wall_sec'])
        print(json.dumps(summary),flush=True)
    except Exception as error:
        summary={'status':'failed','technical_error_type':type(error).__name__,'raw_private_content_emitted':False,
            'useful_binary_gate_passed':False,'release_eligible':False,'tune_run':False,'holdout_media_inference':False}
        if (OUT/'safe-summary.json').exists():(OUT/'safe-summary.json').unlink()
        atomic_json(OUT/'safe-summary.json',summary);print(json.dumps(summary),flush=True);raise SystemExit(1)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['register','run']);args=parser.parse_args()
    try:main(args.action)
    except Exception as error:print(json.dumps({'rejected_or_not_started':True,'technical_error_type':type(error).__name__,'raw_private_content_emitted':False}));sys.exit(1)
