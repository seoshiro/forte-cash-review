import numpy as np
import pytest
from xclip_candidate.hard_negative import fit
from xclip_candidate.evaluate import centroids,score_video


def test_hard_correct_action_not_background_mean_defines_negative_prototype():
    positive=np.array([[1.,0.,0.],[1.,0.,0.]])
    negative=np.tile([0.,0.,1.],(10,1));negative[1]=negative[8]=[.8,.6,0.]
    items=[{'ordered':positive,'times':np.array([1.,2.]),'target':1,'label_sec':1.},
        {'ordered':negative,'times':np.arange(10,dtype=float),'target':0,'label_sec':None}]
    cfg={'negative_prototype':{'minimum_center_separation_sec':3.,'windows_per_negative_video':2}}
    p,mean=centroids(items,'ordered');hp,hard=fit(items,cfg)
    action=np.stack([negative[1],negative[8]]);times=np.array([1.,8.])
    assert score_video(action,times,p,mean,'max')[0]>0
    assert score_video(action,times,hp,hard,'max')[0]<0
    assert score_video(positive,np.array([1.,2.]),hp,hard,'max')[0]>0


def test_fixed_two_window_count_does_not_silently_fall_back():
    items=[{'ordered':np.array([[1.,0.],[1.,0.]]),'times':np.array([0.,1.]),'target':1,'label_sec':0.},
        {'ordered':np.array([[0.,1.],[0.,1.]]),'times':np.array([0.,1.]),'target':0,'label_sec':None}]
    with pytest.raises(ValueError):fit(items,{'negative_prototype':{'minimum_center_separation_sec':3.,'windows_per_negative_video':2}})


def test_registered_code_and_cache_mutations_cannot_escape_final_check(tmp_path,monkeypatch):
    import scripts.xclip_hardneg as diagnostic
    monkeypatch.setattr(diagnostic,'ROOT',tmp_path);path=tmp_path/'frozen.py';path.write_text('original')
    selected=[{'sha256':'synthetic-sha'}];inventory={'synthetic-sha.npz':'original-hash'}
    monkeypatch.setattr(diagnostic,'sources',lambda:(selected,dict(inventory)))
    registration={'code_sha256':{'frozen.py':diagnostic.sha(path)},'cache_sha256':dict(inventory),'source_sha256':['synthetic-sha']}
    diagnostic.verify_registered(registration);path.write_text('changed')
    with pytest.raises(ValueError):diagnostic.verify_registered(registration)
    path.write_text('original');inventory['synthetic-sha.npz']='changed-hash'
    with pytest.raises(ValueError):diagnostic.verify_registered(registration)
