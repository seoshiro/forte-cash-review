import json
from pathlib import Path
import numpy as np
import pytest
from qvt_candidate.features import representations
from qvt_candidate import evaluate


def test_temporal_order_and_boundaries_are_content_only():
    f=np.array([[0.,1.],[2.,1.],[2.,4.]],dtype=np.float32)
    value=representations(f)
    np.testing.assert_array_equal(value['static'],f)
    np.testing.assert_array_equal(value['temporal'][0],[0,1,0,0,2,0])
    np.testing.assert_array_equal(value['temporal'][-1],[2,4,0,-3,0,0])
    with pytest.raises(ValueError):representations([[float('nan')]])


def test_entire_duplicate_group_is_excluded_from_fit(monkeypatch):
    items=[];seen=[]
    for group in range(3):
        for target in [0,1]:
            items.append({'group':group,'target':target,'sha256':str(group)+str(target),
                'label_sec':1.0 if target else None,'times':np.array([0.,1.]),'features':np.array([[target,group],[target,group]],dtype=float)})
    def fit(train,arm,cfg):
        groups={item['group'] for item in train};assert len(groups)==2
        seen.append(groups);return groups
    def predict(model,times,features,arm,threshold):
        assert int(features[0,1]) not in model
        return {'prediction':int(features[0,0]),'time_sec':1.,'score':float(features[0,0])}
    monkeypatch.setattr(evaluate,'fit',fit);monkeypatch.setattr(evaluate,'predict',predict)
    reports,private=evaluate.grouped_oof(items,{'head':{'threshold':.5}})
    assert len(seen)==6
    for arm in ['static','temporal']:
        for row in private[arm]:
            # OOF records contain each held-out group exactly twice.
            assert sum(r['group']==row['group'] for r in private[arm])==2
        assert reports[arm]['confusion_matrix_tn_fp_fn_tp']==[[3,0],[0,3]]
    assert reports['constant_positive']['timestamp_mae_sec'] is None
    assert reports['constant_negative']['balanced_accuracy']==.5


def test_production_prediction_has_no_label_or_name_argument():
    class Model:
        def predict_proba(self,values):
            return np.array([[.8,.2],[.3,.7],[.9,.1]])
    result=evaluate.predict(Model(),np.array([0.,2.,4.]),np.ones((3,4)),'temporal',.5)
    assert result=={'prediction':1,'time_sec':2.,'score':.7}


def test_point_supervision_uses_fixed_grid_and_excludes_other_positive_windows():
    cfg=json.loads(Path('config/qvt-protocol.json').read_text())
    items=[{'target':1,'label_sec':1.9,'times':np.array([0.,2.,4.]),'features':np.eye(3)},
        {'target':0,'label_sec':None,'times':np.array([0.,2.,4.]),'features':-np.eye(3)}]
    model=evaluate.fit(items,'static',cfg)
    # One selected positive plus three negative centers; equal video/class mass.
    # StandardScaler is fitted on four observations; weighted classifier follows it.
    np.testing.assert_allclose(model[0].mean_,np.mean(np.array([items[0]['features'][1],*items[1]['features']]),axis=0))
    assert model[0].n_samples_seen_==4


def test_constants_and_missing_localization_never_pass():
    cfg=json.loads(Path('config/qvt-protocol.json').read_text())
    r={'recall':1.,'specificity':0.,'balanced_accuracy':.5,'f1':.8,'timestamp_mae_sec':None}
    assert evaluate.accepted({'static':r,'temporal':r},cfg) is False
