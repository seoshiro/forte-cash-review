"""Check aggregate temporal-learning arithmetic, frozen identity and cleanup only."""
from pathlib import Path
import json,hashlib,sys,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'.private/xclip-temporal-recipe-control'
sys.path.insert(0,str(ROOT))
from cashreview.supervision import atomic_json


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    (OUT/'calculation-safe-summary.json').unlink(missing_ok=True)
    result=OUT/'safe-summary.json';r=json.loads(result.read_text());terminal=json.loads((OUT/'run/terminal-safe-summary.json').read_text())
    assert r['status']=='completed' and r['technical_monitor_validated']
    assert terminal['worker_exit_code']==0 and terminal['cleanup_complete'] and terminal['quality_gate_passed'] and terminal['worker_report_valid']
    assert terminal['completed_cases']==terminal['expected_cases']==25 and not terminal['deadline_exceeded']
    registration=OUT/'registration.json';assert sha(registration)==r['registration_sha256']
    hashes=json.loads(registration.read_text())['code_sha256'];assert all(sha(ROOT/name)==value for name,value in hashes.items())
    baseline=r['results']['baseline'];candidate=r['results']['temporal_head'];counts=[]
    for data in [baseline,candidate]:
        tn,fp=data['confusion_matrix_tn_fp_fn_tp'][0];fn,tp=data['confusion_matrix_tn_fp_fn_tp'][1]
        assert tn+fp+fn+tp==26 and tn+fp==12 and fn+tp==14
        assert abs(data['f1']-(2*tp/(2*tp+fp+fn)))<1e-12
        assert data['timestamp_matched_positive_videos']==tp and data['all_positive_candidate_point_count']==14
        if not tp:assert data['timestamp_mae_sec'] is None
        counts.append((tn,fp,fn,tp))
    assert counts[0]==(6,6,2,12)
    cfg=json.loads((ROOT/'config/xclip-temporal-recipe-protocol.json').read_text());gate=cfg['binary_gate'];cm=counts[1]
    binary=cm[2]<=gate['fn_max'] and cm[1]<=gate['fp_max'] and candidate['f1']>=gate['f1_min']
    paired=r['paired_point_diagnostic'];common=paired['common_true_positive_count']
    assert max(0,counts[0][3]+cm[3]-14)<=common<=min(counts[0][3],cm[3])
    point=bool(common and candidate['all_positive_candidate_point_mae_sec']<=baseline['all_positive_candidate_point_mae_sec']
        and paired['temporal_candidate_point_mae_sec']<=paired['baseline_candidate_point_mae_sec'])
    assert r['binary_gate_passed']==binary and r['point_non_regression_gate_passed']==point and r['joint_useful_gate_passed']==bool(binary and point)
    for key in ['tune_used','holdout_used','gpu_used','new_bank_decoding','release_eligible','baseline_or_deployment_pack_changed','per_video_outputs_emitted']:assert r[key] is False
    folder=OUT/'final-train-pack';pack=json.loads((folder/'metadata.json').read_text())
    assert pack['registration_sha256']==sha(registration) and not pack['release_eligible']
    assert sha(folder/'projection.npz')==pack['projection_sha256'] and sha(folder/'head.safetensors')==pack['head_sha256']
    fit=r['full_train_fit_diagnostic'];fit_gate=cfg['full_train_fit_gate']
    full_pass=bool(fit['point_negative_max_eval_loss']<=fit_gate['maximum_eval_loss'] and fit['confusion_matrix_tn_fp_fn_tp']==fit_gate['confusion_matrix_tn_fp_fn_tp'] and fit['positive_point_logits_above_threshold_count']==14 and fit['negative_video_max_logits_below_threshold_count']==12)
    assert r['full_train_fit_gate_passed']==full_pass and fit['train_fit_only_not_validation']
    strata=r['diagnostic_exposure_strata'];exposed=strata['diagnostic_exposed_groups'];remaining=strata['remaining_train_groups']
    assert exposed['groups']==4 and remaining['groups']==20 and exposed['videos']+remaining['videos']==26
    assert not r['independent_validation'] and r['adaptive_recipe_selected_on_four_train_groups']
    for name in ['baseline','temporal_head']:
        matrices=[stratum['results'][name]['confusion_matrix_tn_fp_fn_tp'] for stratum in [exposed,remaining]]
        assert [[sum(m[a][b] for m in matrices) for b in range(2)] for a in range(2)]==r['results'][name]['confusion_matrix_tn_fp_fn_tp']
    report={'status':'PASS','scope':'Aggregate arithmetic/integrity verification only; no additional fit or evaluation',
        'safe_summary_sha256':sha(result),'registration_sha256':sha(registration),'registered_source_files':len(hashes),
        'registered_sources_unchanged':True,'baseline_reproduced':True,'final_private_pack_hashes_verified':True,
        'derived_binary_gate':binary,'derived_point_gate':point,'derived_joint_gate':bool(binary and point),
        'f1_delta':candidate['f1']-baseline['f1'],'fp_delta':cm[1]-counts[0][1],'fn_delta':cm[2]-counts[0][2],
        'all_positive_point_count':14,'all_positive_point_mae_delta_sec':candidate['all_positive_candidate_point_mae_sec']-baseline['all_positive_candidate_point_mae_sec'],
        'common_true_positive_count':common,'monitor_wall_sec_including_cleanup':terminal['elapsed_sec'],
        'release_eligible':False,'tune_used':False,'holdout_used':False}
    atomic_json(OUT/'calculation-safe-summary.json',report);print(json.dumps(report))


if __name__=='__main__':
    try:main()
    except Exception as error:print(json.dumps({'status':'failed','technical_error_type':type(error).__name__}));sys.exit(1)
