import copy,json,inspect,warnings
from pathlib import Path
from unittest.mock import patch
import numpy as np
import pytest
from sklearn.exceptions import ConvergenceWarning
from xclip_candidate import linear_head as linear


def cfg():return json.loads((Path(__file__).resolve().parents[1]/'config/xclip-linear-protocol.json').read_text())


def items():
    result=[]
    for k in range(6):
        target=k%2
        features=np.array([[1.,(-1 if target else 1)*(.4+.03*k),.2],
            [1.,(-1 if target else 1)*(1+.03*k),.1],
            [1.,(-1 if target else 1)*(.5+.02*k),.3]])
        result.append({'sha256':str(k),'group':str(k//2),'target':target,'label_sec':1. if target else None,
            'ordered':features,'times':np.array([0.,1.,2.])})
    return result


def test_supervision_and_equal_class_video_weights():
    data=items();X,y,w=linear.supervised_windows(data)
    assert X.shape==(12,3)
    assert np.allclose(w[y==0].sum(),3) and np.allclose(w[y==1].sum(),3)
    assert np.allclose(w[y==0],1/3) and np.allclose(w[y==1],1)
    assert np.allclose(X[3],linear.unit(data[1]['ordered'])[1])


def test_scaler_uses_same_train_only_samples_and_weights():
    data=items();train=[i for i in data if i['group']!='0']
    X,y,w=linear.supervised_windows(train);scaler,model=linear.fit_head(train,cfg())
    assert np.allclose(scaler.mean_,np.average(X,axis=0,weights=w))
    assert model.class_weight is None and model.C==.01 and model.fit_intercept


def test_grouped_cv_excludes_all_neighbour_windows_and_preserves_inputs():
    data=items();before=copy.deepcopy(data);calls=[];original=linear.fit_head
    def spy(train,config):
        calls.append({i['group'] for i in train});return original(train,config)
    with patch.object(linear,'fit_head',side_effect=spy):aggregate,private=linear.evaluate(data,cfg())
    assert calls==[{'1','2'},{'0','2'},{'0','1'}]
    assert all(len(rows)==6 for rows in private.values())
    assert aggregate['results']['linear_head']['all_positive_candidate_point_count']==3
    assert aggregate['cache_only_cpu_runtime']['linear_head']['folds']==3
    for a,b in zip(data,before):
        assert a['label_sec']==b['label_sec'] and np.array_equal(a['ordered'],b['ordered'])


def test_prediction_has_no_supervision_or_identity_interface():
    assert list(inspect.signature(linear.predict_head).parameters)==['head','features','times','threshold_logit']
    data=items();head=linear.fit_head(data[2:],cfg())
    result=linear.predict_head(head,data[0]['ordered'],data[0]['times'],0)
    assert result['time_sec'] in data[0]['times']
    assert set(result)=={'prediction','score','time_sec'}


def test_warning_fails_without_changing_parameters_or_refitting():
    with patch.object(linear.LogisticRegression,'fit',side_effect=lambda *a,**k:warnings.warn('synthetic',ConvergenceWarning)) as fit:
        with pytest.raises(ConvergenceWarning):linear.fit_head(items(),cfg())
    assert fit.call_count==1


def test_cache_validation_rejects_duplicate_contents_invalid_pts_and_points():
    data=items();linear.validate_items(data)
    with pytest.raises(ValueError):linear.validate_items(data+[data[0]])
    data=items();data[0]['times']=np.array([0.,0.,2.])
    with pytest.raises(ValueError):linear.validate_items(data)
    data=items();data[0]['label_sec']=0.
    with pytest.raises(ValueError):linear.validate_items(data)


def test_late_resource_failure_revokes_completed_reports(tmp_path):
    from scripts.xclip_linear import persist_success
    import time
    calls=0
    def check():
        nonlocal calls
        calls+=1
        if calls==3:raise RuntimeError('synthetic late resource limit')
        return {'process_peak_working_set_mib':10.0,'minimum_available_system_ram_mib':2048.0}
    with pytest.raises(RuntimeError):persist_success(tmp_path,{'status':'completed'},check,time.monotonic()+10)
    assert not (tmp_path/'quality-safe-summary.json').exists()
    assert not (tmp_path/'worker-safe-summary.json').exists()
