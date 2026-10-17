import json
from pathlib import Path
import numpy as np
import pytest
from xclip_candidate.features import window_targets,probe_order,match_pts
from xclip_candidate import evaluate


def config():return json.loads(Path('config/xclip-protocol.json').read_text())


def test_fixed_windows_coverage_and_probe_order_counts():
    cfg=config();targets=window_targets(11.63,cfg)
    assert targets.shape[1]==8 and targets[0,0]==0
    assert targets[-1,-1]<=11.63-.05+1e-8
    assert np.all(np.diff(targets,axis=1)>0)
    assert np.max(np.diff(targets[:,0]))<=1.000001
    rows=[{'sha256':str(i),'duration_sec':i+11} for i in range(26)]
    ordered=probe_order(rows)
    assert len(ordered)==26 and len({r['sha256'] for r in ordered})==26
    assert [r['duration_sec'] for r in ordered[:3]]==[11,24,36]
    with pytest.raises(ValueError):probe_order(rows+[rows[0]])


def test_persistence_removes_isolated_positive_without_threshold_selection():
    times=np.arange(5.)
    assert evaluate.pool([-.2,-.1,.8,-.3,-.2],times,'max')==(.8,2.)
    assert evaluate.pool([-.2,-.1,.8,-.3,-.2],times,'persistence')==(-.1,1.5)
    assert evaluate.pool([-.2,.4,.8,-.3,-.2],times,'persistence')==(.4,1.5)


def test_equal_video_centroids_not_window_count():
    def item(target,features,point=None):
        return {'target':target,'times':np.arange(len(features),dtype=float),'ordered':np.array(features),'label_sec':point}
    p,n=evaluate.centroids([item(1,[[1.,0.]],0.),item(0,[[1.,0.]]*2),item(0,[[0.,1.]]*20)],'ordered')
    np.testing.assert_allclose(p,[1,0]);np.testing.assert_allclose(n,[2**-.5]*2)


def test_pts_match_respects_shared_sampler_early_tolerance():
    pts=np.array([0.,.28565,.57143,.85714])
    indices=match_pts(pts,np.array([2/7,4/7]),config()['features']['pts_match_tolerance_sec'])
    np.testing.assert_array_equal(indices,[1,2])
    with pytest.raises(ValueError):match_pts(np.array([0.,.6]),np.array([2/7]),.000101)


def test_windows_working_set_peak_survives_lower_current_rss():
    from types import SimpleNamespace
    from scripts.xclip_experiment import peak_working_set_mib
    assert peak_working_set_mib(SimpleNamespace(rss=100,peak_wset=2048*2**20))==2048
    with pytest.raises(RuntimeError):peak_working_set_mib(SimpleNamespace(rss=100))


def test_production_scoring_accepts_only_features_times_centroids_pooling():
    score,sec=evaluate.score_video(np.array([[1.,0.],[1.,0.],[0.,1.]]),np.array([1.,2.,3.]),
        np.array([1.,0.]),np.array([0.,1.]),'persistence')
    assert score==1. and sec==1.5


def test_entire_group_out_for_both_arms_and_both_poolings(monkeypatch):
    items=[]
    for group in range(3):
        for target in [0,1]:
            f=np.array([[group,target],[group,target]],dtype=float)
            items.append({'group':group,'target':target,'sha256':str(group)+str(target),'times':np.array([0.,1.]),
                'label_sec':.5 if target else None,'ordered':f,'repeated':f})
    def centroids(train,arm):
        groups={r['group'] for r in train};assert len(groups)==2;return groups,None
    def score(features,times,positive,negative,mode):
        assert int(features[0,0]) not in positive;return float(features[0,1])*2-1,.5
    monkeypatch.setattr(evaluate,'centroids',centroids);monkeypatch.setattr(evaluate,'score_video',score)
    reports,_=evaluate.grouped_oof(items,config())
    for name in ['ordered_max','ordered_persistence','repeated_max','repeated_persistence']:
        assert reports[name]['confusion_matrix_tn_fp_fn_tp']==[[3,0],[0,3]]
