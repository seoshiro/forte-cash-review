import copy
import pytest
from scripts.xclip_tune import select_rows,aggregate,distribution


def manifest():
    rows=[]
    for index in range(10):
        target=index%2
        rows.append({'sha256':f'{index:064x}','group':f'g{index}', 'split':'train' if index==0 else 'tune',
            'target':target,'label_sec':1. if target else None,'duration_sec':10.,'error':None})
    return rows


def test_exact_tune_selection_rejects_cross_split_group_and_does_not_mutate():
    rows=manifest();before=copy.deepcopy(rows)
    assert len(select_rows(rows))==9 and rows==before
    rows[-1]['group']=rows[0]['group']
    with pytest.raises(ValueError):select_rows(rows)


def test_tune_invalid_target_and_negative_point_are_rejected():
    rows=manifest();rows[1]['target']=True
    with pytest.raises(ValueError):select_rows(rows)
    rows=manifest();rows[2]['label_sec']=0.
    with pytest.raises(ValueError):select_rows(rows)


def test_failures_are_not_negatives_and_refused_cases_have_no_fake_latency():
    rows=[{'status':'done','truth':1,'prediction':1,'error_sec':2.,'full_wall_sec':4.},
        {'status':'done','truth':0,'prediction':0,'error_sec':None,'full_wall_sec':6.},
        {'status':'failed','truth':1,'prediction':None,'error_sec':None,'full_wall_sec':8.,'failure_reason':'worker_failed'},
        {'status':'refused','truth':0,'prediction':None,'error_sec':None,'full_wall_sec':None,'failure_reason':'cleanup_unconfirmed'}]
    result=aggregate(rows)
    assert result['completed_metrics']['confusion_matrix_tn_fp_fn_tp']==[[1,0],[0,1]]
    assert result['completed_metrics']['timestamp_matched_positive_videos']==1
    assert result['failed_or_refused']==2 and result['failed_positive_count']==result['failed_negative_count']==1
    assert result['not_attempted_count']==1 and result['full_wall_sec_distribution']['count']==3
    assert result['full_wall_sec_distribution']['median']==6.
    assert result['failure_reasons']=={'cleanup_unconfirmed':1,'worker_failed':1}


def test_wall_distribution_is_aggregate_only_and_rejects_invalid_values():
    assert distribution([1.,3.,2.])['mean']==2.
    assert 'values' not in distribution([1.,2.])
    with pytest.raises(ValueError):distribution([float('nan')])
