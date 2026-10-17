"""One frozen local TRAIN experiment. Stdout contains only safe aggregates."""
from pathlib import Path
import os,sys,json,time,hashlib,argparse,datetime,traceback,importlib.metadata as metadata
os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1',HF_HUB_DISABLE_PROGRESS_BARS='1',
    DO_NOT_TRACK='1',TRANSFORMERS_VERBOSITY='error',TOKENIZERS_PARALLELISM='false')
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));os.chdir(ROOT)
from cashreview.offline import deny_network
from cashreview.research_split import unique_train_contents
OUT=ROOT/'.private/xclip-control'
FROZEN=['config/xclip-protocol.json','config/xclip-artifacts.json','xclip_candidate/__init__.py',
    'xclip_candidate/features.py','xclip_candidate/evaluate.py','scripts/xclip_experiment.py',
    'cashreview/research_split.py','cashreview/video.py','cashreview/offline.py','qvt_candidate/evaluate.py',
    'requirements-patched-lock.txt','gguf_candidate/runtime.py','.private/dataset/manifest.json','.private/dataset/split.json',
    'models/xclip-base-patch32/provenance.json','models/xclip-base-patch32/model.safetensors',
    'models/xclip-base-patch32/config.json','models/xclip-base-patch32/preprocessor_config.json','models/xclip-base-patch32/README.md']
FROZEN+=['.private/xclip-synthetic-preflight/safe-summary.json']


def digest(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def peak_working_set_mib(info):
    # Windows keeps this high-water mark after temporary tensors/images free.
    value=getattr(info,'peak_wset',None)
    if type(value) is not int or value<=0:raise RuntimeError('Windows peak working set unavailable')
    return value/2**20


def write(name,data):
    temp=OUT/(name+'.tmp');temp.write_text(json.dumps(data,indent=2),encoding='utf-8');temp.replace(OUT/name)


def rows():
    manifest=json.loads((ROOT/'.private/dataset/manifest.json').read_text(encoding='utf-8'))
    selected=unique_train_contents(manifest)
    if len(selected)!=26 or len({r['group'] for r in selected})!=24:raise ValueError('Frozen TRAIN scope mismatch')
    if sum(r['target'] for r in selected)!=14:raise ValueError('TRAIN target count mismatch')
    return selected


def register():
    OUT.mkdir(exist_ok=True)
    if (OUT/'registration.json').exists():raise RuntimeError('Registration exists; no overwrite')
    ready=json.loads((ROOT/'.private/xclip-prepare/safe-summary.json').read_text())
    if ready['status']!='weights_verified' or not ready['sha256_verified']:raise ValueError('Weights not verified')
    selected=rows()
    record={'protocol_id':'XCLIP-PROTO-01','registered_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'frozen_sha256':{name:digest(ROOT/name) for name in FROZEN},'source_sha256':[r['sha256'] for r in selected],
        'versions':{name:metadata.version(name) for name in ['torch','transformers','av','safetensors','scikit-learn','numpy','huggingface-hub']},
        'train_original_rows':sum(r['manifest_multiplicity'] for r in selected),'train_unique_contents':len(selected),
        'train_auto_groups':len({r['group'] for r in selected}),'cache_policy':'Each new cache file is hashed before CV, reloaded as actual CV input and verified after CV',
        'pooling_fixed_before_feature_extraction':['max','adjacent_pair_minimum_persistence'],
        'manual_annotations_read':False,'holdout_media_inference':False,'holdout_model_evaluation':False}
    write('registration.json',record)
    print(json.dumps({'registered':True,'protocol_id':record['protocol_id'],'train_unique_contents':len(selected),
        'train_auto_groups':record['train_auto_groups'],'registration_sha256':digest(OUT/'registration.json')}),flush=True)


def verify(registration):
    if any(digest(ROOT/name)!=sha for name,sha in registration['frozen_sha256'].items()):raise ValueError('Frozen source changed')
    if [r['sha256'] for r in rows()]!=registration['source_sha256']:raise ValueError('Frozen TRAIN selection changed')
    if {name:metadata.version(name) for name in registration['versions']}!=registration['versions']:raise ValueError('Runtime version changed')


def run():
    if (OUT/'status.json').exists():raise RuntimeError('Run already started; no repeat')
    registration=json.loads((OUT/'registration.json').read_text());verify(registration)
    cfg=json.loads((ROOT/'config/xclip-protocol.json').read_text());start=time.monotonic()
    preflight=json.loads((ROOT/'.private/xclip-synthetic-preflight/safe-summary.json').read_text())
    if preflight['status']!='passed':raise ValueError('Synthetic compatibility preflight failed')
    prior_compute_sec=float(preflight['total_sec'])
    def check():
        if prior_compute_sec+time.monotonic()-start>cfg['budget']['compute_wall_sec_after_weights_ready']:raise TimeoutError('Compute budget exceeded')
        if peak_working_set_mib(psutil.Process().memory_info())>cfg['budget']['max_process_rss_mib']:raise RuntimeError('Peak working-set budget exceeded')
        if torch.cuda.max_memory_reserved()/2**20>cfg['budget']['max_torch_reserved_mib']:raise RuntimeError('Torch reserved budget exceeded')
    write('status.json',{'status':'running','phase':'load','completed_train_videos':0,'elapsed_sec':0})
    import torch,numpy as np,psutil
    from PIL import Image,ImageDraw
    from xclip_candidate.features import Encoder,extract,probe_order
    from xclip_candidate.evaluate import grouped_oof,accepted
    from gguf_candidate.runtime import DeviceMeter
    torch.set_num_threads(4);torch.cuda.reset_peak_memory_stats()
    meter=DeviceMeter();meter.start()
    try:
        encoder=Encoder(ROOT,cfg,check);load_sec=time.monotonic()-start
        static=[Image.new('RGB',(320,180),'gray') for _ in range(8)];moving=[]
        for index in range(8):
            image=Image.new('RGB',(320,180),'black');ImageDraw.Draw(image).rectangle((60+index*12,60,100+index*12,120),fill='white');moving.append(image)
        before=time.monotonic();synthetic=encoder.encode([static,moving]);separate=encoder.encode([static])
        synthetic_pass=bool(np.isfinite(synthetic['ordered']).all()
            and np.max(abs(synthetic['ordered'][0]-synthetic['repeated'][0]))<.001
            and np.max(abs(synthetic['ordered'][0]-separate['ordered'][0]))<.001
            and np.linalg.norm(synthetic['ordered'][1]-synthetic['repeated'][1])>1e-5)
        write('synthetic-safe-summary.json',{'scope':'Generated uniform and moving rectangles only; not cash semantics',
            'synthetic_clips':2,'all_checks_passed':synthetic_pass,'elapsed_sec':time.monotonic()-before,
            'finite':True,'static_ordered_repeated_match':bool(np.max(abs(synthetic['ordered'][0]-synthetic['repeated'][0]))<.001),
            'batch_independence':bool(np.max(abs(synthetic['ordered'][0]-separate['ordered'][0]))<.001)})
        if not synthetic_pass:raise ValueError('Synthetic encoder mechanics failed')
        selected=rows();order=probe_order(selected);cache=OUT/'features';cache.mkdir(exist_ok=True)
        elapsed=[];frame_counts=[];window_counts=[];items=[];inventory={}
        for index,row in enumerate(order):
            check()
            if digest(row['path'])!=row['sha256']:raise ValueError('Source changed before extraction')
            features=extract(encoder,Path(row['path']),cfg)
            if digest(row['path'])!=row['sha256']:raise ValueError('Source changed during extraction')
            path=cache/(row['sha256']+'.npz')
            np.savez_compressed(path,ordered=features['ordered'],repeated=features['repeated'],times=features['times'],elapsed_sec=features['elapsed_sec'])
            inventory[path.name]=digest(path);elapsed.append(features['elapsed_sec']);frame_counts.append(features['frames']);window_counts.append(features['windows'])
            memory=psutil.Process().memory_info();rss=memory.rss/2**20;peak_rss=peak_working_set_mib(memory);reserved=torch.cuda.max_memory_reserved()/2**20
            technical={'split':'train','completed_probe_videos':min(index+1,3),'completed_train_videos':index+1,'load_sec':load_sec,
                'model_parameters':encoder.parameters,'feature_latency_mean_sec':float(np.mean(elapsed)),
                'feature_latency_max_sec':max(elapsed),'torch_reserved_peak_mib':reserved,'process_rss_mib':rss,'process_peak_working_set_mib':peak_rss,
                'processor_class':type(encoder.processor).__name__,'processor_center_crop_enabled':encoder.processor.do_center_crop,
                'frames_total':sum(frame_counts),'windows_total':sum(window_counts),'ordered_and_repeated_included':True,
                'new_runtime_installed':False,'manual_annotations_read':False,'holdout_media_inference':False}
            if index<3:write('technical-safe-summary.json',technical)
            if features['elapsed_sec']>cfg['budget']['max_complete_feature_cost_longest_train_sec'] or reserved>cfg['budget']['max_torch_reserved_mib'] or peak_rss>cfg['budget']['max_process_rss_mib']:
                raise RuntimeError('Technical gate failed')
            write('status.json',{'status':'running','phase':'features','completed_train_videos':index+1,'total_train_videos':len(order),
                'elapsed_sec':time.monotonic()-start,'holdout_media_inference':False})
            print(json.dumps({'phase':'features','completed_train_videos':index+1,'total_train_videos':len(order),'elapsed_sec':time.monotonic()-start}),flush=True)
        write('feature-registration.json',{'registered_before_cv':True,'artifact_sha256':inventory,
            'code_registration_sha256':digest(OUT/'registration.json'),'recorded_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()})
        for row in selected:
            path=cache/(row['sha256']+'.npz')
            if digest(path)!=inventory[path.name]:raise ValueError('Cache changed before CV')
            with np.load(path,allow_pickle=False) as data:
                item={k:np.array(data[k]) for k in ['times','ordered','repeated']}
            item.update({k:row[k] for k in ['sha256','group','target','label_sec']});items.append(item)
        check();results,private=grouped_oof(items,cfg);check();verify(registration)
        cache_unchanged=all(digest(cache/name)==sha for name,sha in inventory.items())
        source_unchanged=all(digest(row['path'])==row['sha256'] for row in selected)
        if not cache_unchanged or not source_unchanged:raise ValueError('Frozen feature/source inventory changed')
        check()
        passed=accepted(results,cfg);write('private-oof-results.json',private)
        device_stats=meter.stop()
        check()
        summary={'split':'train','scope':cfg['scope'],'train_original_rows':27,'train_unique_contents':26,'train_auto_groups':24,
            'results':results,'train_gate_passed':passed,'tune_run':False,'holdout_media_inference':False,'holdout_model_evaluation':False,
            'manual_annotations_read':False,'cloud_inference_used':False,'all_sources_unchanged':source_unchanged,
            'cache_inputs_verified_before_and_after_cv':cache_unchanged,'load_sec':load_sec,'run_wall_sec':time.monotonic()-start,
            'synthetic_compatibility_preflight_sec':prior_compute_sec,'compute_wall_sec_including_preflight':prior_compute_sec+time.monotonic()-start,
            'feature_latency_mean_sec':float(np.mean(elapsed)),'feature_latency_max_sec':max(elapsed),
            'sampled_frames_total':sum(frame_counts),'windows_total_per_arm':sum(window_counts),'torch_reserved_peak_mib':torch.cuda.max_memory_reserved()/2**20,
            'process_rss_mib':psutil.Process().memory_info().rss/2**20,'process_peak_working_set_mib':peak_working_set_mib(psutil.Process().memory_info()),'device_wide_statistics':device_stats,
            'technical_failures':0,'registration_sha256':digest(OUT/'registration.json'),'feature_registration_sha256':digest(OUT/'feature-registration.json'),
            'release_eligible':False,'official_score':False,'limitations':cfg['limits']}
        write('safe-summary.json',summary);write('status.json',{'status':'completed','completed_train_videos':26,'train_gate_passed':passed,
            'elapsed_sec':time.monotonic()-start,'tune_run':False,'holdout_media_inference':False})
        print(json.dumps(summary),flush=True)
    finally:meter.stop()


def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['register','run']);args=parser.parse_args();deny_network()
    register() if args.action=='register' else run()


if __name__=='__main__':
    try:main()
    except Exception as error:
        failure={'status':'failed','technical_error_type':type(error).__name__,
            'stack_locations':[{'file':Path(f.filename).name,'line':f.lineno,'function':f.name} for f in traceback.extract_tb(error.__traceback__)],
            'model_outputs_emitted':False,'manual_annotations_read':False,'tune_run':False,'holdout_media_inference':False}
        OUT.mkdir(exist_ok=True);write('failure-safe-summary.json',failure)
        # Preserve any completed checkpoint if a forbidden repeat was attempted.
        if (OUT/'status.json').exists() and json.loads((OUT/'status.json').read_text()).get('status')=='running':write('status.json',failure)
        print(json.dumps(failure),flush=True);sys.exit(1)
