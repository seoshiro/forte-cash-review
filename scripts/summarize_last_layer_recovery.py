"""Verify registered complete OOF arithmetic, checkpoints and technical authority."""
from pathlib import Path
import json,math,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from cashreview.supervision import atomic_json
from scripts import last_layer_recovery as experiment
EXPECTED='2a45f0817659f5b1ce7ead9c05a1bbdfb92f6cf95cb0ef270e333da4792b5328'


def metrics(value):
    (tn,fp),(fn,tp)=value['confusion_matrix_tn_fp_fn_tp']
    assert all(type(v) is int and v>=0 for v in [tn,fp,fn,tp]) and tn+fp==12 and fn+tp==14 and value['videos']==26
    precision=tp/(tp+fp) if tp+fp else 0.;recall=tp/14;specificity=tn/12
    expected={'precision':precision,'recall':recall,'specificity':specificity,'f1':2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 0.,'balanced_accuracy':(recall+specificity)/2}
    assert all(math.isfinite(value[k]) and abs(value[k]-v)<1e-12 for k,v in expected.items())
    assert value['all_positive_candidate_point_count']==14 and value['timestamp_matched_positive_videos']==tp
    assert math.isfinite(value['all_positive_candidate_point_mae_sec']) and value['all_positive_candidate_point_mae_sec']>=0
    assert value['timestamp_mae_sec'] is None if tp==0 else math.isfinite(value['timestamp_mae_sec']) and value['timestamp_mae_sec']>=0


def main():
    out=experiment.OUT;destination=out/'calculation-safe-summary.json';destination.unlink(missing_ok=True)
    cfg,recipe=experiment.verify(EXPECTED)
    result=json.loads((out/'safe-summary.json').read_text());terminal=json.loads((out/'run/terminal-safe-summary.json').read_text())
    assert result['technical_monitor']==terminal and terminal['cleanup_complete'] and terminal['budget_sec']==1800
    from xclip_candidate.fit_checkpoints import CompletedFits,identity
    cache=CompletedFits(out/'fits',EXPECTED,lambda *a,**kw:None)
    count=cache.count()
    if result['status']!='completed':
        assert terminal['status']=='failed' and not terminal['quality_gate_passed']
        assert result.get('completed_fit_checkpoints',count)==count
        report={'status':'PASS','scope':'Integrity of retained failed attempt only; no complete quality claim','experiment_status':'failed',
                'preserved_complete_fit_checkpoints':count,'complete_cv_fits':min(48,count),'new_fit_or_prediction':False,'release_eligible':False}
        atomic_json(destination,report);print(json.dumps(report));return
    assert terminal['status']=='completed' and terminal['quality_gate_passed'] and terminal['worker_exit_code']==0
    assert terminal['completed_cases']==terminal['passed_cases']==terminal['expected_cases']==76 and not terminal['deadline_exceeded'] and terminal['elapsed_sec']<=1800
    assert count==result['checkpoint_count']==50 and result['cv_fits']==48 and result['full_train_fits']==2
    rows=experiment.prior.previous.original.inputs()[0];groups=sorted({row['group'] for row in rows})
    for ordinal in range(1,51):
        record=cache.validate_commit(out/'fits'/f'{ordinal:04d}')
        enabled=ordinal%2==0
        train=[row for row in rows if row['group']!=groups[(ordinal-1)//2]] if ordinal<=48 else rows
        assert record['ordinal']==ordinal and record['adapter_enabled']==enabled and record['optimizer_steps']==500
        assert record['fit_identity_sha256']==identity(train,recipe,enabled)
    replay=json.loads((out/'replay-safe-summary.json').read_text())
    assert replay['status']=='PASS' and replay['videos']==26 and replay['windows']==678 and replay['views']==2 and replay['maximum_absolute_error']==0
    assert result['registration_sha256']==EXPECTED and result['zero_adapter_max_absolute_error']==0
    for value in result['results'].values():metrics(value)
    baseline=result['results']['baseline'];adapter=result['results']['last_layer_adapter'];control=result['results']['regularized_frozen_head'];gate=recipe['gates']
    assert baseline['confusion_matrix_tn_fp_fn_tp']==recipe['evaluation']['baseline_cm'] and baseline['f1']==.75
    cm=adapter['confusion_matrix_tn_fp_fn_tp'];binary=cm[1][0]<=gate['fn_max'] and cm[0][1]<=gate['fp_max'] and adapter['f1']>=gate['f1_min'] and adapter['f1']>control['f1']
    paired=result['paired_point_diagnostic'];common=paired['common_true_positive_count']
    assert max(0,baseline['confusion_matrix_tn_fp_fn_tp'][1][1]+cm[1][1]-14)<=common<=min(baseline['confusion_matrix_tn_fp_fn_tp'][1][1],cm[1][1])
    point=bool(common and adapter['all_positive_candidate_point_mae_sec']<=baseline['all_positive_candidate_point_mae_sec'] and paired['adapter_point_mae_sec']<=paired['baseline_point_mae_sec'])
    assert result['binary_gate_passed']==binary and result['point_gate_passed']==point and result['joint_gate_passed']==bool(binary and point)
    resource=result['resources'];assert resource['peak_working_set_mib']<=4096 and resource['torch_peak_reserved_mib']<=5000
    assert resource['minimum_available_ram_mib']>=1024 and resource['minimum_free_gpu_mib']>=256
    assert result['source_split_baseline_and_research_ui_preserved'] and result['adaptive_exploratory_train']
    for key in ['tune_used','holdout_used','independent_validation','release_eligible','official_score','semantic_types_rules_or_evidence_validated','per_video_outputs_emitted','cloud_inference_used']:assert result[key] is False
    report={'status':'PASS','experiment_status':'completed','scope':'Complete exploratory TRAIN OOF arithmetic/checkpoint/authority verification only',
            'registration_sha256':EXPECTED,'verified_cv_fits':48,'verified_full_train_fits':2,'verified_atomic_fit_checkpoints':count,
            'binary_gate_passed':binary,'point_gate_passed':point,'joint_gate_passed':bool(binary and point),
            'adapter_minus_baseline_f1':adapter['f1']-baseline['f1'],'adapter_minus_matched_head_f1':adapter['f1']-control['f1'],
            'adapter_minus_baseline_all_positive_point_mae_sec':adapter['all_positive_candidate_point_mae_sec']-baseline['all_positive_candidate_point_mae_sec'],
            'monitor_wall_sec_including_cleanup':terminal['elapsed_sec'],'new_fit_or_prediction':False,'release_eligible':False}
    atomic_json(destination,report);print(json.dumps(report))


if __name__=='__main__':
    try:main()
    except Exception as error:print(json.dumps({'status':'failed','technical_error_type':type(error).__name__,'raw_private_content_emitted':False}));sys.exit(1)
