from pathlib import Path
import json
import numpy as np
import pytest
from PIL import Image,ImageDraw
from cashreview.research_split import unique_train_contents
from motion_candidate.features import summarize_frames
from motion_candidate import evaluate


def row(digest='a',group='synthetic-a',split='train',target=0,point=None):
    return {'sha256':digest*64,'group':group,'split':split,'target':target,'label_sec':point,'error':None}


def test_duplicate_bookkeeping_is_explicit_and_does_not_remove_extra_groups():
    rows=[row(),row(),row('b','synthetic-b',target=1,point=2)]
    selected=unique_train_contents(rows)
    assert len(selected)==2 and sum(r['manifest_multiplicity'] for r in selected)==3
    assert len({r['group'] for r in selected})==2
    assert rows[0]==rows[1]  # Original manifest inputs were not edited.


@pytest.mark.parametrize('changes',[{'split':'tune'},{'group':'other'},{'target':1},{'label_sec':1.}])
def test_duplicate_conflicts_and_leakage_fail_closed(changes):
    a=row();b=dict(a);b.update(changes)
    with pytest.raises(ValueError):unique_train_contents([a,b])


def test_near_duplicate_group_crossing_splits_is_rejected():
    with pytest.raises(ValueError,match='group crosses'):
        unique_train_contents([row(),row('b',split='holdout')])


def test_synthetic_motion_and_brightness_invariance():
    cfg=json.loads(Path('config/motion-protocol.json').read_text())
    frames=[Image.new('RGB',(96,96),'black') for _ in range(8)]
    static=summarize_frames(frames,list(np.arange(8)*.5),cfg)
    assert static['bag'].shape==(60,) and static['windows'].shape==(7,18)
    assert np.isfinite(static['bag']).all() and np.all(static['windows']==0)
    flashed=[Image.new('RGB',(96,96),(i*20,)*3) for i in range(8)]
    value=summarize_frames(flashed,list(np.arange(8)*.5),cfg)
    assert np.max(value['windows'][:,:9])<1e-6
    for i,image in enumerate(frames):ImageDraw.Draw(image).rectangle((4+i*6,30,18+i*6,60),fill='white')
    moving=summarize_frames(frames,list(np.arange(8)*.5),cfg)
    assert np.max(moving['windows'][:,:9])>.01
    assert static['bag'].shape==moving['bag'].shape and np.isfinite(moving['bag']).all()


def test_bag_inference_does_not_use_window_max_or_any_label():
    class Model:
        def predict_proba(self,features):return np.array([[.7,.3]]*len(features))
    # Numeric sentinels distinguish feature units. The function only accepts
    # the unlabeled feature dictionary, not original manifest metadata.
    features={'bag':np.zeros(60),'windows':np.ones((20,18))*1e6}
    assert evaluate.score(Model(),features,'bag')==.3


def test_non_square_uniform_flash_never_creates_padding_motion():
    cfg=json.loads(Path('config/motion-protocol.json').read_text())
    frames=[Image.new('RGB',(96,54),(i*20,)*3) for i in range(8)]
    values=summarize_frames(frames,list(np.arange(8)*.5),cfg)
    assert np.max(values['windows'][:,:9])<1e-6


def test_motion_entire_group_held_out(monkeypatch):
    cfg=json.loads(Path('config/motion-protocol.json').read_text());items=[]
    for group in range(3):
        for target in [0,1]:
            items.append({'group':group,'target':target,'label_sec':.5 if target else None,'sha256':str(group)+str(target),
                'bag':np.array([group,target]),'windows':np.array([[group,target]]),'window_times':np.array([.5])})
    def fit(train,arm,cfg):
        groups={item['group'] for item in train};assert len(groups)==2;return groups
    def score(model,features,arm):
        vector=features['bag'];assert int(vector[0]) not in model;return float(vector[1])
    monkeypatch.setattr(evaluate,'fit',fit);monkeypatch.setattr(evaluate,'score',score)
    reports,_=evaluate.grouped_oof(items,cfg)
    assert reports['bag']['confusion_matrix_tn_fp_fn_tp']==[[3,0],[0,3]]
    assert reports['window']['confusion_matrix_tn_fp_fn_tp']==[[3,0],[0,3]]
