"""One registered local spatial experiment; only fixed safe aggregates emitted."""
from pathlib import Path
import sys,os,json,time,datetime,argparse
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from cashreview.supervision import await_start_gate,supervise,atomic_json,ControlSummary,write_progress
from xclip_candidate.experimental import sha,encoder_artifacts
OUT=ROOT/'.private/xclip-spatial-control'
FILES=['config/xclip-spatial-protocol.json','scripts/xclip_spatial.py','xclip_candidate/spatial.py',
    'xclip_candidate/experimental.py','cashreview/supervision.py']


def inputs():
    from scripts.xclip_experiment import rows,verify
    registration=json.loads((ROOT/'.private/xclip-control/registration.json').read_text());verify(registration)
    if any(registration['frozen_sha256'].get(name)!=digest for name,digest in encoder_artifacts().items()):raise ValueError('Encoder artifact differs from original registration')
    return rows()


def verify_registered(registration):
    if {name:sha(ROOT/name) for name in FILES}!=registration['code_sha256']:raise ValueError('Spatial source changed')
    if sha(ROOT/'.private/xclip-control/registration.json')!=registration['original_registration_sha256']:raise ValueError('Original registration changed')
    selected=inputs()
    if [r['sha256'] for r in selected]!=registration['source_sha256']:raise ValueError('Spatial TRAIN scope changed')
    return selected


def register():
    OUT.mkdir(exist_ok=True)
    if (OUT/'registration.json').exists():raise RuntimeError('No registration overwrite')
    selected=inputs();record={'protocol_id':'XCLIP-SPATIAL-01','registered_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'code_sha256':{name:sha(ROOT/name) for name in FILES},'source_sha256':[r['sha256'] for r in selected],
        'original_registration_sha256':sha(ROOT/'.private/xclip-control/registration.json'),
        'train_unique_contents':len(selected),'train_auto_groups':len({r['group'] for r in selected})}
    with (OUT/'registration.json').open('x') as stream:json.dump(record,stream,indent=2)
    print(json.dumps({'registered':True,'registration_sha256':sha(OUT/'registration.json'),'inference_started':False}))


def worker():
    run,deadline=await_start_gate();start=time.monotonic();completed=0
    os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1',DO_NOT_TRACK='1',TOKENIZERS_PARALLELISM='false')
    from cashreview.offline import deny_network
    deny_network()
    try:
        import numpy as np,torch,psutil
        from xclip_candidate.features import Encoder,probe_order
        from xclip_candidate.spatial import extract,evaluate,accepted
        cfg=json.loads((ROOT/'config/xclip-spatial-protocol.json').read_text());original_cfg=json.loads((ROOT/'config/xclip-protocol.json').read_text())
        registration=json.loads((OUT/'registration.json').read_text());selected=verify_registered(registration)
        if len(selected)!=cfg['selection']['unique_train'] or len({r['group'] for r in selected})!=cfg['selection']['automatic_train_groups']:raise ValueError('Registered selection count mismatch')
        torch.set_num_threads(4);torch.cuda.reset_peak_memory_stats();video_start=None
        def check():
            if time.monotonic()>=deadline:raise TimeoutError('Spatial total budget')
            if video_start is not None and time.monotonic()-video_start>cfg['budget']['per_video_sec']:raise TimeoutError('Spatial per-video budget')
            if psutil.Process().memory_info().peak_wset/2**20>cfg['budget']['max_process_rss_mib']:raise RuntimeError('Spatial memory budget')
            if torch.cuda.max_memory_reserved()/2**20>cfg['budget']['max_torch_reserved_mib']:raise RuntimeError('Spatial GPU budget')
        check();encoder=Encoder(ROOT,original_cfg,check);load_sec=time.monotonic()-start
        cache=run/'features';cache.mkdir();inventory={};costs=[];windows=0;frames=0
        for row in probe_order(selected):
            video_start=time.monotonic();check()
            if sha(row['path'])!=row['sha256']:raise ValueError('Source changed before extraction')
            value=extract(encoder,Path(row['path']),original_cfg,cfg);check()
            if sha(row['path'])!=row['sha256']:raise ValueError('Source changed after extraction')
            path=cache/(row['sha256']+'.npz');np.savez_compressed(path,full_field=value['full_field'],central_crop=value['central_crop'],times=value['times'])
            inventory[path.name]=sha(path);costs.append(time.monotonic()-video_start);windows+=value['windows'];frames+=value['frames']
            completed+=1;write_progress(run,'fixture',completed,completed,26);check();video_start=None;check()
        atomic_json(run/'feature-registration.json',{'artifact_sha256':inventory});items=[]
        for row in selected:
            path=cache/(row['sha256']+'.npz')
            if sha(path)!=inventory[path.name]:raise ValueError('Cache changed before CV')
            with np.load(path,allow_pickle=False) as data:item={key:np.array(data[key]) for key in ['full_field','central_crop','times']}
            item.update({k:row[k] for k in ['group','target','label_sec','sha256']});items.append(item)
        check();aggregate,private=evaluate(items);check();verify_registered(registration)
        if any(sha(cache/name)!=digest for name,digest in inventory.items()):raise ValueError('Cache changed during CV')
        if any(sha(row['path'])!=row['sha256'] for row in selected):raise ValueError('Source changed before final completion')
        check();atomic_json(run/'private-oof-results.json',private)
        summary={'status':'completed','split':'train','protocol_id':cfg['protocol_id'],'results':aggregate,
            'useful_gate_passed':accepted(aggregate,cfg),'train_unique_contents':len(selected),'train_auto_groups':len({r['group'] for r in selected}),
            'load_sec':load_sec,'feature_latency_mean_sec':float(np.mean(costs)),'feature_latency_max_sec':max(costs),
            'elapsed_sec':time.monotonic()-start,'torch_reserved_peak_mib':torch.cuda.max_memory_reserved()/2**20,
            'process_peak_working_set_mib':psutil.Process().memory_info().peak_wset/2**20,'windows_per_view_total':windows,
            'sampled_frames_total':frames,'technical_failures':0,'source_and_actual_cv_cache_unchanged':True,
            'tune_used':False,'holdout_used':False,'type_or_rule_validated':False,'release_eligible':False,
            'baseline_or_deployment_pack_changed':False,'limits':cfg['limits']}
        atomic_json(run/'quality-safe-summary.json',summary,deadline=deadline)
        atomic_json(run/'worker-safe-summary.json',ControlSummary(status='completed',completed_cases=26,passed_cases=26,total_cases=26).model_dump(),deadline=deadline)
    except Exception as error:
        path=run/'quality-safe-summary.json'
        if path.exists():path.unlink()
        atomic_json(path,{'status':'failed','technical_error_type':type(error).__name__,'completed_train_count':completed,
            'raw_private_content_emitted':False,'useful_gate_passed':False,'tune_used':False,'holdout_used':False})
        atomic_json(run/'worker-safe-summary.json',ControlSummary(status='failed',completed_cases=completed,passed_cases=completed,total_cases=26,failure='exception').model_dump())
        raise SystemExit(1)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['register','run','worker']);args=parser.parse_args()
    try:
        if args.action=='register':register()
        elif args.action=='worker':worker()
        else:
            cfg=json.loads((ROOT/'config/xclip-spatial-protocol.json').read_text())
            report=supervise([sys.executable,str(Path(__file__).resolve()),'worker'],OUT/'run',cfg['budget']['wall_sec'],26,str(ROOT))
            # This monitor gate reports technical completion only. Detector gate
            # is separately reported in quality-safe-summary.useful_gate_passed.
            print(json.dumps({'technical_monitor':report}),flush=True)
            if report['quality_gate_passed']:
                summary=json.loads((OUT/'run/quality-safe-summary.json').read_text())
                summary['technical_monitor_validated']=True;atomic_json(OUT/'safe-summary.json',summary)
                print(json.dumps(summary),flush=True)
            else:
                atomic_json(OUT/'safe-summary.json',{'status':'failed','technical_monitor_validated':False,
                    'useful_gate_passed':False,'raw_private_content_emitted':False})
                raise SystemExit(1)
    except Exception as error:print(json.dumps({'status':'not_started_or_failed','technical_error_type':type(error).__name__,'raw_private_content_emitted':False}));sys.exit(1)
