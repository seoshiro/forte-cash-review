"""One preregistered TRAIN control; at most one conditional TUNE. Safe stdout."""
from pathlib import Path
import argparse,hashlib,json,os,sys,time,statistics,traceback
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def rank(seed,kind,value):return hashlib.sha256(f'{seed}:{kind}:{value}'.encode()).hexdigest()

def source_digests():
    paths=list((ROOT/'budget_candidate').glob('*.py'))+list((ROOT/'gate_candidate').glob('*.py'))+list((ROOT/'cashreview').glob('*.py'))+[ROOT/'scripts/evaluate_gate.py',ROOT/'config/gate-protocol.json',ROOT/'config/budget-protocol.json',ROOT/'config/rules.json']
    return {str(p.relative_to(ROOT)):digest(p) for p in paths}

def select(rows,config):
    seed=config['seed'];chosen=[];groups=set()
    for label in [0,1]:
        pool={}
        for r in rows:
            if r['split']=='train' and not r['error'] and r['target']==label:pool.setdefault(r['group'],[]).append(r)
        candidates=sorted(pool,key=lambda g:rank(seed,'group',g))
        selected=0
        for group in candidates:
            if group in groups:continue
            r=min(pool[group],key=lambda r:rank(seed,'source',r['sha256']))
            chosen.append(r);groups.add(group);selected+=1
            if selected==config['per_label']:break
        if selected!=config['per_label']:raise RuntimeError('Insufficient distinct TRAIN groups')
    return sorted(chosen,key=lambda r:rank(seed,'order',r['sha256']))

def register():
    protocol=ROOT/'config/gate-protocol.json';config=json.loads(protocol.read_text())
    manifest=ROOT/'.private/dataset/manifest.json';rows=json.loads(manifest.read_text(encoding='utf-8'))
    chosen=select(rows,config['selection']);out=ROOT/'.private/gate-control';out.mkdir(exist_ok=True)
    registration={'protocol_id':config['protocol_id'],'seed':config['selection']['seed'],'requested':len(chosen),
                  'source_sha256':[r['sha256'] for r in chosen],'manifest_sha256':digest(manifest),'split_sha256':digest(ROOT/'.private/dataset/split.json'),
                  'protocol_sha256':digest(protocol),'frozen_source_digests':source_digests()}
    target=out/'registration.json'
    if target.exists() and json.loads(target.read_text())!=registration:raise RuntimeError('Existing registration differs; no silent reselection')
    if not target.exists():target.write_text(json.dumps(registration,indent=2))
    safe={'registered':True,'protocol_id':config['protocol_id'],'seed':registration['seed'],'selected':len(chosen),
          'positive':sum(r['target'] for r in chosen),'negative':sum(not r['target'] for r in chosen),
          'unique_groups':len({r['group'] for r in chosen}),'registration_sha256':digest(target),'holdout_opened':False,'tune_started':False}
    (out/'registration-safe-summary.json').write_text(json.dumps(safe,indent=2));print(json.dumps(safe),flush=True)
    return registration,config,rows,out

def metrics(y,p):
    tn=sum(t==0 and v==0 for t,v in zip(y,p));fp=sum(t==0 and v==1 for t,v in zip(y,p))
    fn=sum(t==1 and v==0 for t,v in zip(y,p));tp=sum(t==1 and v==1 for t,v in zip(y,p))
    precision=tp/(tp+fp) if tp+fp else 0.;recall=tp/(tp+fn) if tp+fn else 0.;spec=tn/(tn+fp) if tn+fp else 0.
    return {'confusion_matrix_tn_fp_fn_tp':[[tn,fp],[fn,tp]],'precision':precision,'recall':recall,'specificity':spec,
            'balanced_accuracy':(spec+recall)/2,'f1':2*precision*recall/(precision+recall) if precision+recall else 0.}

def run_phase(engine,phase,selected,out,config,load):
    target=out/f'{phase}-safe-summary.json'
    if target.exists():raise RuntimeError('This frozen phase was already completed; no repeated selection')
    folder=out/phase
    if folder.exists():raise RuntimeError('An interrupted phase exists; inspect its status before any retry')
    folder.mkdir();truth=[];pred=[];gate=[];latency=[];failures={};unchanged=True;errors=[];rejected_detail=0;gate_calls=0
    for i,row in enumerate(selected):
        private=folder/f'{i:03d}';private.mkdir();path=Path(row['path']);tick=time.monotonic()
        before=digest(path)
        try:
            result=engine.analyze(path,f'private-gate-{i}',private)
            (private/'result.json').write_text(json.dumps(result,ensure_ascii=False),encoding='utf-8')
            m=json.loads((private/'metrics.json').read_text());coarse=bool(m['gate_calls'][0]['visible_violation'])
            truth.append(row['target']);pred.append(int(result['verdict']=='violation'));gate.append(int(coarse));gate_calls+=len(m['gate_calls'])
            rejected_detail+=int(coarse and not pred[-1])
            if pred[-1] and row['target'] and row['label_sec'] is not None:errors.append(min(abs(e['timecode_sec']-row['label_sec']) for e in result['violations']))
        except Exception as error:
            code=getattr(error,'code',type(error).__name__);failures[code]=failures.get(code,0)+1
        latency.append(time.monotonic()-tick);unchanged &= before==digest(path)
        print(json.dumps({'phase':phase,'attempted':i+1,'requested':len(selected),'completed':len(truth),'technical_failures':sum(failures.values())}),flush=True)
    gm=metrics(truth,gate);fm=metrics(truth,pred);pos=metrics(truth,[1]*len(truth));neg=metrics(truth,[0]*len(truth))
    limits=config['control_acceptance']
    checks={'no_technical_failures':not failures,'all_completed':len(truth)==len(selected),'source_checksums_unchanged':unchanged,
            'gate_recall':gm['recall']>=limits['coarse_gate_recall_min'],'gate_specificity':gm['specificity']>=limits['coarse_gate_specificity_min'],
            'gate_balanced_accuracy':gm['balanced_accuracy']>=limits['coarse_gate_balanced_accuracy_min'],
            'final_recall':fm['recall']>=limits['final_recall_min'],'final_specificity':fm['specificity']>=limits['final_specificity_min'],
            'final_balanced_accuracy':fm['balanced_accuracy']>=limits['final_balanced_accuracy_min'],'final_f1':fm['f1']>=limits['final_f1_min'],
            'beats_constant_controls':fm['balanced_accuracy']>max(pos['balanced_accuracy'],neg['balanced_accuracy']),
            'engine_latency':max(latency)<=limits['max_engine_latency_sec']}
    report={'protocol_id':config['protocol_id'],'split':phase,'requested':len(selected),'completed':len(truth),'technical_failures':failures,
            'coarse_gate':gm,'final_pipeline':fm,'always_positive_control':pos,'always_negative_control':neg,
            'checks':checks,'passed_control':all(checks.values()),'model_load_sec':load,
            'engine_latency_mean_sec':statistics.mean(latency),'engine_latency_max_sec':max(latency),'latency_scope':'Complete engine calls, excluding upload, queue and model load',
            'gate_generation_calls':gate_calls,'coarse_positive_without_final_event':rejected_detail,
            'timestamp_matched_positive_count':len(errors),'timestamp_mae_sec':statistics.mean(errors) if errors else None,
            'vram_allocated_peak_mib':engine.torch.cuda.max_memory_allocated()/2**20,'runtime_torch':str(engine.torch.__version__),
            'holdout_opened':False,'official_score':False,'quality_denominator':'Valid completed videos only; failures separately reported',
            'limitations':'Small TRAIN control or exploratory reused TUNE; type/frame relevance unannotated; sparse coverage; auto groups not human reviewed'}
    target.write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)
    return report

def main():
    os.chdir(ROOT);p=argparse.ArgumentParser();p.add_argument('--register-only',action='store_true');p.add_argument('--run-tune-if-passed',action='store_true');a=p.parse_args()
    registration,config,rows,out=register()
    if a.register_only:return
    from scripts.diagnose_synthetic_semantics import ensure_idle
    ensure_idle()
    os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1')
    from cashreview.offline import deny_network
    deny_network()
    from gate_candidate.engine import GatedEngine
    (out/'status.json').write_text(json.dumps({'stage':'model_loading','tune_started':False,'holdout_opened':False}))
    tick=time.monotonic();engine=GatedEngine('bf16');load=time.monotonic()-tick
    if str(engine.torch.__version__)!=config['runtime']['initial_torch']:raise RuntimeError('Runtime differs from frozen TRAIN control')
    index={r['sha256']:r for r in rows if r['split']=='train' and not r['error']}
    selected=[index[s] for s in registration['source_sha256']]
    (out/'status.json').write_text(json.dumps({'stage':'train_control','tune_started':False,'holdout_opened':False}))
    report=run_phase(engine,'train',selected,out,config,load)
    if a.run_tune_if_passed and report['passed_control']:
        if source_digests()!=registration['frozen_source_digests']:raise RuntimeError('Code/config changed after registration; TUNE not started')
        (out/'accepted-frozen-registration.json').write_text(json.dumps(registration,indent=2))
        (out/'status.json').write_text(json.dumps({'stage':'single_frozen_tune','tune_started':True,'holdout_opened':False}))
        tune=sorted([r for r in rows if r['split']=='tune' and not r['error']],key=lambda r:rank(config['selection']['seed'],'tune-order',r['sha256']))
        run_phase(engine,'tune',tune,out,config,load)
    (out/'status.json').write_text(json.dumps({'stage':'complete','train_passed_control':report['passed_control'],'tune_started':(out/'tune-safe-summary.json').exists(),'holdout_opened':False}))

if __name__=='__main__':
    try:main()
    except Exception as error:
        print(json.dumps({'status':'not_started_or_failed','error_type':type(error).__name__,'source_locations':[{'file':Path(f.filename).name,'line':f.lineno,'function':f.name} for f in traceback.extract_tb(error.__traceback__)],'private_content_emitted':False}),flush=True);sys.exit(1)
