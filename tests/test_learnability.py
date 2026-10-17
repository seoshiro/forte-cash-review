import torch
import json
from pathlib import Path
import numpy as np
from xclip_candidate.learnability import subset,zero_logit_check,training_fit,arm
from xclip_candidate.temporal_head import fit_head,fit_projection


def test_subset_is_fixed_class_balanced_and_group_disjoint():
    rows=[{'sha256':str(i)*64,'target':i%2,'group':f'g{i//2}'} for i in range(8)]
    chosen=subset(rows)
    assert [i['sha256'] for i in chosen]==[rows[i]['sha256'] for i in [0,2,5,7]]
    assert sum(i['target'] for i in chosen)==2 and len({i['group'] for i in chosen})==4
    assert subset(list(reversed(rows)))==chosen


def test_gradient_probe_checks_actual_loss_signs_and_masks_not_network_zeroing():
    valid=torch.tensor([[True,True,True,False],[True,True,False,False],[True,True,True,True],[True,True,True,False]])
    report=zero_logit_check(valid,[0,2],[1,3],[1,3])
    assert report['positive_gradient_sum']==-.25 and report['negative_gradient_sum']==.25
    assert report['other_positive_positions_have_zero_direct_loss_gradient'] and report['invalid_padding_has_zero_gradient']


def test_instrumentation_preserves_original_dropout_training_trajectory():
    root=Path(__file__).resolve().parents[1];original=json.loads((root/'config/xclip-temporal-protocol.json').read_text())
    diagnostic=json.loads((root/'config/temporal-learnability-protocol.json').read_text())
    rng=np.random.default_rng(419);rows=[{'ordered':rng.normal(size=(8+i,16)),'times':np.arange(8+i,dtype=float),
        'target':i%2,'label_sec':3. if i%2 else None} for i in range(4)]
    torch.set_num_threads(1);original['head']['steps']=3
    trained,_=fit_head(rows,original);expected=training_fit(trained,rows)
    recipe={**diagnostic['arms']['original_recipe'],'steps':3};diagnostic['shared']['eval_steps']=[0,1,2,3]
    result=arm(rows,fit_projection(rows,8),diagnostic,recipe)
    assert result['after']['confusion_matrix_tn_fp_fn_tp']==expected['confusion_matrix_tn_fp_fn_tp']
    assert abs(result['after']['point_negative_max_eval_loss']-expected['point_negative_max_eval_loss'])<1e-8
    assert abs(result['after']['positive_point_logit_mean']-expected['positive_point_logit_mean'])<1e-8
