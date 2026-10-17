"""One registered TRAIN experiment; stdout contains aggregate metrics only."""
from pathlib import Path
import os,sys,json,time,hashlib,argparse,datetime,traceback
os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1',
    DO_NOT_TRACK='1',TRANSFORMERS_VERBOSITY='error',TOKENIZERS_PARALLELISM='false')
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));os.chdir(ROOT)
from cashreview.offline import deny_network
deny_network()
OUT=ROOT/'.private/qvt-control'
FROZEN=['config/qvt-protocol.json','qvt_candidate/features.py','qvt_candidate/evaluate.py',
    'qvt_candidate/__init__.py','scripts/qvt_experiment.py','cashreview/video.py','cashreview/offline.py',
    'requirements-patched-lock.txt','.private/dataset/manifest.json','.private/dataset/split.json']


def digest(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def write(name,data):
    tmp=OUT/(name+'.tmp');tmp.write_text(json.dumps(data,indent=2),encoding='utf-8');tmp.replace(OUT/name)


def rows():
    data=json.loads((ROOT/'.private/dataset/manifest.json').read_text(encoding='utf-8'))
    selected=[r for r in data if r['split']=='train' and not r['error']]
    if len(selected)!=27 or len(set(r['group'] for r in selected))!=24:raise ValueError('Unexpected frozen TRAIN scope')
    return selected


def register():
    OUT.mkdir(exist_ok=True)
    if (OUT/'registration.json').exists():raise RuntimeError('Registration already exists; no overwrite')
    selected=rows()
    record={'protocol_id':'QVT-01','registered_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'frozen_sha256':{name:digest(ROOT/name) for name in FROZEN},'source_sha256':sorted(r['sha256'] for r in selected),
        'train_videos':len(selected),'train_groups':len(set(r['group'] for r in selected)),
        'manual_annotations_read':False,'holdout_opened':False,'new_weights_downloaded':False}
    write('registration.json',record)
    print(json.dumps({'registered':True,'train_videos':record['train_videos'],'train_groups':record['train_groups'],
        'registration_sha256':digest(OUT/'registration.json'),'holdout_opened':False}),flush=True)


def verify(registration):
    if any(digest(ROOT/name)!=sha for name,sha in registration['frozen_sha256'].items()):raise ValueError('Frozen source changed')
    if sorted(r['sha256'] for r in rows())!=registration['source_sha256']:raise ValueError('Frozen TRAIN selection changed')


def run():
    if (OUT/'status.json').exists():raise RuntimeError('Experiment already started; bounded run cannot repeat')
    registration=json.loads((OUT/'registration.json').read_text());verify(registration)
    cfg=json.loads((ROOT/'config/qvt-protocol.json').read_text());start=time.monotonic()
    write('status.json',{'status':'running','phase':'load','completed_train_videos':0,'holdout_opened':False})
    import torch,numpy as np,psutil
    from PIL import Image,ImageDraw
    from qvt_candidate.features import VisionEncoder,extract
    from qvt_candidate.evaluate import grouped_oof,accepted
    torch.set_num_threads(4);torch.cuda.reset_peak_memory_stats()
    encoder=VisionEncoder(ROOT,cfg);load_sec=time.monotonic()-start
    synthetic=[Image.new('RGB',(256,256),c) for c in ['black','gray','white']]
    draw=ImageDraw.Draw(synthetic[-1]);draw.rectangle((32,32,128,192),fill='red')
    before=time.monotonic();a=encoder.encode(synthetic);b=encoder.encode(synthetic[:1])
    synthetic_pass=bool(np.isfinite(a).all() and a.shape==(3,128) and np.max(abs(a[0]-b[0]))<0.02
        and np.linalg.norm(a[0]-a[1])>1e-5 and np.linalg.norm(a[0]-a[2])>1e-5)
    write('synthetic-safe-summary.json',{'scope':'Generated color/shape images only; encoder mechanics, not bank quality',
        'synthetic_cases':3,'finite_and_distinct':synthetic_pass,'elapsed_sec':time.monotonic()-before,'manual_annotations_read':False})
    if not synthetic_pass:raise ValueError('Synthetic encoder contract failed')
    selected=sorted(rows(),key=lambda r:r['duration_sec']);probes=[selected[0],selected[len(selected)//2],selected[-1]]
    order=probes+[r for r in sorted(selected,key=lambda r:r['sha256']) if r['sha256'] not in {p['sha256'] for p in probes}]
    feature_dir=OUT/'features';feature_dir.mkdir(exist_ok=True);items=[];elapsed=[];counts=[]
    for i,row in enumerate(order):
        if time.monotonic()-start>cfg['budget']['total_wall_sec']:raise TimeoutError('Experiment budget exhausted')
        if digest(row['path'])!=row['sha256']:raise ValueError('Source changed before extraction')
        times,features,cost=extract(encoder,Path(row['path']),cfg)
        if digest(row['path'])!=row['sha256']:raise ValueError('Source changed during extraction')
        elapsed.append(cost);counts.append(len(times))
        np.savez_compressed(feature_dir/(row['sha256']+'.npz'),times=times,features=features,elapsed_sec=cost)
        items.append({'sha256':row['sha256'],'group':row['group'],'target':row['target'],'label_sec':row['label_sec'],
            'times':times,'features':features})
        rss=psutil.Process().memory_info().rss/2**20;reserved=torch.cuda.max_memory_reserved()/2**20
        if i==2:
            write('technical-safe-summary.json',{'split':'train','probe_videos':3,'load_sec':load_sec,
                'visual_parameters':encoder.parameter_count,'language_parameters_loaded':0,'synthetic_pass':synthetic_pass,
                'feature_latency_mean_sec':float(np.mean(elapsed)),'feature_latency_max_sec':max(elapsed),
                'frames_total':sum(counts),'torch_reserved_peak_mib':reserved,'process_rss_mib':rss,
                'new_weights_downloaded':False,'manual_annotations_read':False,'holdout_opened':False})
        if cost>cfg['budget']['max_feature_latency_sec'] or reserved>cfg['budget']['max_torch_reserved_mib'] or rss>cfg['budget']['max_process_rss_mib']:
            raise RuntimeError('Technical budget gate failed')
        write('status.json',{'status':'running','phase':'features','completed_train_videos':i+1,
            'total_train_videos':len(order),'elapsed_sec':time.monotonic()-start,'holdout_opened':False})
        print(json.dumps({'phase':'features','completed_train_videos':i+1,'total_train_videos':len(order)}),flush=True)
    reports,private=grouped_oof(items,cfg)
    write('private-oof-results.json',private)
    if time.monotonic()-start>cfg['budget']['total_wall_sec']:raise TimeoutError('Experiment budget exhausted')
    verify(registration)
    source_unchanged=all(digest(r['path'])==r['sha256'] for r in selected)
    passed=accepted(reports,cfg) and source_unchanged
    summary={'split':'train','scope':cfg['scope'],'train_videos':len(items),'train_groups':24,'grouped_oof':True,
        'results':reports,'train_gate_passed':passed,'tune_run':False,'tune_ready_only_if_train_passed':passed,
        'holdout_opened':False,'manual_annotations_read':False,'cloud_inference_used':False,'new_weights_downloaded':False,
        'all_sources_unchanged':source_unchanged,'load_sec':load_sec,'experiment_wall_sec':time.monotonic()-start,
        'feature_latency_mean_sec':float(np.mean(elapsed)),'feature_latency_max_sec':max(elapsed),
        'torch_reserved_peak_mib':torch.cuda.max_memory_reserved()/2**20,'process_rss_mib':psutil.Process().memory_info().rss/2**20,
        'sampled_frames_total':sum(counts),'technical_failures':0,'registration_sha256':digest(OUT/'registration.json'),
        'limitations':cfg['limitations'],'official_score':False,'release_eligible':False}
    write('safe-summary.json',summary)
    write('status.json',{'status':'completed','completed_train_videos':len(items),'train_gate_passed':passed,
        'tune_run':False,'holdout_opened':False,'elapsed_sec':time.monotonic()-start})
    print(json.dumps(summary),flush=True)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['register','run']);args=parser.parse_args()
    register() if args.action=='register' else run()


if __name__=='__main__':
    try:main()
    except Exception as error:
        failure={'status':'failed','technical_error_type':type(error).__name__,
            'stack_locations':[{'file':Path(f.filename).name,'line':f.lineno,'function':f.name} for f in traceback.extract_tb(error.__traceback__)],
            'model_outputs_emitted':False,'manual_annotations_read':False,'holdout_opened':False,'tune_run':False}
        OUT.mkdir(exist_ok=True);write('failure-safe-summary.json',failure)
        if (OUT/'status.json').exists():write('status.json',failure)
        print(json.dumps(failure),flush=True);sys.exit(1)
