"""BUDGET-01 technical gate. Refuses to overlap the frozen GPU baseline."""
from pathlib import Path
import os,sys,json,time,argparse,hashlib,statistics,psutil
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));os.chdir(ROOT)
def ensure_idle():
    for relative in ['structured/status.json','vlm-pipeline/status.json']:
        p=ROOT/'.private'/relative
        if p.exists() and json.loads(p.read_text())['stage'] in ['download_preparation','technical_benchmark','tuning_uniform','tuning_coarse_refine','structured_technical_benchmark','structured_tune_uniform','structured_train_uniform','latency_profile']:
            raise RuntimeError('Frozen baseline is active; no candidate GPU workload started')
    for process in psutil.process_iter():
        try:
            if process.pid!=os.getpid() and Path(process.cwd()).resolve()==ROOT and any(Path(x).name in {'benchmark.py','evaluate.py','diagnose_synthetic_structure.py','qa_model_api.py','profile_baseline_stages.py'} for x in process.cmdline()[1:]):
                raise RuntimeError('Another owned model workload is active')
        except (psutil.Error,OSError,ValueError):pass

def main():
    p=argparse.ArgumentParser();p.add_argument('--precision',choices=['bf16','nf4'],default='bf16');a=p.parse_args()
    gate=ROOT/'.private/budget-technical-gate.json'
    if not gate.is_file():raise RuntimeError('Completed profile review and negative-output diagnostic are required before candidate execution')
    reviewed=json.loads(gate.read_text())
    if reviewed.get('protocol_sha256')!=hashlib.sha256((ROOT/'config/budget-protocol.json').read_bytes()).hexdigest() or not reviewed.get('empty_decoder_passed'):
        raise RuntimeError('Candidate technical gate does not match the frozen protocol')
    ensure_idle() # before any torch import, CUDA context, data read or model load
    os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1')
    from cashreview.offline import deny_network
    deny_network()
    from budget_candidate.engine import BudgetEngine
    from cashreview.video import Sample
    from PIL import Image
    out=ROOT/'.private/budget-benchmark'/time.strftime('%Y%m%dT%H%M%SZ',time.gmtime());out.mkdir(parents=True)
    protocol=ROOT/'config/budget-protocol.json';(out/'frozen-protocol.json').write_bytes(protocol.read_bytes())
    registration=json.loads((ROOT/'.private/budget-registration-safe-summary.json').read_text())
    if hashlib.sha256(protocol.read_bytes()).hexdigest()!=registration['protocol_sha256']:raise RuntimeError('Registered protocol changed before candidate execution')
    source=list((ROOT/'budget_candidate').glob('*.py'))+list((ROOT/'cashreview').glob('*.py'))+[Path(__file__),protocol]
    (out/'frozen-source-digests.json').write_text(json.dumps({str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in source},indent=2),encoding='utf-8')
    (out/'stage.json').write_text(json.dumps({'stage':'model_loading'}))
    started=time.monotonic();engine=BudgetEngine(a.precision);load=time.monotonic()-started
    (out/'stage.json').write_text(json.dumps({'stage':'synthetic_contract'}))
    # First model generation is synthetic only; no bank image is exposed.
    synthetic=engine.observe([Sample(float(i),Image.new('RGB',(224,224),(25,65,40))) for i in range(8)],engine.config['max_events_coarse'],engine.config['max_new_tokens_coarse'],time.monotonic()+220)
    synthetic_counts={'raw_events':len(synthetic['events']),
                      'qualifying_events':sum(e['all_conditions_visible'] and e['confidence']>=engine.config['threshold'] for e in synthetic['events']),
                      'scope':'generated blank images only; diagnostic, not real-data specificity'}
    (out/'stage.json').write_text(json.dumps({'stage':'train_probes','requested':3}))
    rows=[r for r in json.loads((ROOT/'.private/dataset/manifest.json').read_text(encoding='utf-8')) if r['split']=='train' and not r['error']]
    selected=[next(r for r in rows if r['target']==target) for target in [0,1]]
    longest=max(rows,key=lambda r:r['duration_sec'])
    if not any(r['sha256']==longest['sha256'] for r in selected):selected.append(longest)
    elapsed=[];success=0;unchanged=True;failures={};metrics=[];truth=[];predictions=[]
    for index,row in enumerate(selected):
        path=Path(row['path']);before=hashlib.file_digest(path.open('rb'),'sha256').hexdigest();tick=time.monotonic()
        try:
            result=engine.analyze(path,f'local-{index}',out/f'{index:03d}')
            (out/f'{index:03d}'/'result.json').write_text(json.dumps(result,ensure_ascii=False),encoding='utf-8')
            metrics.append(json.loads((out/f'{index:03d}'/'metrics.json').read_text()));success+=1
            truth.append(row['target']);predictions.append(int(result['verdict']=='violation'))
        except Exception as error:
            code=getattr(error,'code',type(error).__name__);failures[code]=failures.get(code,0)+1
        elapsed.append(time.monotonic()-tick)
        unchanged &= before==hashlib.file_digest(path.open('rb'),'sha256').hexdigest()
        print(json.dumps({'phase':'train_probes','attempted':index+1,'requested':len(selected),'valid':success}),flush=True)
    report={'requested':len(selected),'schema_valid':success,'technical_failures':failures,
            'source_checksums_unchanged':unchanged,'model_load_sec':load,
            'engine_latency_mean_sec':statistics.mean(elapsed),'engine_latency_max_sec':max(elapsed),
            'latency_scope':'full engine.analyze attempts; excludes upload, queue, process startup and model load',
            'precision':a.precision,'synthetic_schema_valid':True,'guard':engine.guard,
            'synthetic_blank_diagnostic':synthetic_counts,
            'model_technical':engine.model_technical,
            'protocol_sha256':hashlib.sha256(protocol.read_bytes()).hexdigest(),
            'quality_scope':'binary TRAIN probes only, not TUNE; event type/frame relevance unannotated','holdout_read':False}
    from sklearn.metrics import confusion_matrix,precision_recall_fscore_support
    matrix=confusion_matrix(truth,predictions,labels=[0,1]).tolist();tn,fp=matrix[0];fn,tp=matrix[1]
    precision,recall,f1,_=precision_recall_fscore_support(truth,predictions,average='binary',zero_division=0) if truth else (None,None,None,None)
    specificity=tn/(tn+fp) if tn+fp else None
    report['train_probe_binary']={'valid_videos':len(truth),'confusion_matrix_tn_fp_fn_tp':matrix,
           'precision':precision,'recall':recall,'f1':f1,'specificity':specificity,
           'balanced_accuracy':(specificity+recall)/2 if specificity is not None and recall is not None else None,
           'denominator':'valid completed TRAIN probes only; failed reported separately'}
    for phase in ['coarse_decode_sec','refine_decode_sec','evidence_decode_sec']:
        values=[m['phases'].get(phase,0.) for m in metrics];report[phase+'_mean']=statistics.mean(values) if values else None
    report['vram_peak_mib']=max((m['vram_peak_mib'] for m in metrics),default=None)
    report['vram_reserved_peak_mib']=max((m['vram_reserved_peak_mib'] for m in metrics),default=None)
    (out/'safe-summary.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report))
    (out/'stage.json').write_text(json.dumps({'stage':'complete'}))

if __name__=='__main__':
    try:main()
    except Exception as error:
        import traceback
        print(json.dumps({'status':'not_started_or_failed','error_type':type(error).__name__,
             'code':getattr(error,'code',None),'stack_locations':[{'file':Path(f.filename).name,'line':f.lineno,'function':f.name} for f in traceback.extract_tb(error.__traceback__)],
             'no_raw_model_error_emitted':True}));sys.exit(1)
