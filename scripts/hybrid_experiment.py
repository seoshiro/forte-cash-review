"""Synthetic-gated hybrid; no real observations or per-video data on stdout."""
from pathlib import Path
import os,sys,json,time,hashlib,datetime,argparse,traceback,zipfile,importlib.metadata as metadata
os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1',DO_NOT_TRACK='1')
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));os.chdir(ROOT)
OUT=ROOT/'.private/hybrid-r22'
ATTEMPT_OWNED=False
FROZEN=['config/hybrid-protocol.json','hybrid_candidate/__init__.py','hybrid_candidate/observer.py','hybrid_candidate/fixtures.py',
    'scripts/hybrid_experiment.py','config/rules.json','config/gguf-artifacts.json','gguf_candidate/runtime.py',
    'panel_candidate/engine.py','cashreview/video.py','cashreview/offline.py','cashreview/research_split.py',
    'cashreview/processes.py','xclip_candidate/evaluate.py','qvt_candidate/evaluate.py','gate_candidate/engine.py',
    'requirements-patched-lock.txt','.private/dataset/manifest.json','.private/dataset/split.json',
    '.private/xclip-control/registration.json','.private/xclip-control/feature-registration.json','.private/xclip-control/safe-summary.json']


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def write(name,data):
    path=OUT/name;temp=path.with_suffix(path.suffix+'.tmp');temp.parent.mkdir(parents=True,exist_ok=True)
    temp.write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding='utf-8');temp.replace(path)


def claim_attempt():
    global ATTEMPT_OWNED
    # Exclusive creation prevents two invocations from launching native jobs.
    with (OUT/'status.json').open('x',encoding='utf-8') as stream:
        ATTEMPT_OWNED=True
        json.dump({'status':'running','phase':'synthetic','train_started':False},stream)


def check_budget(cfg,start,train_start=None,synthetic=False,now=None):
    current=time.monotonic() if now is None else now
    if current-start>cfg['budget']['total_compute_sec']:raise TimeoutError('Total hybrid budget exceeded')
    if synthetic and current-start>cfg['budget']['synthetic_total_sec']:raise TimeoutError('Synthetic budget exceeded')
    if train_start is not None and current-train_start>cfg['budget']['train_total_sec']:raise TimeoutError('TRAIN budget exceeded')


def check_cache_coverage(rows,inventory):
    if set(inventory)!={r['sha256']+'.npz' for r in rows}:raise ValueError('Feature inventory does not exactly cover selected TRAIN')


def native_identity():
    cfg=json.loads((ROOT/'config/gguf-artifacts.json').read_text());identity={};expected_runtime=set()
    runtime=(ROOT/'.private/llama-cuda124-b11712').resolve()
    ready=json.loads((ROOT/'.private/gguf-preflight/safe-summary.json').read_text())
    exe=Path(ready['server_path']).resolve()
    if ready.get('status')!='artifacts_verified_not_benchmarked' or exe!=runtime/'llama-server.exe':raise ValueError('Native path not verified')
    for row in cfg['artifacts']:
        path=ROOT/('models/qwen3vl-4b-gguf' if row['kind']=='model' else '.private/gguf-preflight/downloads')/row['filename']
        if path.stat().st_size!=row['bytes'] or sha(path)!=row['sha256']:raise ValueError('Pinned native artifact mismatch')
        identity[str(path.relative_to(ROOT))]=row['sha256']
        if row['kind']=='runtime':
            with zipfile.ZipFile(path) as archive:
                for member in archive.infolist():
                    if member.is_dir() or Path(member.filename).suffix.lower() not in ('.dll','.exe'):continue
                    target=(runtime/member.filename).resolve()
                    if not target.is_relative_to(runtime):raise ValueError('Unexpected archive member')
                    with archive.open(member) as stream:expected=hashlib.file_digest(stream,'sha256').hexdigest()
                    if target.stat().st_size!=member.file_size or sha(target)!=expected:raise ValueError('Extracted native binary mismatch')
                    identity[str(target.relative_to(ROOT))]=expected;expected_runtime.add(target)
    actual={p.resolve() for p in runtime.rglob('*') if p.is_file() and p.suffix.lower() in ('.dll','.exe')}
    if actual!=expected_runtime:raise ValueError('Native binary inventory mismatch')
    return identity


def verified_event(observation,frames,registry):
    from hybrid_candidate.observer import apply_rule
    if apply_rule(observation)!='R22':return None
    rule=next(r for r in registry['rules'] if r['id']=='R22' and r['enabled'])
    citation=registry['document']+', p.'+rule['paragraph']+'; '+registry['source']
    return {'rule_id':'R22','type':rule['type'],'timestamp_sec':frames[observation['f']].sec,
        'observation':observation['o'],'description':observation['o']+' '+citation,
        'source_citation':citation,'support_pts':[frames[i].sec for i in observation['e']]}


def register():
    OUT.mkdir(exist_ok=True)
    if (OUT/'registration.json').exists():raise RuntimeError('Hybrid already registered; no overwrite')
    from cashreview.research_split import unique_train_contents
    rows=unique_train_contents(json.loads((ROOT/'.private/dataset/manifest.json').read_text(encoding='utf-8')))
    if len(rows)!=26 or len({r['group'] for r in rows})!=24:raise ValueError('Frozen TRAIN scope mismatch')
    inventory=json.loads((ROOT/'.private/xclip-control/feature-registration.json').read_text())['artifact_sha256']
    check_cache_coverage(rows,inventory)
    if any(sha(ROOT/'.private/xclip-control/features'/name)!=digest for name,digest in inventory.items()):raise ValueError('XCLIP cache changed')
    record={'protocol_id':'HYBRID-R22-01','registered_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'code_sha256':{name:sha(ROOT/name) for name in FROZEN},'feature_cache_sha256':inventory,'native_artifact_sha256':native_identity(),
        'source_sha256':[r['sha256'] for r in rows],'train_unique_contents':26,'train_auto_groups':24,
        'versions':{name:metadata.version(name) for name in ['numpy','pydantic','av','httpx','scikit-learn']},
        'manual_annotations_read':False,'train_started':False,'tune_run':False,'holdout_media_inference':False}
    write('registration.json',record);print(json.dumps({'registered':True,'train_unique_contents':26,'train_auto_groups':24,
        'registration_sha256':sha(OUT/'registration.json'),'real_inference_started':False}),flush=True)


def verify(registration):
    from cashreview.research_split import unique_train_contents
    if any(sha(ROOT/name)!=digest for name,digest in registration['code_sha256'].items()):raise ValueError('Frozen hybrid source changed')
    rows=unique_train_contents(json.loads((ROOT/'.private/dataset/manifest.json').read_text(encoding='utf-8')))
    check_cache_coverage(rows,registration['feature_cache_sha256'])
    if any(sha(ROOT/'.private/xclip-control/features'/name)!=digest for name,digest in registration['feature_cache_sha256'].items()):raise ValueError('Frozen feature cache changed')
    if native_identity()!=registration['native_artifact_sha256']:raise ValueError('Registered native artifacts changed')
    if {name:metadata.version(name) for name in registration['versions']}!=registration['versions']:raise ValueError('Runtime versions changed')


def controls(server,cfg,start):
    from hybrid_candidate.fixtures import CASES,text,frames
    from hybrid_candidate.observer import prompt,schema,parse,apply_rule
    from gate_candidate.engine import gate_prompt,parse_gate
    from gguf_candidate.runtime import NativeServer
    registry=json.loads((ROOT/'config/rules.json').read_text(encoding='utf-8'))
    rule=next(r for r in registry['rules'] if r['id']=='R22' and r['enabled'])
    public_rule={k:rule[k] for k in ['id','paragraph','requirement','visual_conditions','exclusions','verified_source_text']}
    gate_schema={'type':'object','additionalProperties':False,'properties':{'visible_violation':{'type':'boolean'}},'required':['visible_violation']}
    records=[];legacy=[];new_text=[];new_visual=[]
    for stage in ['legacy_text','observer_text','observer_visual']:
        for case in CASES:
            for constrained in ([True,False] if stage!='observer_visual' else [True]):
                if time.monotonic()-start>cfg['budget']['synthetic_total_sec']:raise TimeoutError('Synthetic budget exceeded')
                deadline=min(start+cfg['budget']['synthetic_total_sec'],time.monotonic()+cfg['observer']['max_request_sec'])
                if stage=='legacy_text':
                    legacy_prompt=text(case)+'\n'+gate_prompt([public_rule])+('\nFor this text-only diagnostic the explicit fictional visual facts are authoritative. Decide their rule entailment, not whether an actual image is attached.')
                    response,metric=NativeServer.complete(server,[],legacy_prompt,gate_schema if constrained else None,32,deadline)
                    try:passed=parse_gate(response)==(case['match']=='R22');valid=True
                    except ValueError:passed=False;valid=False
                    legacy.append(passed)
                else:
                    if stage=='observer_text':response,metric=NativeServer.complete(server,[],text(case)+'\n'+prompt(),schema() if constrained else None,cfg['observer']['max_tokens'],deadline)
                    else:response,metric=server.complete(frames(case),prompt(),schema(),cfg['observer']['max_tokens'],deadline)
                    try:
                        observation=parse(response);valid=True
                        passed=(tuple(observation[k] for k in ['area','motion','service','context'])==case['expected'] and apply_rule(observation)==case['match'])
                    except ValueError:passed=False;valid=False
                    (new_text if stage=='observer_text' else new_visual).append(passed)
                records.append({'stage':stage,'case':case['name'],'constrained':constrained,'structure_valid':valid,'passed':passed,'generation_sec':metric['generation_sec']})
                write('controls/'+str(len(records))+'.private.json',{'response':response,'metadata':metric})
                write('control-progress-safe-summary.json',{'scope':'Generated/fictional controls only','completed_cases':len(records),
                    'passed_cases':sum(r['passed'] for r in records),'elapsed_sec':time.monotonic()-start,'real_inference_started':False})
                print(json.dumps({'phase':'synthetic_controls','completed_cases':len(records),'total_cases':20,'passed_cases':sum(r['passed'] for r in records)}),flush=True)
    check_budget(cfg,start,synthetic=True)
    report={'scope':'Artificial diagrams and fictional text; not bank video quality','cases':len(records),'legacy_text_cases':len(legacy),
        'legacy_text_passed':sum(legacy),'observer_text_cases':len(new_text),'observer_text_passed':sum(new_text),
        'observer_visual_cases':len(new_visual),'observer_visual_passed':sum(new_visual),'all_new_controls_passed':all(new_text+new_visual),
        'controls':records,'elapsed_sec':time.monotonic()-start,'bank_data_read':False,'raw_responses_emitted':False,
        'token_scores_before_sampler_available':False,'forced_label_outputs_are_not_confidence':True}
    write('synthetic-safe-summary.json',report);check_budget(cfg,start,synthetic=True);return report


def train(server,cfg,registration,start,train_start,control_report):
    import numpy as np
    from cashreview.research_split import unique_train_contents
    from cashreview.video import sample
    from hybrid_candidate.observer import prompt,schema,parse,apply_rule,select_proposals
    from xclip_candidate.evaluate import centroids,score_video
    from qvt_candidate.evaluate import metrics
    registry=json.loads((ROOT/'config/rules.json').read_text(encoding='utf-8'))
    rows=unique_train_contents(json.loads((ROOT/'.private/dataset/manifest.json').read_text(encoding='utf-8')));items=[]
    check_cache_coverage(rows,registration['feature_cache_sha256'])
    for row in rows:
        with np.load(ROOT/'.private/xclip-control/features'/(row['sha256']+'.npz'),allow_pickle=False) as data:
            item={'times':np.array(data['times']),'ordered':np.array(data['ordered'])}
        item.update(row);items.append(item)
    if [i['sha256'] for i in items]!=registration['source_sha256']:raise ValueError('TRAIN selection changed')
    positive_by_group={g:centroids([i for i in items if i['group']!=g],'ordered') for g in sorted({i['group'] for i in items})}
    records=[];baseline=[];costs=[];proposals_total=0;accepted_events=0;coverage=[];description_nonempty=0
    for index,item in enumerate(items):
        check_budget(cfg,start,train_start)
        tick=time.monotonic();positive,negative=positive_by_group[item['group']]
        choices=select_proposals(item['ordered'],item['times'],positive,negative,cfg['proposal']['top_k'],cfg['proposal']['minimum_center_separation_sec'])
        base_score,base_time=score_video(item['ordered'],item['times'],positive,negative,'max')
        baseline.append({'truth':item['target'],'prediction':int(base_score>=0),'error_sec':abs(base_time-item['label_sec']) if item['target'] else None})
        if sha(item['path'])!=item['sha256']:raise ValueError('Source changed before hybrid')
        events=[];private_observations=[];proposals_total+=len(choices)
        if item['target']:coverage.append(min(abs(float(item['times'][i])-item['label_sec']) for i in choices))
        for choice in choices:
            center=float(item['times'][choice]);radius=cfg['proposal']['context_radius_sec']
            low=max(0.,center-radius);high=min(item['duration_sec']-.05,center+radius)
            frames=sample(Path(item['path']),np.linspace(low,high,cfg['proposal']['context_frames']).tolist(),max_side=cfg['proposal']['source_frame_max_side'])
            if len(frames)!=4:raise ValueError('Expected exactly four decoded context frames')
            deadline=min(start+cfg['budget']['total_compute_sec'],train_start+cfg['budget']['train_total_sec'],tick+cfg['budget']['max_video_engine_sec'],time.monotonic()+cfg['observer']['max_request_sec'])
            response,telemetry=server.complete(frames,prompt(),schema(),cfg['observer']['max_tokens'],deadline)
            observation=parse(response);rule=apply_rule(observation);private_observations.append({'facts':observation,'rule_application':rule,'telemetry':telemetry})
            if rule=='R22':
                events.append(verified_event(observation,frames,registry))
                description_nonempty+=bool(observation['o'].strip())
        if sha(item['path'])!=item['sha256']:raise ValueError('Source changed after hybrid')
        elapsed=time.monotonic()-tick
        if elapsed>cfg['budget']['max_video_engine_sec']:raise TimeoutError('Video engine budget exceeded')
        costs.append(elapsed);accepted_events+=len(events);guess=int(bool(events));sec=events[0]['timestamp_sec'] if events else None
        row={'truth':item['target'],'prediction':guess,'error_sec':abs(sec-item['label_sec']) if item['target'] and sec is not None else None,'source_sha256':item['sha256']};records.append(row)
        write('results/'+item['sha256']+'.private.json',{'observations':private_observations,'events':events})
        write('status.json',{'status':'running','phase':'train','completed_train_videos':index+1,'elapsed_sec':time.monotonic()-start,'tune_run':False,'holdout_media_inference':False})
        print(json.dumps({'phase':'train','completed_train_videos':index+1,'total_train_videos':26}),flush=True)
    verify(registration);source_unchanged=all(sha(i['path'])==i['sha256'] for i in items)
    check_budget(cfg,start,train_start)
    hybrid=metrics(records);prior=metrics(baseline);saved=json.loads((ROOT/'.private/xclip-control/safe-summary.json').read_text())['results']['ordered_max']
    baseline_matches=prior['confusion_matrix_tn_fp_fn_tp']==saved['confusion_matrix_tn_fp_fn_tp']
    useful=hybrid['confusion_matrix_tn_fp_fn_tp'][1][1]>=prior['confusion_matrix_tn_fp_fn_tp'][1][1] and hybrid['confusion_matrix_tn_fp_fn_tp'][0][1]<prior['confusion_matrix_tn_fp_fn_tp'][0][1] and hybrid['f1']>=.8
    summary={'split':'train','scope':cfg['scope'],'train_unique_contents':26,'train_auto_groups':24,'results':{'baseline':prior,'hybrid':hybrid},
        'baseline_matches_saved_frozen_xclip':baseline_matches,'proposal_windows_total':proposals_total,'accepted_events_total':accepted_events,
        'generated_observation_nonempty_events':description_nonempty,'proposal_point_coverage_le3sec':sum(e<=3 for e in coverage),'positive_videos':len(coverage),
        'qwen_stage_latency_mean_sec':float(np.mean(costs)),'qwen_stage_latency_max_sec':max(costs),'train_wall_sec':time.monotonic()-train_start,
        'latency_scope':cfg['comparison']['latency_scope'],
        'total_compute_sec':time.monotonic()-start,'synthetic_gate_passed':control_report['all_new_controls_passed'],
        'all_sources_unchanged':source_unchanged,'useful_hybrid_gate_passed':bool(useful and source_unchanged and baseline_matches),
        'type_or_description_accuracy_ground_truth_available':False,'rule_scope_limited_to_R22':True,'release_eligible':False,
        'manual_annotations_read':False,'tune_run':False,'holdout_media_inference':False,'holdout_model_evaluation':False,'technical_failures':0}
    write('private-oof-metrics.json',records);check_budget(cfg,start,train_start);return summary


def run():
    if (OUT/'status.json').exists():raise RuntimeError('Hybrid already started; no repeat')
    from panel_candidate.engine import PanelServer
    from cashreview.offline import deny_network
    from gguf_candidate.runtime import DeviceMeter
    import psutil
    for process in psutil.process_iter(['name','exe']):
        try:
            if (process.info['name'] or '').lower()=='llama-server.exe' and Path(process.info['exe']).is_relative_to(ROOT/'.private/llama-cuda124-b11712'):
                raise RuntimeError('Owned native model already running; do not duplicate')
        except (psutil.Error,TypeError):pass
    registration=json.loads((OUT/'registration.json').read_text());verify(registration);cfg=json.loads((ROOT/'config/hybrid-protocol.json').read_text())
    start=time.monotonic();claim_attempt()
    server=PanelServer(OUT/'runtime');meter=DeviceMeter();meter.start();train_start=None;summary=None
    try:
        server.start();deny_network([server.port]);load=server.load_sec
        report=controls(server,cfg,start);verify(registration)
        check_budget(cfg,start,synthetic=True)
        if not report['all_new_controls_passed']:
            status={'status':'completed','synthetic_gate_passed':False,'train_started':False,'tune_run':False,'holdout_media_inference':False,
                'model_load_sec':load}
        else:
            write('status.json',{'status':'running','phase':'train','train_started':True});train_start=time.monotonic()
            summary=train(server,cfg,registration,start,train_start,report)
    finally:
        device=meter.stop();server.close()
    check_budget(cfg,start,train_start,synthetic=train_start is None)
    if summary is None:
        status.update(total_compute_sec=time.monotonic()-start,**device);write('status.json',status)
        check_budget(cfg,start,synthetic=True);print(json.dumps(status),flush=True)
    else:
        summary.update(model_load_sec=load,total_compute_sec=time.monotonic()-start,train_wall_sec=time.monotonic()-train_start,**device)
        write('train-safe-summary.json',summary);check_budget(cfg,start,train_start)
        write('status.json',{'status':'completed','train_started':True,'useful_hybrid_gate_passed':summary['useful_hybrid_gate_passed'],'tune_run':False,'holdout_media_inference':False})
        check_budget(cfg,start,train_start)
        print(json.dumps(summary),flush=True)


def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['register','run']);a=p.parse_args();register() if a.action=='register' else run()


if __name__=='__main__':
    try:main()
    except Exception as error:
        record={'status':'failed','technical_error_type':type(error).__name__,'locations':[{'file':Path(f.filename).name,'line':f.lineno} for f in traceback.extract_tb(error.__traceback__)],
            'raw_content_emitted':False,'tune_run':False,'holdout_media_inference':False}
        record['attempt_owned_by_this_invocation']=ATTEMPT_OWNED
        OUT.mkdir(exist_ok=True);write('failure-safe-summary.json' if ATTEMPT_OWNED else 'rejected-invocation-safe-summary.json',record)
        if ATTEMPT_OWNED:write('status.json',record)
        if ATTEMPT_OWNED and (OUT/'train-safe-summary.json').exists():
            summary=json.loads((OUT/'train-safe-summary.json').read_text());summary.update(status='failed',useful_hybrid_gate_passed=False,technical_failures=1)
            write('train-safe-summary.json',summary)
        print(json.dumps(record),flush=True);sys.exit(1)
