"""Private real-video evaluation; never prints predictions, descriptions or evidence."""
from pathlib import Path
import argparse, sys, os, json, time, hashlib, statistics, csv,subprocess
from collections import Counter
os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1',DO_NOT_TRACK='1')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from cashreview.offline import deny_network
from cashreview.engine import LocalEngine
from cashreview.observations import ObservationError
from sklearn.metrics import confusion_matrix,precision_recall_fscore_support


def main():
    p=argparse.ArgumentParser();p.add_argument('--split',choices=['train','tune','holdout'],default='tune');p.add_argument('--strategy',choices=['uniform','coarse_refine'],default='uniform');p.add_argument('--limit',type=int);p.add_argument('--open-final-holdout',action='store_true');a=p.parse_args()
    root=Path('.private');dataset=root/'dataset';cfg=Path('config/experiment.json');rule=Path('config/rules.json');split=json.loads((dataset/'split.json').read_text(encoding='utf-8'))
    if a.split=='holdout':
        if not a.open_final_holdout:raise RuntimeError('Holdout remains closed; freeze parameters first')
        if split['holdout_opened']:raise RuntimeError('Holdout was already opened; independent evaluation cannot be repeated')
        if not json.loads(cfg.read_text())['scene_groups_human_reviewed']:raise RuntimeError('Human scene-family grouping review required')
        split['holdout_opened']=True;split['frozen_config_sha256']=hashlib.file_digest(cfg.open('rb'),'sha256').hexdigest();split['frozen_rules_sha256']=hashlib.file_digest(rule.open('rb'),'sha256').hexdigest();(dataset/'split.json').write_text(json.dumps(split,indent=2),encoding='utf-8')
    rows=[r for r in json.loads((dataset/'manifest.json').read_text(encoding='utf-8')) if r['split']==a.split and not r['error']]
    if a.limit:rows=rows[:a.limit]
    run_id=time.strftime('%Y%m%dT%H%M%SZ',time.gmtime())+'-'+a.strategy+'-'+a.split;out=root/'experiments'/run_id;out.mkdir(parents=True)
    (out/'frozen-config.json').write_bytes(cfg.read_bytes());(out/'frozen-rules.json').write_bytes(rule.read_bytes());(out/'frozen-split.json').write_text(json.dumps(split),encoding='utf-8')
    source_files=list(Path('cashreview').glob('*.py'))+[Path('scripts/evaluate.py'),cfg,rule]
    (out/'frozen-source-digests.json').write_text(json.dumps({str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in source_files},indent=2),encoding='utf-8')
    (out/'code-commit.txt').write_text(subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),encoding='ascii')
    deny_network();start=time.monotonic();engine=LocalEngine();load_sec=time.monotonic()-start
    y=[];pred=[];errors=[];times=[];local=[];failed=0;failure_categories=Counter()
    for i,r in enumerate(rows):
        start=time.monotonic();f=out/f'{i:03d}';f.mkdir()
        try:
            result=engine.analyze(Path(r['path']),f'local-{i}',f,a.strategy)
            (f/'result.json').write_text(json.dumps(result,ensure_ascii=False),encoding='utf-8')
            truth=r['target'];guess=int(result['verdict']=='violation');y.append(truth);pred.append(guess)
            if truth and guess and r['label_sec'] is not None:errors.append(min(abs(v['timecode_sec']-r['label_sec']) for v in result['violations']))
            local.append({'sha256':r['sha256'],'truth':truth,'prediction':guess,'error':None})
        except Exception as e:
            failure_categories[e.code if isinstance(e,ObservationError) else type(e).__name__]+=1
            failed+=1;local.append({'sha256':r['sha256'],'error':type(e).__name__})
        times.append(time.monotonic()-start)
        # Safe progress is aggregate counts only.
        print(json.dumps({'completed':i+1,'requested':len(rows),'failed':failed}),flush=True)
    cm=confusion_matrix(y,pred,labels=[0,1]).tolist()
    if y:precision,recall,f1,_=precision_recall_fscore_support(y,pred,average='binary',zero_division=0)
    else:precision=recall=f1=None
    summary={'run_id':run_id,'split':a.split,'strategy':a.strategy,'requested':len(rows),'completed':len(y),'failed':failed,'confusion_matrix_tn_fp_fn_tp':cm,'precision':precision,'recall':recall,'f1':f1,'quality_denominator':'successfully completed videos only; failed reported separately','matched_positive_timing_count':len(errors),'timestamp_mae_sec':statistics.mean(errors) if errors else None,'timestamp_median_error_sec':statistics.median(errors) if errors else None,'latency_mean_sec':statistics.mean(times) if times else None,'latency_max_sec':max(times) if times else None,'latency_scope':'all local batch attempts including failures; excludes upload and one-time model load','over_300_sec':sum(t>300 for t in times),'model_load_sec':load_sec,'vram_peak_mib':engine.torch.cuda.max_memory_allocated()/2**20,'config_sha256':hashlib.file_digest(cfg.open('rb'),'sha256').hexdigest(),'split_sha256':hashlib.file_digest((out/'frozen-split.json').open('rb'),'sha256').hexdigest(),'official_score':False,'frame_relevance':'requires local human annotations','classification_quality':'unmeasured: event-type annotations not provided','limitations':'Small dataset; scene-family groups pending human review. Timestamp metrics only on detected positive videos; one target timestamp is incomplete event ground truth.'}
    summary['technical_failure_categories']=dict(failure_categories)
    (out/'private-predictions.json').write_text(json.dumps(local),encoding='utf-8');(out/'safe-summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(json.dumps(summary))

if __name__=='__main__':main()
