"""Validate aggregate-only TUNE evidence; never read predictions, frames or case timings."""
from pathlib import Path
import hashlib,json
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'.private/xclip-tune-control'


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    source=OUT/'safe-summary.json';r=json.loads(source.read_text())
    assert r['status']=='completed' and r['completed_results']==r['attempted_original_videos']==9
    assert r['failed_or_refused']==r['not_attempted_count']==r['over_300_seconds']==0
    m=r['completed_metrics'];tn,fp=m['confusion_matrix_tn_fp_fn_tp'][0];fn,tp=m['confusion_matrix_tn_fp_fn_tp'][1]
    assert tn+fp+fn+tp==m['videos']==9 and tn+fp==4 and fn+tp==5
    assert abs(2*tp/(2*tp+fp+fn)-m['f1'])<1e-12
    assert m['timestamp_matched_positive_videos']==tp==1 and m['timestamp_mae_sec']==3.0
    wall=r['full_wall_sec_distribution']
    assert wall['count']==9 and abs(wall['sum']/9-wall['mean'])<1e-9
    assert all(wall[a]<=wall[b] for a,b in zip(['min','p25','median','p75','p95'],['p25','median','p75','p95','max']))
    assert wall['max']<300 and r['total_assessment_wall_sec']>=wall['sum']
    assert wall==r['completed_wall_sec_distribution']
    # Registration contains labels/paths: select ONLY technical hashes and aggregate count.
    assert sha(OUT/'registration.json')==r['registration_sha256']
    registration=json.loads((OUT/'registration.json').read_text())
    code=registration['code_sha256']
    unique=len({row['sha256'] for row in registration['selection']})
    assert len(registration['selection'])==9 and unique==8
    assert all(sha(ROOT/name)==value for name,value in code.items())
    terminals=list((OUT/'cases').glob('case-*/worker/terminal-safe-summary.json'))
    assert len(terminals)==9
    for path in terminals:
        terminal=json.loads(path.read_text())
        assert terminal['worker_exit_code']==0 and terminal['cleanup_complete'] and terminal['quality_gate_passed']
        assert terminal['worker_report_valid'] and not terminal['deadline_exceeded']
    assert not any(r[k] for k in ['holdout_used','threshold_or_model_changed','final_test','official_score','release_eligible','per_video_outputs_emitted'])
    report={'status':'PASS','scope':'Aggregate arithmetic/integrity only; not an additional model evaluation',
        'source_safe_summary_sha256':sha(source),'registration_sha256':sha(OUT/'registration.json'),
        'registered_source_file_count':len(code),'registered_sources_unchanged':True,
        'original_videos':9,'exact_unique_contents':unique,'completed_cases':9,'owned_case_cleanup_confirmed':9,
        'confusion_matrix_tn_fp_fn_tp':[[tn,fp],[fn,tp]],'f1':m['f1'],
        'tp_point_mae_sec':m['timestamp_mae_sec'],'tp_point_count':tp,'wall_arithmetic_consistent':True,
        'holdout_used':False,'new_model_evaluation':False,'release_eligible':False}
    (OUT/'calculation-safe-summary.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report))


if __name__=='__main__':
    try:main()
    except Exception as error:print(json.dumps({'status':'failed','technical_error_type':type(error).__name__}));raise SystemExit(1)
